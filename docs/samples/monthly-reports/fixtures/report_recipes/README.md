# レポート生成レシピ（再現・チューニング）

**目的**: データソース・テンプレ・プロンプト周辺のオプションを **1 JSON に固定**し、同じ条件でコマンドを再実行できるようにする。

## 実行

プロジェクトルートで:

```powershell
python scripts/monthly_report_run_recipe.py docs/samples/monthly-reports/fixtures/report_recipes/hirayama_physics_pattern_b_shell.recipe.json
```

チューニング時に **seed のみ試す**:

```powershell
python scripts/monthly_report_run_recipe.py ...\hirayama_physics_pattern_b_shell.recipe.json --seed 12345
```

**ドライラン**（引数のみ表示、`openrouter` は起動しない）:

```powershell
python scripts/monthly_report_run_recipe.py ...\foo.recipe.json --dry-run
```

**ラン記録**（追記 JSON Lines・チューニング比較用）:

```powershell
python scripts/monthly_report_run_recipe.py ...\foo.recipe.json --record docs/samples/monthly-reports/fixtures/report_recipes/run_log.jsonl
```

`run_log.jsonl` は個人環境・キー混入防止のため **既定では gitignore**。必要なら抜粋だけコミットしてください。

## レシピの書き方

- `recipe_version`: 現在は **1**
- **相対パス**はすべて **リポジトリルート**からの POSIX 形式（`\` は使わない）
- **`structure.structure_from_ideal: true`** のとき **`ideal_html` 必須**（十倉 v4 系シェルの再現用）
- **`prompts.scope_reminder`**（任意）：`monthly_report_draft_openrouter.py` に **`--bundle-scope-reminder`** として渡す。複数生徒が同一 Doc の MTG に混在するときなど、モデル入力の「対象レポートのスコープ」に挿入される（正本規約は `monthly_pattern_b_content.template.md` の該当節）
- 再現性の限界は `monthly_report_draft_openrouter.py` の docstring と同様（モデル側が `seed` を無視し得る等）

チューニングの順序の一例:

1. `sources.preset` / `generation.max_bundle_chars` で **欠落・切り詰め**がないか
2. **`temperature`** を 0.05〜0.1 で固定、`seed` を振って **出力差分の許容幅**を把握
3. **`ideal_html` / `structure_from_ideal`** でレイアウトを固定してから文言・表を推敲
