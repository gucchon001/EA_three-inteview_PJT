"""
月次レポート HTML/Markdown 生成を「レシピ JSON」単位で固定し、チューニング・再現に使う。

  python scripts/monthly_report_run_recipe.py \\
    docs/samples/monthly-reports/fixtures/report_recipes/hirayama_physics_pattern_b_shell.recipe.json

単発の上書き（例 seed のみ試す）:

  python scripts/monthly_report_run_recipe.py path/to/recipe.json --seed 42

実処理は scripts/monthly_report_draft_openrouter.py に委譲する。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OPENROUTER_SCRIPT = ROOT / "scripts" / "monthly_report_draft_openrouter.py"


def _rel(p: str | None) -> str | None:
    if not p:
        return None
    return str(p).strip() or None


def recipe_to_workshop_job_fields(rec: dict[str, Any]) -> dict[str, str | None]:
    rv = rec.get("recipe_version")
    if rv != 1:
        raise ValueError(f"未対応の recipe_version: {rv!r}（1のみ）")

    prompts = rec.get("prompts") or {}
    scope_reminder = prompts.get("scope_reminder")
    prompt_scope_notes = (
        str(scope_reminder).strip() if scope_reminder is not None else None
    )
    return {"prompt_scope_notes": prompt_scope_notes or None}


def _recipe_to_argv(rec: dict[str, Any], root: Path) -> list[str]:
    rv = rec.get("recipe_version")
    if rv != 1:
        raise ValueError(f"未対応の recipe_version: {rv!r}（1のみ）")

    sources = rec.get("sources") or {}
    prompts = rec.get("prompts") or {}
    structure = rec.get("structure") or {}
    gen = rec.get("generation") or {}
    output = rec.get("output")
    if not output:
        raise ValueError("recipe に output がありません")

    src_dir = sources.get("dir")
    if not src_dir:
        raise ValueError("sources.dir がありません")

    out_raw = Path(str(output))
    out_abs = str(out_raw.resolve()) if out_raw.is_absolute() else str((root / out_raw).resolve())

    argv: list[str] = [
        str(OPENROUTER_SCRIPT),
        "--sources-dir",
        str(root / src_dir),
        "--output",
        out_abs,
        "--template",
        str(root / (prompts.get("template") or "docs/samples/monthly-reports/monthly_pattern_b_content.template.md")),
        "--family-tone-md",
        str(
            root
            / (
                prompts.get("family_tone_md")
                or ".cursor/skills/monthly-report-notebooklm-patterns/references/family-facing-tone.md"
            )
        ),
        "--artifact",
        str(gen.get("artifact") or "md"),
        "--temperature",
        str(float(gen.get("temperature", 0.1))),
        "--max-tokens",
        str(int(gen.get("max_tokens", 16_384))),
        "--timeout",
        str(float(gen.get("timeout_sec", 420.0))),
        "--max-bundle-chars",
        str(int(gen.get("max_bundle_chars", 150_000))),
        "--structure-max-chars",
        str(int(structure.get("structure_max_chars", 48_000))),
        "--ideal-max-chars",
        str(int(structure.get("ideal_max_chars", 12_000))),
    ]

    model = gen.get("model")
    if model is None:
        model = ""
    argv.extend(["--model", str(model)])

    seed = gen.get("seed")
    if seed is not None:
        argv.extend(["--seed", str(int(seed))])

    scope_r = recipe_to_workshop_job_fields(rec)["prompt_scope_notes"]
    if scope_r:
        argv.extend(["--bundle-scope-reminder", scope_r])

    pj = sources.get("presets_json")
    argv.extend(["--presets-json", str(root / (pj or "scripts/monthly_report_source_presets.json"))])

    globs_raw = sources.get("globs")
    globs_list: list[str] = list(globs_raw) if isinstance(globs_raw, list) else []
    for g in globs_list:
        argv.extend(["--glob", str(g)])

    if sources.get("with_gws_json"):
        argv.append("--with-gws-json")

    if sources.get("preset_tokura_sources"):
        argv.append("--preset-tokura-sources")
    else:
        sp = sources.get("preset")
        if globs_list:
            if sp:
                raise ValueError("sources.preset と sources.globs は併用できません")
        elif sp:
            argv.extend(["--source-preset", str(sp)])

    ideal_html = _rel(structure.get("ideal_html"))
    structure_html = _rel(structure.get("structure_html"))
    sf_ideal = bool(structure.get("structure_from_ideal"))

    if ideal_html:
        argv.extend(["--ideal-html", str(root / ideal_html)])
    if structure_html:
        argv.extend(["--structure-html", str(root / structure_html)])
    if sf_ideal:
        argv.append("--structure-from-ideal")

    return argv


def resolve_output_for_recipe(rec: dict[str, Any], root: Path) -> Path | None:
    out = rec.get("output")
    if not out:
        return None
    p = Path(str(out))
    return p.resolve() if p.is_absolute() else (root / p).resolve()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1_048_576), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(description="レシピ JSON に従って monthly_report_draft_openrouter.py を実行")
    p.add_argument("recipe", type=Path, help="*.recipe.json")
    p.add_argument("--dry-run", action="store_true", help="実行せず構築した argv を表示")
    p.add_argument(
        "--record",
        type=Path,
        default=None,
        help="JSON Lines でラン概要をこのパスへ追記（チューニング比較用）",
    )
    p.add_argument("--seed", type=int, default=None, help="レシピの seed を上書き")
    p.add_argument("--temperature", type=float, default=None, help="レシピの temperature を上書き")
    p.add_argument("--model", default=None, help="レシピの model を上書き（空文字で環境既定）")
    p.add_argument("--output", type=Path, default=None, help="レシピの output を上書き（ルート相対でも絶対でも可）")
    args = p.parse_args()

    recipe_path = args.recipe.resolve()
    if not recipe_path.is_file():
        print(f"レシピが見つかりません: {recipe_path}", file=sys.stderr)
        return 2

    raw = json.loads(recipe_path.read_text(encoding="utf-8"))
    if args.seed is not None:
        gen = raw.setdefault("generation", {})
        gen["seed"] = int(args.seed)
    if args.temperature is not None:
        raw.setdefault("generation", {})["temperature"] = float(args.temperature)
    if args.model is not None:
        raw.setdefault("generation", {})["model"] = args.model
    if args.output is not None:
        raw["output"] = str(args.output.resolve())

    try:
        argv_tail = _recipe_to_argv(raw, ROOT)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    full_argv = [sys.executable] + argv_tail
    print("→", " ".join(full_argv[:6]), "...")

    if args.dry_run:
        print(json.dumps(full_argv, ensure_ascii=False, indent=2))
        return 0

    r = subprocess.run(full_argv, cwd=str(ROOT))
    code = int(r.returncode or 0)

    if args.record and code == 0:
        try:
            rec_rel = recipe_path.relative_to(ROOT).as_posix()
        except ValueError:
            rec_rel = str(recipe_path)
        outp_final = resolve_output_for_recipe(raw, ROOT)
        row: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "recipe_path": rec_rel,
            "recipe_id": raw.get("id"),
            "recipe_sha256": _sha256_file(recipe_path),
            "openrouter_exit": code,
            "output_sha256": _sha256_file(outp_final)
            if outp_final and outp_final.is_file()
            else None,
            "generation": raw.get("generation"),
        }
        lp = args.record.resolve()
        lp.parent.mkdir(parents=True, exist_ok=True)
        with lp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"recorded {lp}")

    return code


if __name__ == "__main__":
    raise SystemExit(main())
