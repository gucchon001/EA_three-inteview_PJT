# tokura 世帯｜一次ソース × tokura_v2 反映チェック（プレースホルダ済みドラフト）

**調査作成日**: 2026-05-13  
**対象月**: 2026年4月  
**照合レポート**: docs/samples/monthly-reports/monthly_2026-04_tokura_v2_report.html

## 一次ソース一覧

| # | パス | 役割 |
|---|------|------|
| S1 | samples/reports/household_tokura/sources/_gws_student_A1-Z200_values.json | student シート |
| S2 | samples/reports/household_tokura/sources/_gws_SL_lesson_plan_A1-M250_values.json | 【SL】lesson plan |
| S3 | samples/reports/household_tokura/sources/_gws_doc_teacher_MTG_gemini.txt | 教師 MTG（プレーン） |
| S4 | samples/reports/household_tokura/sources/_gws_spreadsheet_meta.json | スプレッドシートメタ |

## 差分表

| # | レポート位置 | 項目 | ソース | 可否 | 反映 | メモ |
|---|-------------|------|--------|------|------|------|

（ここへ行を追加。手順・ラベル定義は source-coverage-prompt.md を参照）

## 優先アクション

| 症状 | 推奨 |
|------|------|
## 実行用プロンプト（このチャットに貼り、@ で S1/S2/S3 とレポートを添付）

`
あなたは EA_three-inteview_PJT の月次 Pattern B の品質レビュアです。
次のパスを読み、source-coverage-prompt.md のラベル定義に従い差分表を完成させ、上記「差分表」以下を埋めた完全版 Markdown を出力してください。

- TARGET_MONTH: 2026-04 / 2026年4月
- REPORT: docs/samples/monthly-reports/monthly_2026-04_tokura_v2_report.html
- S1: samples/reports/household_tokura/sources/_gws_student_A1-Z200_values.json
- S2: samples/reports/household_tokura/sources/_gws_SL_lesson_plan_A1-M250_values.json
- S3: samples/reports/household_tokura/sources/_gws_doc_teacher_MTG_gemini.txt
`

---
**正本プロンプト**:
.cursor/skills/monthly-report-new-household-gws/references/source-coverage-prompt.md
