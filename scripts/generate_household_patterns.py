"""
household_giga の Pattern A〜D をテンプレとして、household_registry.json の各世帯向けに
HTML と sources（時系列の NotebookLM 書き出し等）を生成する。

前提: nlm が PATH にあり、PYTHONUTF8=1 で本文取得できること。

使用例（プロジェクトルート）:
  python scripts/generate_household_patterns.py
  python scripts/generate_household_patterns.py --slug takafuji
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "samples" / "reports"
REGISTRY_PATH = REPORTS / "household_registry.json"
TEMPLATE = REPORTS / "household_giga"
NL_TO_MD = ROOT / "scripts" / "notebooklm_json_to_txt.py"

PATTERN_FILES = [
    "pattern_a_responsive.html",
    "pattern_b.html",
    "pattern_c_simple.html",
    "pattern_d.html",
]


def pattern_c_student_line(h: dict) -> str:
    ph = h["pattern_honorific"]
    m = re.match(r"^(.+?さま)（(.+)）$", ph)
    if not m:
        return h["meta_student_line"]
    name_sama, yomi = m.group(1), m.group(2)
    display = name_sama.replace("さま", " 様", 1)
    sid = h["student_id"]
    c = h["course"]
    return f"{display}（{yomi}・{sid}・{c}）"


def pattern_b_td_name(h: dict) -> str:
    ph = h["pattern_honorific"]
    m = re.match(r"^(.+?さま)（(.+)）$", ph)
    if not m:
        return h["meta_student_line"]
    name_sama, yomi = m.group(1), m.group(2)
    display = name_sama.replace("さま", " 様", 1)
    return f"{display}（{yomi}・{h['course']}）"


def run_nlm_content(source_id: str, out_txt: Path) -> None:
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    subprocess.run(
        ["nlm", "content", "source", source_id, "-o", str(out_txt)],
        check=True,
        env=env,
        cwd=ROOT,
    )


def body_to_nl_json(body: str, title: str) -> dict:
    return {
        "status": "success",
        "content": body,
        "title": title,
        "source_type": "unknown",
        "char_count": len(body),
    }


def personalize_html(html: str, h: dict, slug: str) -> str:
    sid = h["student_id"]
    rpt = f"RPT-202603-{sid}" if sid != "TBD" else "RPT-202603-TBD"
    select_val = f"{slug}{sid}" if sid != "TBD" else f"{slug}TBD"
    path_old = "samples/reports/household_giga/"
    path_new = f"samples/reports/household_{slug}/"

    generic_card_a = (
        "<p><strong>一次情報</strong>は <code>sources/00_260319_時系列まとめ_NotebookLM.md</code> と "
        "<code>sources/03_学習計画表_プレースホルダー.md</code>（実シートに差し替え）を優先し、"
        "教師MTG・ご家庭の個別ソースは NotebookLM から追記してください。</p>"
    )
    generic_card_d = (
        "<p><strong>一次情報</strong>は <code>sources/00_260319_時系列まとめ_NotebookLM.md</code> を参照し、"
        "KPI 文面を編集してください。</p>"
    )

    out = html
    out = out.replace(
        "儀賀家 Math AA SL — 学習状況分析レポート（Pattern A）",
        f"{h['family_house']} {h['course']} — 学習状況分析レポート（Pattern A）",
    )
    out = out.replace(
        "儀賀さま（ぎがさん）Math AA SL — 学習状況分析レポート（Pattern B）",
        f"{h['pattern_honorific']}{h['course']} — 学習状況分析レポート（Pattern B）",
    )
    out = out.replace(
        "儀賀さま（ぎがさん）Math AA SL — 学習レポート（Pattern C）",
        f"{h['pattern_honorific']}{h['course']} — 学習レポート（Pattern C）",
    )
    out = out.replace(
        "儀賀さま（ぎがさん）Math AA SL — 学習ダッシュボード（Pattern D）",
        f"{h['pattern_honorific']}{h['course']} — 学習ダッシュボード（Pattern D）",
    )
    out = out.replace(
        "学習状況分析レポート（儀賀さま・ぎがさん）",
        f"学習状況分析レポート（{h['pattern_honorific']}）",
    )
    out = out.replace("儀賀 様（ぎがさん・70569・Math AA SL）", pattern_c_student_line(h))
    out = out.replace(
        "儀賀さま（ぎがさん・70569・Math AA SL）",
        f"{h['pattern_honorific']}・{sid}・{h['course']}",
    )
    out = out.replace(
        "Math AA SL・生徒番号 70569｜",
        f"{h['course']}・生徒番号 {sid}｜",
    )
    out = out.replace(
        "対象：儀賀さま（ぎがさん）／生徒番号 70569・Math AA SL",
        f"対象：{h['pattern_honorific']}／生徒番号 {sid}・{h['course']}",
    )
    out = out.replace("<td>儀賀 様（ぎがさん・Math AA SL）</td>", f"<td>{pattern_b_td_name(h)}</td>")
    out = out.replace("<td>70569</td>", f"<td>{sid}</td>")
    out = out.replace(
        "<p>学校試験に向け Paper 1・2 を実施。Calculus は<strong>約71%</strong>と良好。一方で <strong>Geometry / Trigonometry（角度問題）</strong>は弱点として共有されています（01）。</p>",
        generic_card_a,
    )
    out = out.replace(
        "<p>Paper 1・2 を実施。Calculus は<strong>約71%</strong>。Trig/Geometry は強化中です。</p>",
        generic_card_d,
    )

    repl: list[tuple[str, str]] = [
        (path_old, path_new),
        ("household_giga/", f"household_{slug}/"),
        ("儀賀家・Pattern", f"{h['family_house']}・Pattern"),
        ("儀賀家 Math", f"{h['family_house']} Math"),
        ("儀賀さま（ぎがさん）", h["pattern_honorific"]),
        ("儀賀 様（Math AA SL・生徒番号 70569）", h["meta_student_line"]),
        ("儀賀 様（ぎがさん・Math AA SL・70569）", h["meta_student_line"]),
        ("儀賀 様（ぎがさん・Math AA SL）", h["meta_student_line"]),
        ("儀賀 様（Math AA SL・生徒番号 70569）", h["meta_student_line"]),
        ("儀賀 様（ぎがさん・70569・Math AA SL）", h["meta_student_line"]),
        ("儀賀 様（ぎがさん・70569）", h["meta_student_line"]),
        ("儀賀 様（ぎがさん）", h["meta_student_line"]),
        ("RPT-202603-70569", rpt),
        ("giga70569", select_val),
        ("（70569 儀賀さま Drive ソースあり）", f"（{h['nl_drive_blurb']}）"),
    ]

    for a, b in repl:
        out = out.replace(a, b)

    if sid != "TBD":
        out = out.replace("70569", sid)

    # 「儀賀さま（ぎがさん・」のあとが「）」で終わらないため、単体置換で残るパターンを潰す
    legacy_opt = f"儀賀さま（ぎがさん・{sid}・Math AA SL）"
    if legacy_opt in out:
        out = out.replace(
            legacy_opt,
            f"{h['pattern_honorific']}・{sid}・{h['course']}",
        )

    # sources リンクをこの世帯の一次情報に合わせる（01〜04 未配置時は 00 / プレースホルダー）
    out = out.replace("sources/01_教師MTG_20260225.md", "sources/00_260319_時系列まとめ_NotebookLM.md")
    out = out.replace("sources/02_家庭面談・提案_20260127.md", "sources/00_260319_時系列まとめ_NotebookLM.md")
    out = out.replace("sources/03_学習計画表_20260331.md", "sources/03_学習計画表_プレースホルダー.md")
    out = out.replace("sources/04_参照メール_レビュー用.md", "sources/04_参照メール_プレースホルダー.md")

    out = out.replace('<span class="kpi-value">71%</span>', '<span class="kpi-value">—</span>')
    out = out.replace('<span class="number">71%</span>', '<span class="number">—</span>')
    out = out.replace("約71%", "（要確認）")
    out = out.replace('style="width: 71%"', 'style="width: 0%"')
    out = out.replace(
        "Calculus 正答率 約71%、Paper1・2 演習",
        "（要確認）一次情報・03 を参照",
    )
    out = out.replace("Calculus 約71%、Paper1・2", "（要確認）一次情報参照")
    out = re.sub(
        r"data: \[35, 42, 48, 55, 65, 71\]",
        "data: [0, 0, 0, 0, 0, 0]  /* デモ: sources の数値で置換 */",
        out,
    )

    return out


def write_placeholder_sources(sources_dir: Path, h: dict, slug: str) -> None:
    p03 = sources_dir / "03_学習計画表_プレースホルダー.md"
    p03.write_text(
        "---\nschema_version: 1\nkind: household_source\nhousehold_slug: household_"
        f"{slug}\nsource_slot: \"03\"\ntitle: \"学習計画表（スナップショットを差し替え）\"\n---\n\n"
        "※ **数値の正**は Google スプレッドシートの最新スナップショットを `03_学習計画表_YYYYMMDD.md` として保存し、"
        "本ファイルと差し替えてください。\n",
        encoding="utf-8",
    )
    p04 = sources_dir / "04_参照メール_プレースホルダー.md"
    p04.write_text(
        "---\nschema_version: 1\nkind: household_source\nhousehold_slug: household_"
        f"{slug}\nsource_slot: \"04\"\ntitle: \"レビュー用メール（任意）\"\n---\n\n"
        "（任意）レビュー比較用のメール要約・リンクを記載。\n",
        encoding="utf-8",
    )


def write_source_ids(sources_dir: Path, h: dict, slug: str) -> None:
    nb = REGISTRY_PATH.read_text(encoding="utf-8")
    notebook_id = json.loads(nb)["notebook_id"]
    p = sources_dir / f"notebooklm_source_ids_{slug}.md"
    p.write_text(
        f"""---
schema_version: 1
kind: source_registry
household_slug: household_{slug}
notebooklm_notebook_id: "{notebook_id}"
language: ja
---

NotebookLM ノート: EA_生徒状況分析

| 用途 | source_id |
|------|-----------|
| 260319 時系列まとめ | {h["timeline_source_id"]} |

※ 教師MTG・ご家庭提案・Drive は NotebookLM 上のタイトルで検索し、行を追記してください。
""",
        encoding="utf-8",
    )

    readme = sources_dir / "README.md"
    readme.write_text(
        f"# sources（household_{slug}）\n\n"
        "- `00_260319_時系列まとめ_NotebookLM.md` … NotebookLM の時系列ソースを `nlm content source` → JSON → "
        "`notebooklm_json_to_txt.py` で生成。\n"
        "- `03_学習計画表_プレースホルダー.md` … 実シートのスナップショットに差し替え。\n"
        "- 01・02 相当の個別ソースは NotebookLM から `source_get_content` で取り込み、このフォルダに保存。\n",
        encoding="utf-8",
    )


def process_household(h: dict) -> None:
    slug = h["slug"]
    dest = REPORTS / f"household_{slug}"
    sources_dir = dest / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    title = f"260319_{h['pattern_honorific'].split('（')[0]} 面談・教師MTG 時系列まとめ"
    body_path = sources_dir / "_timeline_body.txt"
    json_path = sources_dir / "_nl_timeline.json"
    md_path = sources_dir / "00_260319_時系列まとめ_NotebookLM.md"

    print(f"=== {slug}: fetch timeline {h['timeline_source_id']}")
    run_nlm_content(h["timeline_source_id"], body_path)
    body = body_path.read_text(encoding="utf-8")
    json_path.write_text(json.dumps(body_to_nl_json(body, title), ensure_ascii=False), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(NL_TO_MD), str(json_path), str(md_path)],
        check=True,
        cwd=ROOT,
    )
    body_path.unlink(missing_ok=True)

    write_placeholder_sources(sources_dir, h, slug)
    write_source_ids(sources_dir, h, slug)

    for fname in PATTERN_FILES:
        src = TEMPLATE / fname
        raw = src.read_text(encoding="utf-8")
        out = personalize_html(raw, h, slug)
        (dest / fname).write_text(out, encoding="utf-8", newline="\n")
        print(f"  wrote {dest / fname}")

    print(f"=== done household_{slug}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", help="単一世帯のみ（例: takafuji）")
    args = parser.parse_args()

    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    households = data["households"]
    if args.slug:
        households = [h for h in households if h["slug"] == args.slug]
        if not households:
            print("unknown slug", args.slug)
            sys.exit(1)

    for h in households:
        process_household(h)

    print("完了。samples/reports/index.html の表を更新してください。")


if __name__ == "__main__":
    main()
