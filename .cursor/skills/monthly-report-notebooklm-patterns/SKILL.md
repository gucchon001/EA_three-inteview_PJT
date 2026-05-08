---
name: monthly-report-notebooklm-patterns
description: "EA_three-inteview_PJT 専用。NotebookLM MCP から一次情報を取り samples/reports の sources と Pattern A〜D HTML を整合させる。source_get_content、household_giga、Pattern B C D、factcheck。Triggers: NotebookLM レポート、パターンやり直し、MCP から HTML、家庭レポート"
metadata:
  last_verified: "2026-05-07"
---

# Monthly Report: NotebookLM → Pattern A〜D（プロジェクトスキル）

**配置**: 本リポジトリの `.cursor/skills/monthly-report-notebooklm-patterns/`（`samples/reports/`・`scripts/`・`docs/project/` を正とする。）

NotebookLM のソース本文を取得し `sources/` に格納したうえで、Pattern A〜D の HTML を一次情報と照合しながら更新する。詳細は **references/workflow-full.md**、グローバルスキルとの分担は **references/related-skills.md**。

**ご家庭向け月次（Pattern B × 月次案ドラフト等）**: 第三者・観察者調にならない文体と `notebook_query` 追記文は **references/family-facing-tone.md** を正とする。

**世帯別 Pattern A〜D 以外の「月次サンプル（鈴木・高藤）」**: 正本は `docs/samples/monthly-reports/`。**バージョン**は `versions/v1`・`v2`・`v3` に凍結（上書きしない）。現行 HTML は **v3.2**（05 の **`calendar_buckets_10` をトピック別**、**03（授業日）**→トピック割当、`DATA_CONTRACT_05_学習の進捗.md`）。レイアウト②③⑤・レビュー対応は **USER_REVIEW_月次レポート_2名分.md** 等。Vercel 同期は `node scripts/sync_monthly_reports_to_vercel.mjs`（`*_report.html` + `versions/` + `monthly-reports-index.html` → `index.html`）。

**03 授業内容 — 理解度（★）の目安（配布 HTML／MD 共通の固定文案）**: 表の直下に **改変せず** 次を載せる。`★☆☆＝基礎内容の定着が必要`／`★★☆＝基礎問題が解けるが応用問題に対応できない`／`★★★＝基礎に加え応用問題にも対応できている`／`※いずれも授業内の観察と演習の様子に基づきます。` 正本は **`docs/samples/monthly-reports/monthly_pattern_b_content.template.md`** の **03 授業内容** 節。

## いつ使うか

- 本プロジェクトで月次レポートを NotebookLM を正として取り直すとき
- `source_get_content` で JSON を得て `sources/*.md` に落とすとき
- Pattern A〜D を同じ家庭データで揃えるとき
- **`docs/samples/monthly-reports/` の月次 HTML／MD** を文字起こし・学習計画表から整えるとき（**03** の★目安は **固定文案**）

## 手順（エージェント）

1. 対象の `notebook_id`・`source_id` を確認（`notebooklm_source_ids_*.md` 等）。MCP は **グローバルスキル notebooklm-mcp** に従う。
2. MCP で本文を取得し JSON を `samples/reports/<household>/sources/_nl_response.json` に保存。
3. リポジトリルートで `python scripts/notebooklm_json_to_txt.py` を **出力 `.md`** で実行。
4. 各 01〜04 の YAML を整備。
5. `samples/reports/<household>/` の pattern_a〜d の HTML を sources と突合（**03 が数値の正**）。`#factcheck`・`#graph-requirements`・`#references`・`#review-mail` を揃える。
6. **`docs/samples/monthly-reports/` でご家庭向け月次（Pattern B・鈴木／高藤系）を生成・更新する場合**：`monthly_pattern_b_content.template.md` の **03 授業内容** と `references/family-facing-tone.md` の **03 授業内容 — 理解度（★）の目安**に従い、表下の固定文案を**原文どおり**入れる。必要なら `node scripts/sync_monthly_reports_to_vercel.mjs`。
7. `samples/reports/index.html` を確認。
8. `python scripts/serve_project.py` でリンク確認。

## 関連スキル

| 役割 | 参照 |
|------|------|
| MCP 接続・ツール | **notebooklm-mcp**（グローバル） |
| スキル新規・改修 | **skill-builder** / **skill-growing**（グローバル） |

## Troubleshooting

### エラー: MCP で取得できない・401

**原因**: 認証切れ、ID 誤り、MCP 未再起動。

**対処**: notebooklm-mcp の手順（`nlm login` 等）。

### エラー: 日本語が文字化け

**原因**: charset 未指定の静的配信。

**対処**: `scripts/serve_project.py` を使う。UTF-8 で保存。

### エラー: Pattern 間で数値が違う

**原因**: 03 以外を正にした、片方だけ更新。

**対処**: **03 を正**とし、ファクトチェック表を全パターンで統一（workflow-full.md）。
