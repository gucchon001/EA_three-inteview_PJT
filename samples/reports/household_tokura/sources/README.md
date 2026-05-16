# sources（household_tokura）

- `00_260319_時系列まとめ_NotebookLM.md` … NotebookLM の時系列ソースを `nlm content source` → JSON → `notebooklm_json_to_txt.py` で生成。
- `03_学習計画表_プレースホルダー.md` … 実シートのスナップショットに差し替え。
- 01・02 相当の個別ソースは NotebookLM から `source_get_content` で取り込み、このフォルダに保存。

## gws 一次取得（2026-05-10）

スプレッドシート `1d0_0kj2C-kjgikWRGsorTw8wADYIk0Z4j59AwFDzaDo`（タブ `student`・gid 962254713）と、教師 MTG Doc `1KbH40l3U3oXkXTLrlKAfnIZUmIr5_OcrITz1L_QS-fs` を **UTF-8 JSON** で保存。Windows で PowerShell の `Out-File` のみでは日本語が化けることがあるため、再取得は `python scripts/_fetch_tokura_gws_once.py` を使用。

| ファイル | 内容 |
|----------|------|
| `_gws_spreadsheet_meta.json` | `spreadsheets.get`（全シート一覧・構造） |
| `_gws_student_A1-Z200_values.json` | `values.get` … `student!A1:Z200` |
| `_gws_doc_teacher_MTG_gemini.json` | `documents.get`（Gemini 議事録） |
| `_gws_SL_lesson_plan_A1-M250_values.json` | `values.get` … `'【SL】lesson plan'!A1:M250` |
| `_gws_HL_lesson_plan_A1-Z200_values.json` | `values.get` … `'lesson plan'!A1:Z200`（HL 側・必要に応じて参照） |
| `_gws_doc_teacher_MTG_gemini.txt` | 上記 JSON から `scripts/gws_doc_json_to_plaintext.py` で抽出したプレーンテキスト |

月次レポート初版: [docs/samples/monthly-reports/monthly_2026-04_tokura_report.md](../../../../docs/samples/monthly-reports/monthly_2026-04_tokura_report.md)
