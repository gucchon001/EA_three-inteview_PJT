# ワークフロー詳細: NotebookLM → sources → Pattern A〜D

パスは **本リポジトリのルート** を基準とする。

## フェーズ 0: スコープ

- **家庭フォルダ**: `samples/reports/<household>/`（例: `household_giga`, `demo_household_takafuji`）
- **3ソース**: 01 教師MTG、02 家庭面談・提案、03 学習計画表（**数値の正は 03**）
- **04**: レビュー用メール（根拠外）

## フェーズ 1: NotebookLM から本文取得

1. NotebookLM 上で対象ノートの **`source_id`** を確認（家庭用レジストリ: `notebooklm_source_ids_*.md` があれば利用）。
2. MCP **`source_get_content`**（またはホストが提供する同等ツール）で JSON を取得。
3. 応答を `sources/_nl_response.json` に保存（再現用）。

**品質**: `content` が HTML ログイン案内だけの場合は、Drive 直リンクやスプレッドシートをソースにし直す（`docs/project/月次レポート生成ワークフロー.md` 参照）。

## フェーズ 2: Markdown 化

プロジェクトルートで:

```text
python scripts/notebooklm_json_to_txt.py samples/reports/<household>/sources/_nl_response.json samples/reports/<household>/sources/<出力ファイル名>.md
```

- **`.md` 出力**: JSON のメタ＋ `schema_version` が YAML フロントマターに付く。
- 手編集で **YAML** を補完（`household_slug`, `source_slot`, `notebooklm_source_id` 等）。

## フェーズ 3: sources そろい・ゲート

| ゲート | 確認 |
|--------|------|
| G1 | 01・02・03 が揃い、日付・スロットがレポート月と整合 |
| G2 | KPI・目標・不足コマが **03** と一致（01 と矛盾する数値は 03 優先） |
| G3 | 本文の根拠がメール本文ではなく **01〜03** になっている |

## フェーズ 4: Pattern A〜D HTML

同一 `sources/` を参照するパスで更新する。

| ファイル | 役割 |
|----------|------|
| `pattern_a_responsive.html` | レスポンシブ・Chart.js・iframe レビュー |
| `pattern_b.html` | A4・印刷向け |
| `pattern_c_simple.html` | 軽量・メール向け |
| `pattern_d.html` | ダッシュボード UI（リアルタイム数値はデモ明示） |

各ファイルに含める（儀賀家サンプルと同水準）:

- 冒頭バナー（sources 01〜03・`serve_project`）
- **主眼**（03・02 中心、01 は時系列）
- KPI・本文・表（sources と一致）
- `#review-mail`（04、根拠外）
- `#factcheck`
- `#graph-requirements`
- `#references`（相対パス・NotebookLM URL・スプレッドシートは 03 に合わせる）

## フェーズ 5: 一覧と確認

- `samples/reports/index.html` に **該当家庭 × A〜D** のリンクがあること。
- `python scripts/serve_project.py` のあと、各 HTML と `sources/*.md` のリンクを開いて確認。

## ドキュメント月次サンプル（Pattern B・ご家庭向け HTML）

`samples/reports/` の Pattern A〜D とは別系統で、**`docs/samples/monthly-reports/`** に **Pattern B 月次規約**（`monthly_pattern_b_content.template.md`・`monthly_pattern_b_template.html`）および **適合済み配布サンプル**（`monthly_YYYY-MM_*_report.*`、例：鈴木・高藤分）がある。教師 MTG の文字起こしと学習計画表から HTML を書くときは **まず規約（MD → HTML を複製したテンプレ）を正とし**、ファイル名だけを短絡しない。

- **03（ご家庭向け月次の「授業内容」）** の表下 **理解度（★）の目安**：`family-facing-tone.md` の「03 授業内容 — 理解度（★）の目安」または `monthly_pattern_b_content.template.md` の **03 授業内容** 節（**固定文案・改変禁止**）。
- **文体・notebook_query**：`family-facing-tone.md` 全体。
- **全文エディタ**（微修正）：`tools/monthly_report_full_editor.html`（`localStorage` キーはエディタファイル内の `STORAGE_KEY` を正とする）。

同期・本番反映：`node scripts/sync_monthly_reports_to_vercel.mjs`。

## アーティファクト一覧（典型）

```
samples/reports/<household>/
  pattern_a_responsive.html
  pattern_b.html
  pattern_c_simple.html
  pattern_d.html
  sources/
    _nl_response.json          # 取得再現用（任意）
    01_*.md
    02_*.md
    03_*.md
    04_参照メール_レビュー用.md
    notebooklm_source_ids_*.md  # 任意
```
