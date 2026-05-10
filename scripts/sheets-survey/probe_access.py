"""SA で対象スプレッドシートにアクセスできるか確認するプローブ。

使い方:
  python scripts/sheets-survey/probe_access.py

成功時: シート一覧（タイトル + gid）を stdout に出力
失敗時: エラーメッセージと SA メールを表示（共有を依頼するため）
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

REPO_ROOT = Path(__file__).resolve().parents[2]
SA_PATH = REPO_ROOT / "config" / "gen-lang-client-0360012476-457924b0f2ae.json"
SPREADSHEET_ID = "1inBUyjKQbFEH1tt-XnauWFKJqRU21F-GQGEzleLJLbA"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def main() -> int:
    if not SA_PATH.exists():
        print(f"SA file not found: {SA_PATH}", file=sys.stderr)
        return 2

    sa_email = json.loads(SA_PATH.read_text(encoding="utf-8")).get("client_email", "?")
    print(f"SA email: {sa_email}")
    print(f"Spreadsheet: {SPREADSHEET_ID}")

    creds = service_account.Credentials.from_service_account_file(str(SA_PATH), scopes=SCOPES)
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

    try:
        meta = svc.spreadsheets().get(
            spreadsheetId=SPREADSHEET_ID,
            fields="properties.title,sheets.properties(sheetId,title,index,gridProperties)",
        ).execute()
    except HttpError as e:
        print(f"\nAccess error ({e.resp.status}): {e}", file=sys.stderr)
        print(
            f"\n→ {sa_email} を対象スプレッドシートに「閲覧者」として共有してください。",
            file=sys.stderr,
        )
        return 1

    title = meta.get("properties", {}).get("title", "?")
    sheets = meta.get("sheets", [])
    print(f"\nOK: {title} ({len(sheets)} sheets)")
    for s in sheets:
        p = s["properties"]
        rows = p.get("gridProperties", {}).get("rowCount", "?")
        cols = p.get("gridProperties", {}).get("columnCount", "?")
        print(f"  [{p['index']:>3}] gid={p['sheetId']:<12} {rows:>4}x{cols:<3}  {p['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
