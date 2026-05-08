# 月次レポート（Pattern B × 月次案）サンプル置き場

- **ユーザーレビュー（鈴木・高藤・整理済み）**: [USER_REVIEW_月次レポート_2名分.md](USER_REVIEW_月次レポート_2名分.md)
- **実施ステップとレビュー観点**: [IMPLEMENTATION_STEPS_月次レビュー対応.md](IMPLEMENTATION_STEPS_月次レビュー対応.md)
- **再現性方針（テンプレ／スキル／プロンプト）**: [REPRODUCIBILITY_方針_月次レポート.md](REPRODUCIBILITY_方針_月次レポート.md)

## 推奨する作業順（個別生徒の前に）

1. **項目とデータソース**を固定する: スプレの月次マップを [monthly_pattern_b_content.template.md](monthly_pattern_b_content.template.md) 先頭の表に写す。設計の参照として [_mapping_monthly_to_pattern_b.md](_mapping_monthly_to_pattern_b.md) を使う。
2. **レイアウト**を固定する: [monthly_pattern_b_template.html](monthly_pattern_b_template.html) をブラウザで開き、見出し（**01・02（塾）・03（授業）・04・05・07**。06 は使わない。学校の試験は原則 01 に集約）と表の列が月次案と矛盾しないか確認する。変更は主に「行数・列数・KPI の有無」に留める。
3. その後、生徒別 MD を複製して中身を埋め、確定 MD から HTML を複製ファイルへ転記する。

## ファイル

| ファイル | 用途 |
|----------|------|
| [_mapping_monthly_to_pattern_b.md](_mapping_monthly_to_pattern_b.md) | 月次案（スプレ「イメージ」タブ）の**データソース注記**と Pattern B コンポーネントの対応表（Step 1 相当） |
| [monthly_pattern_b_content.template.md](monthly_pattern_b_content.template.md) | **Markdown 正本ひな形**（月次マップ写し・レイアウト対応表・各 `##` の根拠ソース行・推敲3回ログ・人間チェックリスト）（Step 2 + 2b） |
| [monthly_pattern_b_template.html](monthly_pattern_b_template.html) | **月次案対応のレイアウトひな型**（`pattern_b.html` の CSS を流用し、セクション構成のみ月次用に整理） |
| `monthly_YYYY-MM_<student>.md` | 生徒別に上記テンプレを複製して作成 |
| `monthly_YYYY-MM_<student>.html` | テンプレ HTML を複製し、確定 MD から転記した配布用 |
| [monthly_2026-04_suzuki_report.md](monthly_2026-04_suzuki_report.md) / [monthly_2026-04_suzuki_report.html](monthly_2026-04_suzuki_report.html) | **配布用** 73594 鈴木謙吾さま（2026-03 対象・レポート文体） |
| [monthly_2026-04_takafuji_report.md](monthly_2026-04_takafuji_report.md) / [monthly_2026-04_takafuji_report.html](monthly_2026-04_takafuji_report.html) | **配布用** 72324 高藤泰次郎さま（2026-04 対象・**v3.5.1**・05 に学習計画表リンク・**01「学校のテスト状況」**・採番 01・02–05） |
| [REVIEW_高藤_PDFコメント反映_v3.3.md](REVIEW_高藤_PDFコメント反映_v3.3.md) | **内部用** 高藤 PDF レビュー → v3.3 本文・メタ反映メモ |
| [monthly_2026-04_suzuki_sources.md](monthly_2026-04_suzuki_sources.md) | **内部用** ソースメタ・推敲ログ・人間チェック |
| [monthly_2026-04_takafuji_sources.md](monthly_2026-04_takafuji_sources.md) | **内部用** 高藤さま（同上） |
| [monthly_2026-04_suzuki.md](monthly_2026-04_suzuki.md) / [monthly_2026-04_suzuki.html](monthly_2026-04_suzuki.html) | 初版アーカイブ（分割前の単一ファイル） |
| [SECURE_DELIVERY_月次レポート_HTML.md](SECURE_DELIVERY_月次レポート_HTML.md) | **配布** HTML のまま送るときのセキュリティ（署名 URL・ZIP・クラウドリンク）。[T1-3](../../project/T1-3_セキュリティ要件定義書.md) と整合 |

## ワークフロー（短縮）

1. 月次マップ（スプレ）を更新したら、必要に応じて `_mapping_*.md` とテンプレ先頭の対応表を同期する。
2. テンプレを複製し、gws / NotebookLM で各 `##` を埋める（**根拠ソースはマップと同一表記**）。
3. **推敲3回**を `## 推敲ログ` に記録する。
4. `## 人間チェック` を埋めてから HTML 化（プラン Step 3〜）。

プラン全文: Cursor プラン「月次レポート PatternB 手順」参照。

## バージョン（v1 / v2 / v3）

- 方針とパス: [versions/README.md](versions/README.md)
- **v3 / v3.2**＝05 に **10 マス**（**v3.2**: `calendar_buckets_10` を **トピック別**、`sources` と `prog-topic-map` で **03（授業日）**→トピック割当、[DATA_CONTRACT_05_学習の進捗.md](DATA_CONTRACT_05_学習の進捗.md) セクション3.1）。HTML 先頭 `monthly-report-revision: v3.2`。ルートの `*_report.html` が最新。
- **v2**＝ユーザーレビュー反映のみ（表中心の 05）。凍結: `versions/v2/`。
- **v1**＝凍結保管。鈴木は `versions/v1/monthly_2026-04_suzuki_legacy_full.html`（分割・レビュー前の単体 HTML 相当）。高藤は v1 HTML 未保管（`versions/v1/README.md`）。

一覧ページの正本: [monthly-reports-index.html](monthly-reports-index.html)（同期で `src/reports/templates/monthly-reports/index.html` になる）。

## Vercel（Pattern A〜D と同じ配信）

ルートの [vercel.json](../../../vercel.json) は `src/reports/templates/**` を静的配信する。月次の `*_report.html` と **`versions/`**・**`monthly-reports-index.html`** をデプロイに含めるには、次を実行してから `vercel` / `vercel deploy --prod` する。

```bash
node scripts/sync_monthly_reports_to_vercel.mjs
```

配信パス例: `/monthly-reports/index.html`（一覧）、`/monthly-reports/versions/v3/monthly_2026-04_suzuki_report.html`（凍結 v3）など。トップのパターン一覧は [src/reports/templates/index.html](../../../src/reports/templates/index.html) から「月次サンプル」へリンク済み。
