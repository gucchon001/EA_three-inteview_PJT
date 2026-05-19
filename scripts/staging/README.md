# Staging helper scripts

レポート工房 MVP の `staging` 準備を、手元から確認しやすくするための補助スクリプトです。実 Secret 値は受け取りません。

## 1. preflight

Cloud Run `staging` へ出す前に、ローカルの準備と GCP 側の最低限の前提を確認します。

```powershell
pwsh ./scripts/staging/monthly_report_staging_preflight.ps1
```

確認するもの:

- `Dockerfile`
- `requirements-app.txt`
- `supabase/migrations/*.sql`
- `gcloud` の active project / active account
- staging に必要な GCP API が有効か
- runtime service account が存在するか
- 現在の shell に必要な非Secret env があるか
- Secret Manager に必要な secret が存在するか

## 2. smoke

deploy 後に browser 到達確認を行います。

```powershell
pwsh ./scripts/staging/monthly_report_staging_smoke.ps1 `
  -ServiceUrl "https://monthly-report-workshop-staging-xxxxx-an.a.run.app"
```

確認するもの:

- `/health` が `200`
- `/monthly-reports/jobs` が `200` または redirect
- `/auth/google` が `302/303`

この smoke の次に、Cloud Run Jobs の worker smoke を必ず行います。helper script は browser 到達確認までで、worker 実行自体は [staging-deploy-runbook.md](C:/dev/CODE/EA_three-inteview_PJT/docs/monthly-report-workshop/staging-deploy-runbook.md) の `Worker Job Smoke` を正本にします。

`/healthz` は Cloud Run の予約パス制限に当たりうるため、staging smoke では `/health` を使います。

## 3. monitoring

worker smoke のあとに、Cloud Monitoring alert policy と通知先を揃えるための helper です。既定は preview only で、`-Apply` を付けたときだけ Cloud Logging metric / Cloud Monitoring policy を create or update します。

```powershell
pwsh ./scripts/staging/monthly_report_staging_monitoring.ps1 `
  -NotificationChannels "projects/gen-lang-client-0360012476/notificationChannels/1234567890123456789" `
  -RunbookUrl "https://github.com/gucchon001/EA_three-inteview_PJT/blob/main/docs/monthly-report-workshop/staging-deploy-runbook.md" `
  -SecurityOperationsUrl "https://github.com/gucchon001/EA_three-inteview_PJT/blob/main/docs/monthly-report-workshop/security-operations.md"
```

実反映:

```powershell
pwsh ./scripts/staging/monthly_report_staging_monitoring.ps1 `
  -NotificationChannels "projects/gen-lang-client-0360012476/notificationChannels/1234567890123456789" `
  -Apply
```

作成/更新対象:

- log-based metric `monthly_report_worker_failed_count`
- alert policy `monthly-report-staging-worker-manual-recovery`
- alert policy `monthly-report-staging-worker-failed-spike`
- alert policy `monthly-report-staging-worker-fetch-sources-stale`

通知先は full resource name でも numeric channel id でも渡せます。Cloud Monitoring の documentation field にはローカルファイルではなく、GitHub blob などの到達可能な URL を渡してください。

## 注意

- `staging` は現行MVPでは `public ingress` 前提です。
- OAuth / 通常UIライブE2Eは、Cloud Run IAM private service のままだと成立しません。
- 実際の手順順序は [staging-deploy-runbook.md](C:/dev/CODE/EA_three-inteview_PJT/docs/monthly-report-workshop/staging-deploy-runbook.md) を正本にします。
