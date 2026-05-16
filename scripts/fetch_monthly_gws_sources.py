"""
学習計画表（Sheets）と教師 MTG（Docs）を gws で取得し、UTF-8 JSON をローカルに保存する。
Windows では npm の gws.cmd を cmd /c 経由で起動する（subprocess の直接 spawn が失敗するため）。

例（プロジェクトルート）:
  python scripts/fetch_monthly_gws_sources.py ^
    --spreadsheet-id "YOUR_SPREADSHEET_ID" ^
    --document-id "YOUR_DOC_ID" ^
    --out-dir samples/reports/household_foo/sources

  # HL タブ不要なら:
  # python scripts/fetch_monthly_gws_sources.py --spreadsheet-id "..." --document-id "..." ^
  #   --out-dir ... --no-hl-lesson-plan

  # 取得後に OpenRouter でドラフト（HL なし: pattern_b_gws_sl、あり: pattern_b_gws_sl_hl）:
  # python scripts/monthly_report_draft_openrouter.py ^
  #   --sources-dir samples/reports/household_foo/sources --source-preset pattern_b_gws_sl_hl ^
  #   --artifact md --output path/to/monthly_Y-MM_slug_draft.md
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _gws_argv() -> list[str]:
    """Windows: npm's gws.cmd は CreateProcess で直起動できないため cmd /c を挟む。"""
    appdata = os.environ.get("APPDATA", "")
    cmd_path = Path(appdata) / "npm" / "gws.cmd"
    if cmd_path.is_file():
        return ["cmd", "/c", str(cmd_path)]
    return ["gws"]


def _run_gws_json(args_list: list[str], cwd: Path) -> bytes:
    p = subprocess.run(args_list, cwd=cwd, capture_output=True)
    if p.returncode != 0:
        sys.stderr.write(p.stderr.decode("utf-8", errors="replace"))
        raise SystemExit(p.returncode)
    return p.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Sheets/Docs JSON via gws (UTF-8 binary stdout).")
    parser.add_argument("--spreadsheet-id", required=True, help="Spreadsheet ID from URL /d/<id>/")
    parser.add_argument("--document-id", required=True, help="Google Doc ID from /document/d/<id>/")
    parser.add_argument(
        "--out-dir",
        required=True,
        type=Path,
        help="Output directory (e.g. samples/reports/household_slug/sources)",
    )
    parser.add_argument(
        "--range-student",
        default="student!A1:Z200",
        help="Range for basic info tab (default: student!A1:Z200)",
    )
    parser.add_argument(
        "--range-sl-lesson",
        default="'【SL】lesson plan'!A1:M250",
        help="Range for SL lesson plan tab",
    )
    parser.add_argument(
        "--range-hl-lesson",
        default="'lesson plan'!A1:Z200",
        help="Range for HL lesson plan tab (hidden tabs OK if entitled)",
    )
    parser.add_argument(
        "--no-hl-lesson-plan",
        action="store_true",
        help="Skip fetching the 'lesson plan' tab (e.g. SL-only books)",
    )
    args = parser.parse_args()

    out: Path = args.out_dir
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    gws = _gws_argv()
    sid = args.spreadsheet_id
    did = args.document_id

    cmds: list[tuple[list[str], Path]] = [
        (
            gws
            + [
                "sheets",
                "spreadsheets",
                "get",
                "--params",
                json.dumps({"spreadsheetId": sid}),
                "--format",
                "json",
            ],
            out / "_gws_spreadsheet_meta.json",
        ),
        (
            gws
            + [
                "sheets",
                "spreadsheets",
                "values",
                "get",
                "--params",
                json.dumps({"spreadsheetId": sid, "range": args.range_student}),
                "--format",
                "json",
            ],
            # ファイル名は既存サンプル（household_tokura）・README との整合を優先
            out / "_gws_student_A1-Z200_values.json",
        ),
        (
            gws
            + [
                "sheets",
                "spreadsheets",
                "values",
                "get",
                "--params",
                json.dumps({"spreadsheetId": sid, "range": args.range_sl_lesson}),
                "--format",
                "json",
            ],
            out / "_gws_SL_lesson_plan_A1-M250_values.json",
        ),
        (
            gws
            + [
                "docs",
                "documents",
                "get",
                "--params",
                json.dumps({"documentId": did}),
                "--format",
                "json",
            ],
            out / "_gws_doc_teacher_MTG_gemini.json",
        ),
    ]

    if not args.no_hl_lesson_plan:
        cmds.append(
            (
                gws
                + [
                    "sheets",
                    "spreadsheets",
                    "values",
                    "get",
                    "--params",
                    json.dumps({"spreadsheetId": sid, "range": args.range_hl_lesson}),
                    "--format",
                    "json",
                ],
                out / "_gws_HL_lesson_plan_A1-Z200_values.json",
            )
        )

    for argv, path in cmds:
        data = _run_gws_json(argv, ROOT)
        path.write_bytes(data)
        print(f"OK {path} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
