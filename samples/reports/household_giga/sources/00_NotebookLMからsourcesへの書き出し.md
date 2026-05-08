---
schema_version: 1
kind: procedure
household_slug: household_giga
title: "NotebookLM から sources への書き出し"
language: ja
---

1) Cursor で MCP「source_get_content」を実行し、source_id を指定する（例: notebooklm_source_ids_儀賀.md 参照）。

2) 返ってきた JSON 全体を、このフォルダに _nl_response.json などの名前で保存する。
   （content フィールドに本文が入っています）

3) プロジェクトルートで次を実行し、Markdown（YAML フロントマター付き）を生成する。

   python scripts/notebooklm_json_to_txt.py samples/reports/household_giga/sources/_nl_response.json samples/reports/household_giga/sources/01_教師MTG_20260225_全文.md

   （代替）CLI `nlm content source <source_id> -o body.txt` で本文だけ取り出す場合、Windows では `PYTHONUTF8=1` を付けないと特殊文字で書き込みに失敗することがあります。取り出した本文から JSON を組み `notebooklm_json_to_txt.py` に渡してください。

4) 文字化け・縦タブ（Unicode U+000B）はスクリプト内で改行に近づけています。Meet のノイズ（Roboto リンク等）は必要に応じて手で削除してください。

5) Google Drive フォルダだけをソースにした場合、本文が HTML のログイン案内になることがあります。その場合はスプレッドシートを Drive から直接ソース追加するか、シートをエクスポートした .md を sources に置いてください。
