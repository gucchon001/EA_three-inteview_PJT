---
name: monthly-report-new-household-gws
description: "EA_three-inteview_PJT。月次 Pattern B を新規ご家庭向けに構築する。一次ソースは gws で学習計画表（student + 【SL】lesson plan、必要なら lesson plan）と教師 MTG Doc。再現レシピ(recipe)→OpenRouter→ドラフト MD/HTML→manifest→全文エディタ。最終はブラウザ完結自動生成への北極星に接続——docs/monthly-report-workshop/AUTOMATION_NORTH_STAR.md。Triggers: 新規家庭 月次レポート、gws 月次、学習計画表、教師MTG、全文エディタ、reports-manifest、recipe、Pattern B 新規"
metadata:
  last_verified: "2026-05-14"
---

# 月次新規レポート（gws 一次ソース + 全文エディタ）

**配置**: `.cursor/skills/monthly-report-new-household-gws/`  
**戦略・アーキ（ぶれない方針）**: [AUTOMATION_NORTH_STAR.md](../../../docs/monthly-report-workshop/AUTOMATION_NORTH_STAR.md)（静的 POC と将来のレポート工房のゴール／非交渉）  
**規約の正本**: [docs/samples/monthly-reports/monthly_pattern_b_content.template.md](docs/samples/monthly-reports/monthly_pattern_b_content.template.md) と [monthly_pattern_b_template.html](docs/samples/monthly-reports/monthly_pattern_b_template.html)。

## 既存スキルとの分担

| 用途 | スキル |
|------|--------|
| **本ワークフロー**（gws 直取得・新規世帯の月次） | **本スキル** |
| Pattern A〜D、NotebookLM を正とする抽出・家庭向け文体の詳細 | **monthly-report-notebooklm-patterns**（[family-facing-tone.md](../monthly-report-notebooklm-patterns/references/family-facing-tone.md)・★固定文案） |
| gws CLI・Sheets/Docs 取得の落とし穴 | **gws-sheets**、**gws-docs-to-local**、**gws-params-encoding**（グローバル） |

## いつ使うか

- 新しいご家庭の **月次 Pattern B** を初めて切るとき
- 一次情報が **学習計画表（複数タブ）+ 教師 MTG（Google Doc）** のとき
- ドラフトを **全文エディタ**で推敲・送付前チェックするとき

## 手順（要約）

詳細は **references/workflow.md**、データの割り当ては **references/data-contract.md**、エディタ URL と manifest は **references/editor.md**。

1. **入力をそろえる**: `spreadsheetId`、教師 MTG の `documentId`、世帯 `slug`、対象 `YYYY-MM`、（任意）シート名の上書き。
2. **gws で取得**: `python scripts/fetch_monthly_gws_sources.py …` → `samples/reports/household_<slug>/sources/` に JSON（UTF-8）。Doc は `python scripts/gws_doc_json_to_plaintext.py` で `.txt` も生成推奨。
3. **レポート本文**: テンプレに沿って MD／HTML。**家庭向けの禁止語・01 転記・担当ラベル**は [family-facing-tone.md](../monthly-report-notebooklm-patterns/references/family-facing-tone.md) と `monthly_pattern_b_content.template.md` の「ご家庭配布での表記ルール」を併読。**02 は mood 3 行**。03 の長い単元は `.unit-main` / `.unit-subtopics` を使う。  
   （任意）OpenRouter でドラフトする場合は `--source-preset pattern_b_gws_sl`（HL タブ未取得）または `pattern_b_gws_sl_hl`（HL あり）。別世帯でファイル規約だけ違うときは `scripts/monthly_report_source_presets.json` を複製して `--presets-json` で指すか、`--glob` を複数指定。`--list-source-presets` で名前確認。
4. **マニフェスト**: [docs/samples/monthly-reports/reports-manifest.json](docs/samples/monthly-reports/reports-manifest.json) の `samples` にキーを追加し、**`revision` を更新**。[src/reports/templates/monthly-reports/reports-manifest.json](src/reports/templates/monthly-reports/reports-manifest.json) と同期。
5. **公開パス**: [vercel.json](vercel.json) に新規 `*_report.html` 用ルートを追加（必要時）。目次 [monthly-reports/index.html](src/reports/templates/monthly-reports/index.html) を更新。デプロイ時は `node scripts/sync_monthly_reports_to_vercel.mjs` を運用に合わせ実行。
6. **全文エディタ**: `python scripts/serve_project.py` 後、`http://127.0.0.1:<port>/docs/samples/monthly-reports/tools/monthly_report_full_editor.html?sample=<slug>` で開く（下書きがあると上書きされない → **下書き削除**またはサンプルボタン）。

## 自動生成への道筋（チューニング）

現在の **`*.recipe.json` + `monthly_report_run_recipe.py`** は、将来的な工房の **ジョブパラメータ／再現バンドル** に相当させる。**North Star はブラウザ上で完結した自動生成**。レイアウトは **ideal+structure-from-ideal または Jinja+ペイロード** で固定すること（詳細は [AUTOMATION_NORTH_STAR.md](../../../docs/monthly-report-workshop/AUTOMATION_NORTH_STAR.md)）。

## 参照

- [references/workflow.md](references/workflow.md)
- [references/data-contract.md](references/data-contract.md)
- [references/editor.md](references/editor.md)
- [references/source-coverage-prompt.md](references/source-coverage-prompt.md)（一次ソース読み取り可否 × 本文反映の汎用プロンプト／再実行テンプレート）

## Troubleshooting

- **PowerShell だけで gws をファイルに保存すると JSON が化ける** → 必ず本リポの取得スクリプト（子プロセスでバイナリ stdout）を使う。
- **エディタでサンプルが読めない** → `file://` 禁止。`serve_project.py` の http URL を使う。
- **Gemini メモの人名誤記** → 音声・原記録と照合してから配布。
