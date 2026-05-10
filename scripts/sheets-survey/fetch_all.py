"""全タブのフルスナップショットを sample-extracts/ に保存する。

入力:
  - SA: config/gen-lang-client-0360012476-457924b0f2ae.json
  - SPREADSHEET_ID: ★新【EB塾】【2026年度】指導モニタリング管理表

出力:
  - docs/sheets-migration/sample-extracts/{nnn}_{title}.json
    各ファイルに values（A1:ZZ200 範囲）と mergedRanges を含む

使い方:
  python scripts/sheets-survey/fetch_all.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

REPO_ROOT = Path(__file__).resolve().parents[2]
SA_PATH = REPO_ROOT / "config" / "gen-lang-client-0360012476-457924b0f2ae.json"
OUT_DIR = REPO_ROOT / "docs" / "sheets-migration" / "sample-extracts"
SPREADSHEET_ID = "1inBUyjKQbFEH1tt-XnauWFKJqRU21F-GQGEzleLJLbA"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
RANGE_TEMPLATE = "{title}!A1:ZZ200"

INVALID_FS = re.compile(r"[\\/:*?\"<>|]")


def safe_name(s: str) -> str:
    return INVALID_FS.sub("_", s).strip()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    creds = service_account.Credentials.from_service_account_file(str(SA_PATH), scopes=SCOPES)
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

    try:
        meta = svc.spreadsheets().get(
            spreadsheetId=SPREADSHEET_ID,
            fields="properties.title,sheets.properties(sheetId,title,index,gridProperties),sheets.merges",
        ).execute()
    except HttpError as e:
        print(f"meta fetch error: {e}", file=sys.stderr)
        return 1

    title = meta["properties"]["title"]
    sheets = meta.get("sheets", [])
    print(f"Fetched meta: {title} ({len(sheets)} sheets)")

    # 各シートの values をまとめて取得
    ranges = [RANGE_TEMPLATE.format(title=s["properties"]["title"]) for s in sheets]
    try:
        batch = svc.spreadsheets().values().batchGet(
            spreadsheetId=SPREADSHEET_ID,
            ranges=ranges,
            valueRenderOption="FORMATTED_VALUE",
            dateTimeRenderOption="FORMATTED_STRING",
        ).execute()
    except HttpError as e:
        print(f"batchGet error: {e}", file=sys.stderr)
        return 1

    value_ranges = {vr["range"].split("!")[0].strip("'"): vr.get("values", []) for vr in batch.get("valueRanges", [])}

    saved = 0
    for s in sheets:
        p = s["properties"]
        idx = p["index"]
        gid = p["sheetId"]
        name = p["title"]
        merges = s.get("merges", [])

        payload = {
            "spreadsheet_id": SPREADSHEET_ID,
            "spreadsheet_title": title,
            "index": idx,
            "gid": gid,
            "title": name,
            "grid_properties": p.get("gridProperties", {}),
            "merged_ranges": merges,
            "values": value_ranges.get(name, []),
        }
        fname = f"{idx:03d}_{safe_name(name)}.json"
        out = OUT_DIR / fname
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        saved += 1
        print(f"  [{idx:>3}] {fname}  rows={len(payload['values'])} merges={len(merges)}")

    print(f"\nSaved {saved} files under: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
