#!/usr/bin/env python3
"""
NotebookLM の source_list_drive の JSON から、Google ドキュメント／スプレッドシートの URL を列挙する。

使い方:
  1. MCP で source_list_drive(notebook_id=...) を実行し、結果をファイルに保存する。
  2) 次を実行する。

     python scripts/notebooklm_drive_urls.py path/to/source_list_drive.json

  標準入力でも可:

     type source_list_drive.json | python scripts/notebooklm_drive_urls.py -

出力: TSV（title, type, url）を標準出力。レポート「参照一覧」に貼り付け可能。

注意:
  - NotebookLM に「URL のみ」で追加した Drive フォルダ等は、API が drive_doc_id を返さない場合があり抽出できない。
  - ネイティブの「Drive から追加」した Docs / Sheets は drive_doc_id から URL を復元できる。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def doc_url(doc_id: str) -> str:
    return f"https://docs.google.com/document/d/{doc_id}/edit"


def sheets_url(doc_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{doc_id}/edit"


def slides_url(doc_id: str) -> str:
    return f"https://docs.google.com/presentation/d/{doc_id}/edit"


def url_for_type(drive_type: str, doc_id: str) -> str:
    t = (drive_type or "").lower()
    if t == "google_docs":
        return doc_url(doc_id)
    if t in ("google_sheets", "sheets"):
        return sheets_url(doc_id)
    if t in ("google_slides", "slides"):
        return slides_url(doc_id)
    return f"(unknown type {drive_type}) https://drive.google.com/open?id={doc_id}"


def main() -> None:
    raw = sys.argv[1] if len(sys.argv) > 1 else None
    if raw in (None, "-"):
        data = json.load(sys.stdin)
    else:
        data = json.loads(Path(raw).read_text(encoding="utf-8"))

    rows: list[tuple[str, str, str]] = []
    for item in data.get("drive_sources") or []:
        did = item.get("drive_doc_id")
        title = (item.get("title") or "").replace("\t", " ")
        dtype = item.get("type") or ""
        if not did:
            continue
        rows.append((title, dtype, url_for_type(dtype, did)))

    print("title\ttype\turl")
    for r in rows:
        print("\t".join(r))

    if not rows:
        print(
            "# drive_sources に drive_doc_id がありません。"
            " source_list_drive の JSON か、ノートに Drive 連携ソースがあるか確認してください。",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
