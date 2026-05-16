# 全文エディタと manifest

## ローカルで開く（必須経路）

`file://` ではマニフェストやサンプル HTML を fetch できない。

```powershell
python scripts/serve_project.py
```

ブラウザで（ポートは起動ログに従う）:

`http://127.0.0.1:<port>/docs/samples/monthly-reports/tools/monthly_report_full_editor.html`

## 初回読み込みを特定サンプルにする

ブラウザ下書きが **無い** ときだけ効く:

`.../monthly_report_full_editor.html?sample=<manifest のキー>`

例: `?sample=tokura`（`reports-manifest.json` の `samples.tokura` が指す HTML）。

下書きが残っている場合は **下書き削除** するか、画面上の **マニフェスト由来のサンプルボタン**から選ぶ。

## manifest のルール

正本は次の **両方** を同期させる。

- [docs/samples/monthly-reports/reports-manifest.json](../../../docs/samples/monthly-reports/reports-manifest.json)
- [src/reports/templates/monthly-reports/reports-manifest.json](../../../src/reports/templates/monthly-reports/reports-manifest.json)

新しいレポート HTML を追加したら:

1. `samples` に `"<slug>": "monthly_YYYY-MM_<slug>_report.html"` を追加（または更新）。
2. **`revision` を必ず変更**する（エディタが正本更新を検知するため）。

## 新規 HTML をデプロイしたときのチェックリスト

- [ ] `docs/samples/monthly-reports/monthly_YYYY-MM_<slug>_report.html` が正本
- [ ] `src/reports/templates/monthly-reports/monthly_YYYY-MM_<slug>_report.html` にミラー（運用ルールに従う）
- [ ] 両 `reports-manifest.json` 更新 + `revision`
- [ ] [vercel.json](../../../vercel.json) に `/monthly_YYYY-MM_<slug>_report.html` → 静的パスのルート追加（既存パターンと同様）
- [ ] [monthly-reports/index.html](../../../src/reports/templates/monthly-reports/index.html) にカード追加（任意だが推奨）
- [ ] デプロイ時は `node scripts/sync_monthly_reports_to_vercel.mjs` を運用に合わせ実行

## 本番 URL

静的プロトタイプ: `https://ea-report-prototypes.vercel.app/monthly-reports/tools/monthly_report_full_editor.html`

マニフェストはデプロイ済み JSON を読む。ローカルで編集した manifest を本番でも見せたい場合は **デプロイ後**に確認する。
