# sources（household_hirabayashi_economics）

平林 礼さまの **Economics SL** 用。学習計画表ブック・教師 MTG は Physics 用フォルダ（`samples/reports/household_hirabayashi/sources`）とは **別ファイル** を指す。

| 種類 | URL / ID |
|------|-----------|
| 学習計画表（Economics SL） | [スプレッドシート（gid 例: Economics タブ）](https://docs.google.com/spreadsheets/d/1hNXIgBDqB9qJnrgVqzfx9CamyEXVIJLQE0cHNfYDJEs/edit?gid=1761554689) — ID **`1hNXIgBDqB9qJnrgVqzfx9CamyEXVIJLQE0cHNfYDJEs`** |
| 教師 MTG Doc（Economics／Tehee Lee） | [教師 MTG Doc](https://docs.google.com/document/d/1bY06bEO_GKbDKVaX2WP-9FFT8HncWetw2v5ChArjABE/edit) — ID **`1bY06bEO_GKbDKVaX2WP-9FFT8HncWetw2v5ChArjABE`** |

## 注意（複数生徒が同一 MTG に出る場合）

Economics の教師メモに **複数の生徒**が同一 Doc で登場することがある。自動生成では `monthly_pattern_b_content.template.md` の **「複数の生徒が同一 MTG／同一 Doc に登場するとき」**に加え、レシピの **`prompts.scope_reminder`**（`--bundle-scope-reminder`）で Economics・対象氏名を明示する。**Physics 用ソースとファイルを混在させないこと。**

## gws で再取得する（プロジェクトルート）

Economics のブックは SL 進捗タブ名が **`lesson plan`**（`【SL】lesson plan` ではない）。他ブックと違うときは `_gws_spreadsheet_meta.json` のシート名で確認する。

```powershell
python scripts/fetch_monthly_gws_sources.py `
  --spreadsheet-id "1hNXIgBDqB9qJnrgVqzfx9CamyEXVIJLQE0cHNfYDJEs" `
  --document-id "1bY06bEO_GKbDKVaX2WP-9FFT8HncWetw2v5ChArjABE" `
  --out-dir samples/reports/household_hirabayashi_economics/sources `
  --no-hl-lesson-plan `
  --range-sl-lesson "'lesson plan'!A1:M250"
```

1. MTG をプレーン化:

```powershell
python scripts/gws_doc_json_to_plaintext.py `
  samples/reports/household_hirabayashi_economics/sources/_gws_doc_teacher_MTG_gemini.json `
  samples/reports/household_hirabayashi_economics/sources/_gws_doc_teacher_MTG_gemini.txt
```

## Pattern B HTML（レシピ・北極星パイプライン）

ソース取得後:

```powershell
python scripts/monthly_report_run_recipe.py docs/samples/monthly-reports/fixtures/report_recipes/hirayama_economics_pattern_b_shell.recipe.json
```

サンプル登録キー **`hirayama_economics`**（マニフェスト・エディタ・Vercel）は HTML 確定後に追加する運用でもよい。
