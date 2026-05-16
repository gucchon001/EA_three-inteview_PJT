"""
一次ソース（テキスト・JSON）を読み込み、[OpenRouter](https://openrouter.ai/) 経由で
月次レポートの Markdown または HTML（Pattern B 風）草稿を出力する。

**レシピでの再実行**: チューニング・再現用に全オプションを JSON に固定する場合は
`python scripts/monthly_report_run_recipe.py docs/.../fixtures/report_recipes/*.recipe.json` を使う
（`fixtures/report_recipes/README.md`）。

前提:
  - リポジトリ直下の `.env` に OPENROUTER_API_KEY（必須）
  - `--artifact html` で v3 検証向け単一ファイル HTML を出力可能（ソース根拠 + 規約）。
  - **再現性**：既定 `--temperature` は **0.1**。`--seed INT` または環境変数 **`OPENROUTER_SEED`**（整数）で API に
    `seed` を付与（モデル／ルーティングによっては無視され得ます。完全な決定論は保証されません）。
  - `--artifact html` では温度を **最大 0.1** に丸めます（それ以上指定しても 0.1）。

他世帯でも同じ: `fetch_monthly_gws_sources.py` で `samples/reports/household_<slug>/sources` を埋めたうえで
`--source-preset pattern_b_gws_sl`（HL 取得時は `pattern_b_gws_sl_hl`）を指定する。

複数の生徒が同一教師 MTG Doc に並ぶときは、`--bundle-scope-reminder`（レシピでは `prompts.scope_reminder`）で対象教科・氏名スコープを明示できる。

十倉 v3（理想 HTML に構造寄せ・strict bundle）の例:

  python scripts/monthly_report_draft_openrouter.py ^
    --sources-dir samples/reports/household_tokura/sources ^
    --source-preset pattern_b_gws_sl ^
    --ideal-html docs/samples/monthly-reports/fixtures/tokura_2026-04_user_ideal.html ^
    --structure-from-ideal ^
    --max-bundle-chars 400000 ^
    --artifact html ^
    --seed 704050 ^
    --output docs/samples/monthly-reports/monthly_2026-04_tokura_v3_report.html

（従来）v2 を構造参考にする場合:

  python scripts/monthly_report_draft_openrouter.py ^
    --sources-dir samples/reports/household_tokura/sources ^
    --with-gws-json ^
    --ideal-html docs/samples/monthly-reports/fixtures/tokura_2026-04_user_ideal.html ^
    --structure-html docs/samples/monthly-reports/monthly_2026-04_tokura_v2_report.html ^
    --artifact html ^
    --output docs/samples/monthly-reports/monthly_2026-04_tokura_v3_report.html
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from eb_app.monthly_reports.llm_messages import build_monthly_report_messages

PRESETS_DEFAULT_PATH = Path(__file__).resolve().parent / "monthly_report_source_presets.json"


def load_source_preset_globs(presets_path: Path, preset_name: str) -> tuple[str, list[str]]:
    """プリセット名から (description, globs) を返す。"""
    if not presets_path.is_file():
        raise FileNotFoundError(f"presets ファイルが見つかりません: {presets_path}")
    raw = json.loads(presets_path.read_text(encoding="utf-8"))
    block = raw.get("presets") or {}
    entry = block.get(preset_name)
    if not isinstance(entry, dict):
        names = ", ".join(sorted(block.keys())) if isinstance(block, dict) else ""
        raise KeyError(f"不明な --source-preset: {preset_name!r}（利用可能: {names}）")
    globs_raw = entry.get("globs") or []
    if not isinstance(globs_raw, list) or not all(isinstance(x, str) for x in globs_raw):
        raise ValueError(f"プリセット {preset_name!r} の globs が不正です")
    desc = str(entry.get("description") or "").strip()
    return desc, globs_raw


def list_source_preset_names(presets_path: Path) -> list[str]:
    if not presets_path.is_file():
        return []
    raw = json.loads(presets_path.read_text(encoding="utf-8"))
    block = raw.get("presets") or {}
    if not isinstance(block, dict):
        return []
    return sorted(block.keys())


def html_to_plain(html: str) -> str:
    t = re.sub(r"(?is)<script\b[^>]*>.*?</script>", " ", html)
    t = re.sub(r"(?is)<style\b[^>]*>.*?</style>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def truncate_middle(s: str, max_chars: int) -> tuple[str, bool]:
    if len(s) <= max_chars:
        return s, False
    half = max(800, max_chars // 2 - 200)
    return s[:half] + "\n\n...[TRUNCATED middle]...\n\n" + s[-half:], True


def strip_md_code_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        lines = s.split("\n")
        if len(lines) >= 2 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
        if lines[0].startswith("```"):
            rest = "\n".join(lines[1:]).strip()
            if rest.endswith("```"):
                rest = rest[: rest.rfind("```")].rstrip()
            return rest.strip()
    return s


try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[misc, assignment]


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_REPORT_MODEL = "anthropic/claude-sonnet-4.6"


def resolve_report_model(cli_override: str) -> str:
    """レポート本文生成用モデル。CLI > OPENROUTER_MODEL_REPORT > OPENROUTER_MODEL > 既定（Sonnet系）。"""
    if cli_override.strip():
        return cli_override.strip()
    for env_key in ("OPENROUTER_MODEL_REPORT", "OPENROUTER_MODEL"):
        v = (os.environ.get(env_key) or "").strip()
        if v:
            return v
    return DEFAULT_REPORT_MODEL


def resolve_openrouter_seed(cli_seed: int | None) -> int | None:
    """CLI --seed が優先。未指定時は OPENROUTER_SEED（整数）。"""
    if cli_seed is not None:
        return cli_seed
    raw = (os.environ.get("OPENROUTER_SEED") or "").strip()
    if not raw:
        return None
    try:
        return int(raw, 10)
    except ValueError:
        print(
            f"警告: OPENROUTER_SEED は整数のみ有効です（無視）: {raw!r}",
            file=sys.stderr,
        )
        return None


def _load_env() -> None:
    env_path = ROOT / ".env"
    if load_dotenv is not None:
        load_dotenv(env_path)
        return
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key and key not in os.environ:
            if (len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'"):
                val = val[1:-1]
            os.environ[key] = val


def gather_source_text(sources_dir: Path, patterns: tuple[str, ...]) -> tuple[str, list[str]]:
    """Return (combined text with file headers, list of relative paths used)."""

    def _drop_redundant_mtg_json(paths: list[Path]) -> list[Path]:
        """同フォルダに MTG の .txt があるときは同名 .json を束ねない（トークン重複回避）。"""
        has_txt = any(p.name == "_gws_doc_teacher_MTG_gemini.txt" for p in paths)
        if not has_txt:
            return paths
        return [p for p in paths if p.name != "_gws_doc_teacher_MTG_gemini.json"]

    used: list[Path] = []
    chunks: list[str] = []

    files: list[Path] = []
    for pat in patterns:
        files.extend(sorted(sources_dir.glob(pat)))
    uniq_list = _drop_redundant_mtg_json(sorted({p.resolve() for p in files}, key=lambda p: str(p).lower()))

    for p in uniq_list:
        if not p.is_file():
            continue
        used.append(p)
        chunks.append(f"### FILE: {p.name}\n\n")
        chunks.append(p.read_text(encoding="utf-8", errors="replace"))
        chunks.append("\n\n")

    rel: list[str] = []
    for x in used:
        try:
            rel.append(x.relative_to(sources_dir).as_posix())
        except ValueError:
            rel.append(x.name)
    return "".join(chunks), rel


def truncate_bundle(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[: max_chars - 400] + "\n\n...[TRUNCATED: increase --max-bundle-chars]...\n", True


def chat_completions(
    api_key: str,
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
    timeout_sec: float,
    seed: int | None = None,
) -> str:
    body: dict[str, object] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if seed is not None:
        body["seed"] = seed
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")

    req = Request(
        OPENROUTER_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/local/ea_three-interview_pjt",
            "X-Title": "EA monthly report draft (OpenRouter)",
        },
    )
    try:
        with urlopen(req, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8")
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace") if e.fp else str(e)
        raise RuntimeError(f"OpenRouter HTTP {e.code}: {detail}") from e
    except URLError as e:
        raise RuntimeError(f"OpenRouter request failed: {e}") from e

    data = json.loads(body)
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"OpenRouter に choices がありません: {body[:1200]}")
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"OpenRouter の content が空です: {body[:1200]}")
    return content


def build_prompts(
    *,
    artifact: str,
    rules_excerpt_path: Path | None,
    template_path: Path,
    bundle: str,
    ideal_plain: str,
    structure_html: str,
    scope_reminder: str | None = None,
) -> list[dict[str, str]]:
    return build_monthly_report_messages(
        artifact=artifact,
        rules_excerpt_path=rules_excerpt_path,
        template_path=template_path,
        bundle=bundle,
        ideal_plain=ideal_plain,
        structure_html=structure_html,
        prompt_scope_notes=scope_reminder,
    )


def main() -> int:
    default_template = ROOT / "docs/samples/monthly-reports/monthly_pattern_b_content.template.md"
    default_tone = ROOT / ".cursor/skills/monthly-report-notebooklm-patterns/references/family-facing-tone.md"

    p = argparse.ArgumentParser(description="月次レポート草稿を OpenRouter で生成（Markdown または HTML）")
    p.add_argument(
        "--sources-dir",
        type=Path,
        default=None,
        help="一次ソースがあるディレクトリ（例: household_*/sources）。--list-source-presets 時は省略可",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="書き出し先（.md または .html）。--list-source-presets 時は省略可",
    )
    p.add_argument("--template", type=Path, default=default_template, help="正本テンプレ Markdown のパス")
    p.add_argument(
        "--family-tone-md",
        type=Path,
        default=default_tone,
        help="文体ガイド family-facing-tone.md のパス（無ければスキップ）",
    )
    p.add_argument(
        "--artifact",
        choices=("md", "html"),
        default="md",
        help="出力形式。html は Pattern B 単一ファイル想定。",
    )
    p.add_argument(
        "--with-gws-json",
        action="store_true",
        help="束ねるファイルに `_gws_*.json` を追加（*.txt/*.md のみ既定のとき）。",
    )
    p.add_argument(
        "--presets-json",
        type=Path,
        default=PRESETS_DEFAULT_PATH,
        help="--source-preset の定義 JSON（既定: scripts/monthly_report_source_presets.json）",
    )
    p.add_argument(
        "--source-preset",
        default=None,
        metavar="NAME",
        help="既定の gws 出力束ね（例: pattern_b_gws_sl, pattern_b_gws_sl_hl）。--list-source-presets で一覧。",
    )
    p.add_argument(
        "--list-source-presets",
        action="store_true",
        help="--presets-json にあるプリセット名を表示して終了する。",
    )
    p.add_argument(
        "--preset-tokura-sources",
        action="store_true",
        help="非推奨: --source-preset pattern_b_gws_sl と同じ（後方互換）。",
    )
    p.add_argument(
        "--ideal-html",
        type=Path,
        default=None,
        help="ユーザー検収済み HTML。プレーン化し語感参考として渡す（事実転載禁止）。",
    )
    p.add_argument(
        "--structure-html",
        type=Path,
        default=None,
        help="レイアウト踏襲用の参考 HTML（長い場合は切り詰め）。",
    )
    p.add_argument(
        "--structure-from-ideal",
        action="store_true",
        help="--ideal-html と同一ファイルを構造参考としても渡す（ユーザー理想のセクション数・見出しに揃えやすい）。",
    )
    p.add_argument("--structure-max-chars", type=int, default=48_000)
    p.add_argument("--ideal-max-chars", type=int, default=12_000)
    p.add_argument(
        "--glob",
        action="append",
        dest="globs",
        default=[],
        metavar="PATTERN",
        help="sources 内で読む glob（複数可）。未指定時は *.txt と *.md（+ --with-gws-json）",
    )
    p.add_argument(
        "--model",
        default="",
        help="OpenRouter の model ID（未指定時は環境変数→Sonnet 既定）",
    )
    p.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        metavar="FLOAT",
        help="サンプリング温度（既定 0.1。--artifact html では最大 0.1 に制限）。",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="INT",
        help="疑似乱数シードを API に渡す（再現寄り）。未指定時は OPENROUTER_SEED。",
    )
    p.add_argument("--max-tokens", type=int, default=16_384)
    p.add_argument("--timeout", type=float, default=420.0)
    p.add_argument("--max-bundle-chars", type=int, default=150_000)
    p.add_argument(
        "--bundle-scope-reminder",
        default=None,
        metavar="TEXT",
        help="根拠ソースの直前に挿入するスコープ注記（例: 複数生徒 MTG で科目・生徒を限定）。",
    )

    args = p.parse_args()
    presets_json = args.presets_json.resolve()
    if args.list_source_presets:
        if not presets_json.is_file():
            print(f"presets が見つかりません: {presets_json}", file=sys.stderr)
            return 1
        names = list_source_preset_names(presets_json)
        raw = json.loads(presets_json.read_text(encoding="utf-8"))
        block = raw.get("presets") or {}
        for name in names:
            ent = block.get(name) if isinstance(block, dict) else None
            desc = ""
            if isinstance(ent, dict):
                desc = str(ent.get("description") or "").strip()
            line = name
            if desc:
                line += " - " + desc
            print(line)
        return 0

    if args.sources_dir is None or args.output is None:
        print(
            "`--sources-dir` と `--output` は必須です（--list-source-presets 以外）。",
            file=sys.stderr,
        )
        return 2

    sources_dir = args.sources_dir.resolve()
    if not sources_dir.is_dir():
        print(f"sources-dir がディレクトリではありません: {sources_dir}", file=sys.stderr)
        return 1

    has_explicit_globs = bool(args.globs)
    has_preset = bool(args.source_preset)
    has_tokura = bool(args.preset_tokura_sources)
    if has_explicit_globs and (has_preset or has_tokura):
        print(
            "`--glob` と `--source-preset` / `--preset-tokura-sources` は同時に使えません。",
            file=sys.stderr,
        )
        return 2
    if has_preset and has_tokura:
        print(
            "`--source-preset` と `--preset-tokura-sources` は同時に使えません。",
            file=sys.stderr,
        )
        return 2

    preset_name: str | None = args.source_preset
    if has_tokura:
        preset_name = "pattern_b_gws_sl"
        print(
            "注意: `--preset-tokura-sources` は非推奨です。代わりに `--source-preset pattern_b_gws_sl` を使ってください。",
            file=sys.stderr,
        )

    if has_explicit_globs:
        globs_list = list(args.globs)
        if args.with_gws_json and "_gws_*.json" not in globs_list:
            globs_list.append("_gws_*.json")
    elif preset_name:
        try:
            _desc, globs_from_preset = load_source_preset_globs(presets_json, preset_name)
        except (OSError, json.JSONDecodeError, KeyError, ValueError, FileNotFoundError) as e:
            print(f"--source-preset の解決に失敗しました: {e}", file=sys.stderr)
            return 2
        globs_list = list(globs_from_preset)
    else:
        globs_list = ["*.txt", "*.md"]
        if args.with_gws_json and "_gws_*.json" not in globs_list:
            globs_list.append("_gws_*.json")
    globs = tuple(globs_list)

    _load_env()
    api_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        print("OPENROUTER_API_KEY が設定されていません（.env または環境変数）。", file=sys.stderr)
        return 1

    model = resolve_report_model(args.model)

    bundle, used = gather_source_text(sources_dir, globs)
    if not bundle.strip():
        print(f"coverage: {globs} に該当するファイルがありませんでした: {sources_dir}", file=sys.stderr)
        return 1

    bundle_out, truncated = truncate_bundle(bundle, args.max_bundle_chars)
    seed = resolve_openrouter_seed(args.seed)

    template_path = args.template.resolve()
    if not template_path.is_file():
        print(f"template が見つかりません: {template_path}", file=sys.stderr)
        return 1

    tone_path: Path | None = args.family_tone_md
    if tone_path and not tone_path.is_file():
        tone_path = None

    ideal_plain = ""
    if args.ideal_html:
        ip = args.ideal_html.resolve()
        if not ip.is_file():
            print(f"--ideal-html が見つかりません: {ip}", file=sys.stderr)
            return 1
        raw_ideal = ip.read_text(encoding="utf-8", errors="replace")
        ideal_plain, _it = truncate_middle(html_to_plain(raw_ideal), args.ideal_max_chars)

    structure_html = ""
    if args.structure_from_ideal:
        if not args.ideal_html:
            print("--structure-from-ideal には --ideal-html が必要です。", file=sys.stderr)
            return 1
        ip = args.ideal_html.resolve()
        if not ip.is_file():
            print(f"--ideal-html が見つかりません: {ip}", file=sys.stderr)
            return 1
        structure_html, _st = truncate_middle(
            ip.read_text(encoding="utf-8", errors="replace"), args.structure_max_chars
        )
    elif args.structure_html:
        sp = args.structure_html.resolve()
        if not sp.is_file():
            print(f"--structure-html が見つかりません: {sp}", file=sys.stderr)
            return 1
        structure_html, _st = truncate_middle(
            sp.read_text(encoding="utf-8", errors="replace"), args.structure_max_chars
        )

    messages = build_prompts(
        artifact=args.artifact,
        rules_excerpt_path=tone_path,
        template_path=template_path,
        bundle=bundle_out,
        ideal_plain=ideal_plain,
        structure_html=structure_html,
        scope_reminder=args.bundle_scope_reminder,
    )

    max_tokens = args.max_tokens
    temperature = max(0.0, float(args.temperature))
    if float(args.temperature) < 0 or float(args.temperature) > 2:
        print("temperature は 0〜2 の範囲が無難です。", file=sys.stderr)
    if args.artifact == "html":
        max_tokens = max(max_tokens, 24_576)
        temperature = min(temperature, 0.1)

    preamble = (
        f"<!-- openrouter draft artifact={args.artifact} sources: {', '.join(used)} "
        f"truncated={truncated} model={model} temperature={temperature}"
        + (f" seed={seed}" if seed is not None else " seed=null")
        + " -->\n\n"
    )

    try:
        content = chat_completions(
            api_key,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_sec=args.timeout,
            seed=seed,
        )
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    if args.artifact == "html":
        content = strip_md_code_fence(content)
        if "<!DOCTYPE html>" not in content and "<html" not in content.lower():
            print("警告: 出力に html 要素が見あたりません。モデルまたは max-tokens を確認してください。", file=sys.stderr)

    out_path = args.output.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(preamble + content, encoding="utf-8", newline="\n")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
