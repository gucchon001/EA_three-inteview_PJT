# ワークフロー（月次新規・gws ベース）

## 前提チェックリスト

| 項目 | メモ |
|------|------|
| 学習計画表の Spreadsheet ID | URL の `/d/` と次の `/` の間 |
| 教師 MTG Doc の Document ID | `/document/d/<id>/` の `<id>`（`?tab=` は含めない） |
| 世帯 `slug` | フォルダ名 `household_<slug>` に使う（英小文字・アンダースコア推奨） |
| 対象年月 | `YYYY-MM`（ファイル名 `monthly_YYYY-MM_<slug>_report.*`） |
| gws 認証 | `gws auth login -s sheets` と `gws auth login -s docs` |

進め方の上位方針（静的 POC と将来のブラウザ工房・非交渉事項）は [AUTOMATION_NORTH_STAR.md](../../../docs/monthly-report-workshop/AUTOMATION_NORTH_STAR.md) を必ず読む。

## ステップ 1 — メタと値の取得

プロジェクトルートで:

```powershell
python scripts/fetch_monthly_gws_sources.py `
  --spreadsheet-id "<SPREADSHEET_ID>" `
  --document-id "<DOC_ID>" `
  --out-dir samples/reports/household_<slug>/sources
```

生成例:

- `_gws_spreadsheet_meta.json` — `spreadsheets.get`（gid → シート名の確認用）
- `_gws_student_A1-Z200_values.json`
- `_gws_SL_lesson_plan_A1-M250_values.json`
- `_gws_HL_lesson_plan_A1-Z200_values.json`（ブックに `lesson plan` がある場合）
- `_gws_doc_teacher_MTG_gemini.json`

Doc を読みやすくする:

```powershell
python scripts/gws_doc_json_to_plaintext.py `
  samples/reports/household_<slug>/sources/_gws_doc_teacher_MTG_gemini.json `
  samples/reports/household_<slug>/sources/_gws_doc_teacher_MTG_gemini.txt
```

シート名がプロジェクト既定と違う場合は `fetch_monthly_gws_sources.py` の `--range-student` 等で上書き（`--help` 参照）。

一次ソースのみを束ねて OpenRouter で Markdown/HTML ドラフトする場合は `scripts/monthly_report_draft_openrouter.py` の `--source-preset pattern_b_gws_sl`（HL タブも取得したときは `pattern_b_gws_sl_hl`）。プリセット一覧は `--list-source-presets`。世帯特有のファイル名だけ変えるなら `--presets-json` で別 JSON を指すか `--glob` を複数指定。

**再現性・チューニング**: `docs/samples/monthly-reports/fixtures/report_recipes/*.recipe.json` にパラメータを固定し、`python scripts/monthly_report_run_recipe.py <recipe>` で同一条件を再実行する（`fixtures/report_recipes/README.md` 参照）。

## ステップ 2 — ドラフト作成

1. [monthly_pattern_b_content.template.md](../../../docs/samples/monthly-reports/monthly_pattern_b_content.template.md) を思考の正とする。
2. `docs/samples/monthly-reports/monthly_pattern_b_template.html` または既存事例 HTML を複製し、`monthly_YYYY-MM_<slug>_report.md` / `.html` を編集。
3. **01** は `student`、**03・05・07 の事実**は lesson plan 系、**02・04 の文章**は MTG（＋必要なら計画表メモ）を根拠にする。

### ステップ 2b —（推奨）形固定パイプライン：ペイロード → Jinja

家庭配布 DOM を LLM で丸ごと生成させず、**Jinja シェル + JSON ペイロード**で形を担保する場合:

- テンプレ: [`docs/samples/monthly-reports/templates/pattern_b_compact_01_05.html.j2`](../../../docs/samples/monthly-reports/templates/pattern_b_compact_01_05.html.j2)（01〜05・tokura_v2 型 compact）
- スキーマ目安: [`fixtures/payloads/schema.pattern_b_compact_01_05.json`](../../../docs/samples/monthly-reports/fixtures/payloads/schema.pattern_b_compact_01_05.json)
- 例ペイロード: [`fixtures/payloads/tokura_2026-04_v2_shape.json`](../../../docs/samples/monthly-reports/fixtures/payloads/tokura_2026-04_v2_shape.json)

```powershell
pip install Jinja2
python scripts/render_monthly_report_payload.py `
  --payload docs/samples/monthly-reports/fixtures/payloads/tokura_2026-04_v2_shape.json `
  --output docs/samples/monthly-reports/_tmp_preview.html
```

LLM は **ペイロード JSON の文字列だけ**生成し、サーバまたは CI で上記スクリプトと同等のレンダをかける運用を想定。

## ステップ 2.5 —（任意）一次ソース × 本文のギャップ表

配布前またはレビュー時に、**読み取れるのに未反映**と**推定で書いた**を区別したい場合、[source-coverage-prompt.md](source-coverage-prompt.md) のプレースホルダを埋め、コピペ用プロンプトでエージェント実行する。出力は `docs/samples/monthly-reports/SOURCE_COVERAGE_<slug>_…md` などに保存。

## ステップ 3 — manifest・デプロイ・エディタ

[editor.md](editor.md) のチェックリストに従う。

## ステップ 4 — 品質ゲート（最低限）

- [ ] 03 直下の **理解度（★）の目安** が規約どおり原文か
- [ ] 02 mood 表が **学習進捗・学習意欲・宿題の提出**の **3 行**になっているか（`monthly_pattern_b_content.template.md` と整合）
- [ ] 「教師 MTG」「Gemini メモ」「担当CA」「シート俗称の直書き」が家庭向け本文・表ラベルに無いか
- [ ] 01 の IB **目標／現状**が計画表と列対応している（入力ミスでの同一値転記でないこと）
- [ ] 07・05 に**仮の単一授業日**のみを家庭向けに書いていないか
- [ ] 数値・氏名・教師名が一次ソースと矛盾していないか
- [ ] （必要時）[source-coverage-prompt.md](source-coverage-prompt.md) で **読取-A/B/C** と反映状況を一覧化した
