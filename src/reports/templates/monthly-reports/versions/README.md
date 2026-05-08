# 月次レポート HTML のバージョン管理

## 方針

- **上書き禁止**: 配布用の大きな改訂ごとに **`versions/vN/`** に HTML（必要なら MD）をコピーして凍結する。
- **最新版の URL**: ルートの `monthly_YYYY-MM_<name>_report.html` を正とする（運用・Vercel 同期の既定）。内容が v3 なら HTML 先頭コメントに `monthly-report-revision: v3` を記す。
- **過去版の URL**: `versions/v1/...` のように **明示パス**で参照する。

## 現在の格納

| バージョン | 鈴木（73594） | 高藤（72324） | 備考 |
|------------|---------------|---------------|------|
| **v1** | [v1/monthly_2026-04_suzuki_legacy_full.html](v1/monthly_2026-04_suzuki_legacy_full.html) | [v1/README.md](v1/README.md) | 鈴木は分割・レビュー対応**前**の単体 HTML（`monthly_2026-04_suzuki.html` 相当）を凍結。高藤は初回から `_report` のみのため **v1 HTML は未保管**（README に記載）。 |
| **v2** | [v2/monthly_2026-04_suzuki_report.html](v2/monthly_2026-04_suzuki_report.html) | [v2/monthly_2026-04_takafuji_report.html](v2/monthly_2026-04_takafuji_report.html) | ユーザーレビュー反映後（2026-04-22）。MD も同梱。 |
| **v3** | [v3/monthly_2026-04_suzuki_report.html](v3/monthly_2026-04_suzuki_report.html) | [v3/monthly_2026-04_takafuji_report.html](v3/monthly_2026-04_takafuji_report.html) | **鈴木** **v3.2**：05 に **10 マス**・`calendar_buckets_10`（週別）。[DATA_CONTRACT_05_学習の進捗.md](../DATA_CONTRACT_05_学習の進捗.md)。**高藤** **v3.5.1**：v3.5 ＋ **05 学習計画表**をスプレッドシートへリンク（▶学習計画表）。学校の試験の独立節なし。**Statistics（Topic 4）学校テスト**は **01「学校のテスト状況」**。採番 01・02–05。MD 同梱。 |

## 次回 v4 を出すとき

1. ルートの `*_report.html` / `.md` を編集して新版にする。
2. リリース時点の内容を `versions/v4/` にコピーして凍結する。
3. `node scripts/sync_monthly_reports_to_vercel.mjs` を実行し、`monthly-reports/index.html` のバージョン表を更新。
4. `vercel deploy`（または本番プロモート）。
