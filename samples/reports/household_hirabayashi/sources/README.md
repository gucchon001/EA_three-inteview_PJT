# sources（household_hirabayashi）

平林 礼さま（生徒番号 **67982**）・Physics SL。<https://docs.google.com/spreadsheets/d/1XR6pdZc23fijgYmjKZ0gcqU57iHsmRdfzmZHVQYGyNg/> と教師 MTG Doc。<https://docs.google.com/document/d/19MrWixGP5bpvcLY2spSn_yKen9WSgN4g1by-zjERVA4/edit>

このブックの SL 進捗タブは **`lesson plan`**（`【SL】lesson plan` ではない）。HL 向け別タブの取得はしない（`--no-hl-lesson-plan`）。

## gws で再取得する（プロジェクトルート）

```powershell
python scripts/fetch_monthly_gws_sources.py `
  --spreadsheet-id "1XR6pdZc23fijgYmjKZ0gcqU57iHsmRdfzmZHVQYGyNg" `
  --document-id "19MrWixGP5bpvcLY2spSn_yKen9WSgN4g1by-zjERVA4" `
  --out-dir samples/reports/household_hirabayashi/sources `
  --no-hl-lesson-plan `
  --range-sl-lesson "'lesson plan'!A1:M250"
```

続けて MTG をプレーン化:

```powershell
python scripts/gws_doc_json_to_plaintext.py `
  samples/reports/household_hirabayashi/sources/_gws_doc_teacher_MTG_gemini.json `
  samples/reports/household_hirabayashi/sources/_gws_doc_teacher_MTG_gemini.txt
```

スプレッドシート構成（gid 参考）:

| タイトル | gid |
|-----------|-----|
| student | 1718767612 |
| lesson plan | 704050348 |
| （非表示）トピック一覧 | 1727797645 |
| video | 661355791 |

| ファイル | 内容 |
|----------|------|
| `_gws_spreadsheet_meta.json` | `spreadsheets.get` |
| `_gws_student_A1-Z200_values.json` | `student!A1:Z200` |
| `_gws_SL_lesson_plan_A1-M250_values.json` | **`lesson plan`!A1:M250** |
| `_gws_doc_teacher_MTG_gemini.json` | 教師 MTG（Gemini メモ Doc） |
| `_gws_doc_teacher_MTG_gemini.txt` | 上記から抽出した UTF-8 テキスト |

## 全文エディタ（公開サンプル）

Physics 進捗の閲覧用 HTML は **`hirayama_physics`**（表示名 「平山（Physics）」）としてマニフェスト登録済みです。

ローカル: `docs/samples/monthly-reports/tools/monthly_report_full_editor.html?sample=hirayama_physics`

Economics は **別ブック・別 Doc** で `samples/reports/household_hirabayashi_economics/sources` を用意し、`hirayama_economics_pattern_b_shell.recipe.json` と **`prompts.scope_reminder`**（複数生徒 MTG の切り分け）で生成する。

## OpenRouter で月次ドラフト（任意）

`pattern_b_gws_sl` で student・SL の JSON・MTG・meta が束ねられます。

**HTML（エディタ用・十倉 v3/v4 と同じレイアウトパイプライン）**: 理想 HTML を語感参考にし、`--structure-from-ideal` で DOM／CSS を揃えます。

```powershell
python scripts/monthly_report_draft_openrouter.py `
  --sources-dir samples/reports/household_hirabayashi/sources `
  --source-preset pattern_b_gws_sl `
  --ideal-html docs/samples/monthly-reports/fixtures/tokura_2026-04_user_ideal.html `
  --structure-from-ideal `
  --max-bundle-chars 400000 `
  --artifact html `
  --temperature 0.1 `
  --seed 6798201 `
  --output docs/samples/monthly-reports/monthly_2026-04_hirayama_physics_report.html
```

同等の実行を **レシピ JSON で固定**する場合:

```powershell
python scripts/monthly_report_run_recipe.py docs/samples/monthly-reports/fixtures/report_recipes/hirayama_physics_pattern_b_shell.recipe.json
```

Markdown のみほしい場合は `--artifact md`。ideal／構造オプションは省略可ですが、この場合 HTML の見た目は十倉系とずれやすくなります。

```powershell
python scripts/monthly_report_draft_openrouter.py `
  --sources-dir samples/reports/household_hirabayashi/sources `
  --source-preset pattern_b_gws_sl `
  --artifact md `
  --output docs/samples/monthly-reports/_tmp_monthly_2026-04_hirabayashi_draft.md
```
