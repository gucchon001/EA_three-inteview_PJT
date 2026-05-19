# レポート工房 MVP staging デプロイ準備 Runbook

## 位置づけ

- 正本/補助資料の区分: MVP staging 環境の実デプロイ前準備 runbook
- 起点: `development-plan.md`, `security-operations.md`, `pre-e2e-setup.md`
- 関連文書: `AUTOMATION_NORTH_STAR.md`, `api-definition.md`, `test-plan.md`, `production-promotion-checklist.md`
- 最終更新: 2026-05-19

この runbook は、レポート工房 MVP を Google Cloud `gen-lang-client-0360012476` の staging 環境へ出す直前に、Secret、IAM、Cloud Run service、Cloud Run Jobs、smoke、ライブ E2E の準備を揃えるための手順である。実 Secret 値、資格情報 JSON の中身、OAuth client secret、OpenRouter key、Supabase service role key はこの文書にも Git 管理ファイルにも書かない。staging green 後の production 昇格手順は [production-promotion-checklist.md](production-promotion-checklist.md) を正とする。

## 決定事項

- Project ID: `gen-lang-client-0360012476`
- Region: `asia-northeast1`
- Artifact Registry repository: `monthly-report-workshop`
- Cloud Run service: `monthly-report-workshop-staging`
- Cloud Run Job: `monthly-report-worker-staging`
- Runtime service account: `monthly-report-staging@gen-lang-client-0360012476.iam.gserviceaccount.com`
- Build source: repo root
- Packaging: root `Dockerfile` + `requirements-app.txt`
- HTTP entrypoint: `uvicorn eb_app.main:app --app-dir src --host 0.0.0.0 --port ${PORT:-8080}`
- Worker entrypoint: `python -m eb_app.monthly_reports.worker_entry --max-jobs 1 --lease-timeout-seconds 900`
- MVP completion condition: レポート工房 MVP が staging 環境で動くこと。指導ポータル統合は今回の完了条件に含めない。
- MVP staging の Cloud Run service は **public ingress** を前提とする。通常UI、`/auth/google`、`/auth/callback`、Supabase session bridge はブラウザ経由で到達できる必要があり、Cloud Run IAM private service 前提とは両立しない。アクセス制御は Cloud Run IAM ではなく、Supabase Auth、`tomonokai-corp.com` 制限、HTTPOnly Cookie、RLS で行う。
- 2026-05-19 時点の確認済み staging image は `01c993a-templatefix-20260519`、service revision は `monthly-report-workshop-staging-00004-9vt`、worker smoke 最新 execution は `monthly-report-worker-staging-fpfks`、API live E2E 成功 job は `mrj_b2695817af474330a2eed6b43cc3be00`。

## Cloud Run 構成

Cloud Run service は FastAPI の HTTP UI/API を受ける。対象は `/health`, `/auth/google`, `/auth/callback`, `/monthly-report-workshop/e2e`, `/monthly-reports/*`, `/api/monthly-reports/*` で、通常 UI の DOM 更新は HTML page/action/fragment を使う。

Cloud Run Jobs は DB 上の `queued` job を claim して OpenRouter 生成、validation、artifact 保存を進める。HTTP service のプロセスメモリには依存しない。初期 staging では常駐 worker pool ではなく、手動またはスケジュール実行の Cloud Run Job として扱う。

## APIs to Enable

```bash
gcloud config set project gen-lang-client-0360012476
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com
```

Google OAuth / Workspace read flow で使う API:

```bash
gcloud services enable \
  docs.googleapis.com \
  sheets.googleapis.com \
  drive.googleapis.com
```

## Authentication Policy

ローカルのデプロイ操作は、人間アカウントの `gcloud auth login` と runtime service account impersonation を第一候補にする。ユーザー提供の credential path `/config/gen-lang-client-0360012476-457924b0f2ae.json`、またはWindows作業環境での `config/gen-lang-client-0360012476-457924b0f2ae.json` は中身を表示・コピーしない。やむを得ず使う場合もローカルの一時操作だけに限定し、Cloud Run 環境変数や Secret Manager へ service account key JSON を登録しない。

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project gen-lang-client-0360012476
```

## Service Account / IAM Checklist

デプロイ実行者に必要な権限:

- `roles/run.admin` on project
- `roles/run.sourceDeveloper` on project
- `roles/iam.serviceAccountUser` on `monthly-report-staging@gen-lang-client-0360012476.iam.gserviceaccount.com`
- `roles/artifactregistry.admin` または repository 作成済みなら必要最小の writer
- `roles/secretmanager.admin` または Secret 作成/更新担当者
- `roles/logging.viewer` for smoke/debug

Runtime service account:

```bash
gcloud iam service-accounts create monthly-report-staging \
  --display-name="Monthly Report Workshop staging runtime"
```

実作成済みの service account:

```bash
gcloud iam service-accounts describe \
  monthly-report-staging@gen-lang-client-0360012476.iam.gserviceaccount.com
```

Runtime service account に付与する最小権限:

- Secret Manager Secret Accessor: `roles/secretmanager.secretAccessor`
- Logs Writer は Cloud Run 実行基盤で通常利用できる。明示が必要な組織設定なら `roles/logging.logWriter`

staging テスターの browser access について:

- MVP staging service は `--allow-unauthenticated` を前提にするため、一般のテスターへ `roles/run.invoker` を配らない。
- もし組織ポリシーで unauthenticated ingress が禁止される場合、現行の `/auth/google` / `/auth/callback` / 通常UI smoke はそのままでは成立しない。IAP / LB / 別auth境界の追加設計が必要で、今回のMVP staging完了条件から外れる blocker として扱う。

Cloud Build service account には build/deploy 方式に応じて以下を確認する:

- Artifact Registry writer
- Cloud Run Builder: `roles/run.builder`
- 必要時のみ Service Account User on runtime service account

## Secret Names

Secret Manager には staging 専用値だけを入れる。production、local、portal staging と混ぜない。

| Secret name | Cloud Run env var | 手動設定場所 |
|---|---|---|
| `mrf-staging-eb-monthly-report-database-url` | `EB_MONTHLY_REPORT_DATABASE_URL` | Supabase staging project の DB connection string |
| `mrf-staging-supabase-jwt-secret` | `SUPABASE_JWT_SECRET` | Supabase staging Dashboard |
| `mrf-staging-google-oauth-client-secret` | `GOOGLE_OAUTH_CLIENT_SECRET` | Google Cloud OAuth client |
| `mrf-staging-google-token-encryption-key` | `EB_GOOGLE_TOKEN_ENCRYPTION_KEY` | operator が生成し Secret Manager へ登録 |
| `mrf-staging-openrouter-api-key` | `OPENROUTER_API_KEY` | OpenRouter dashboard |

Secret にしない staging env:

| Env var | Value |
|---|---|
| `EB_ENV` | `staging` |
| `EB_AUTH_MODE` | `supabase` |
| `EB_ENABLE_MOCK_UI` | unset or `0` |
| `EB_ALLOWED_EMAIL_DOMAIN` | `tomonokai-corp.com` |
| `SUPABASE_URL` | Supabase staging project URL |
| `SUPABASE_ANON_KEY` | Supabase staging anon key |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` |
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth staging client ID |
| `EB_GOOGLE_TOKEN_ENCRYPTION_KEY_VERSION` | `staging-v1` |
| `EB_GOOGLE_OAUTH_SCOPES` | `openid email profile https://www.googleapis.com/auth/documents.readonly https://www.googleapis.com/auth/spreadsheets.readonly https://www.googleapis.com/auth/drive.readonly` |
| `OPENROUTER_MODEL_REPORT` | staging で検証する report model |
| `OPENROUTER_MODEL_LIGHT` | staging で検証する light model |
| `OPENROUTER_TIMEOUT` | `120` 以上を推奨 |
| `EB_MONTHLY_REPORT_PROMPT_VERSION` | staging 検証対象の prompt version |
| `EB_APP_VERSION` | Git SHA or release tag |

## Manual Setup Locations

Supabase staging:

- Project settings: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`
- Auth Providers > Google: Google OAuth client ID / client secret
- Auth URL Configuration: `Site URL` に staging service URL の origin を設定する
- Auth URL Configuration: `Additional Redirect URLs` に `https://<staging-service-url>/auth/callback` を登録する
- Auth URL Configuration の例: `https://monthly-report-workshop-staging-<hash>-an.a.run.app/auth/callback`
- Database: `supabase/migrations/*.sql` を staging DB に適用
- RLS: `monthly_report_*` tables の RLS 有効化と policy 適用を確認

Google Cloud Console:

- OAuth consent screen: Internal が可能なら Workspace 内部アプリ。External/testing の場合は staging テストユーザーを明示
- OAuth client: Web application
- Authorized redirect URI: `https://<SUPABASE_PROJECT_REF>.supabase.co/auth/v1/callback`
- Authorized domain: Supabase / Cloud Run / 独自ドメインの構成に合わせる

OpenRouter:

- staging 用 API key を作成
- 利用上限と対象 model を確認
- key value は `mrf-staging-openrouter-api-key` にだけ登録

GitHub repository secrets for optional smoke:

- `CLOUD_RUN_SMOKE_URL`: `https://<staging-service-url>/health`
- `CLOUD_RUN_SMOKE_BEARER_TOKEN`: MVP staging は public service 前提のため通常不要。後続でprivate health endpointを増やす場合だけ設定

## Manual Setup Order

手動設定は次の順で進める。前の項目が埋まっていない状態で次へ進まない。

1. Google Cloud project の API 有効化と Artifact Registry / runtime service account 作成
2. Supabase staging project 作成
3. Supabase staging に `supabase/migrations/*.sql` を適用し、RLS policy を確認
4. Google Cloud Console で OAuth consent screen と Web client を作成
5. Supabase Auth Providers > Google に client ID / client secret を設定
6. Cloud Run staging service 名と URL 形式を確定
7. Supabase Auth URL Configuration に `Site URL` と `Additional Redirect URLs` を設定
8. Secret Manager に DB URL、JWT secret、Google OAuth client secret、token encryption key、OpenRouter API key を登録
9. Cloud Run service / Cloud Run Job で使う非Secret env を確定
10. staging テスト用の Google Docs / Sheets を用意し、テストユーザーから閲覧できることを確認
11. root `Dockerfile` から image build
12. 同じ image tag で Cloud Run service と Cloud Run Job を deploy
13. `/health`、`/monthly-reports/jobs`、`/auth/google` の browser smoke
14. Cloud Run Jobs の worker smoke を実行し、queued job なしでも entrypoint が正常終了することを確認
15. 通常UIまたは `/monthly-report-workshop/e2e` で Google OAuth → source fetch → OpenRouter → preview/validation のライブE2E

実行補助:

- 事前確認: `pwsh ./scripts/staging/monthly_report_staging_preflight.ps1`
- deploy 後 smoke: `pwsh ./scripts/staging/monthly_report_staging_smoke.ps1 -ServiceUrl "https://<staging-service-url>"`

各ステップで人手が埋める値:

1. Supabase staging
`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`, Google provider設定、`Site URL`, `Additional Redirect URLs`

2. Google OAuth
`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, OAuth consent screen の公開範囲、テストユーザー

3. OpenRouter
`OPENROUTER_API_KEY`, `OPENROUTER_MODEL_REPORT`, `OPENROUTER_MODEL_LIGHT`

4. Cloud Run
service URL、`EB_APP_VERSION`, `EB_MONTHLY_REPORT_PROMPT_VERSION`, deploy 実行アカウント、`allow-unauthenticated`

## Pre-Deploy Prerequisites

staging deploy 前に、次が埋まっていることを確認する:

- Supabase staging project が作成済みで、`monthly_report_*` migration と RLS policy が適用済み
- Cloud Run staging service URL に使う region / service name が確定している
- `tomonokai-corp.com` の staging テストユーザーが 1人以上用意されている
- staging テスト用の Google Docs 1件以上、Google Sheets 1件以上があり、OAuth 実行ユーザーから閲覧できる
- `OPENROUTER_MODEL_REPORT`, `OPENROUTER_MODEL_LIGHT`, `EB_MONTHLY_REPORT_PROMPT_VERSION`, `EB_APP_VERSION` の staging 値が決まっている
- worker job と service が **同じ image tag** を使う運用にする
- GitHub Actions manual smoke を使うなら `CLOUD_RUN_SMOKE_URL` を登録済み

## Secret Creation Templates

値は標準入力または安全な operator 端末から登録する。コマンド履歴へ実値を残さない。

```bash
printf '%s' '<value>' | gcloud secrets create mrf-staging-openrouter-api-key \
  --replication-policy=automatic \
  --data-file=-

printf '%s' '<value>' | gcloud secrets versions add mrf-staging-openrouter-api-key \
  --data-file=-
```

他の Secret も同じ形で作成する。`<value>` は実行時に operator が置き換え、作業ログへ残さない。

## Artifact Registry

```bash
gcloud artifacts repositories create monthly-report-workshop \
  --repository-format=docker \
  --location=asia-northeast1 \
  --description="Monthly Report Workshop staging/prod images"
```

Image name template:

```bash
IMAGE="asia-northeast1-docker.pkg.dev/gen-lang-client-0360012476/monthly-report-workshop/monthly-report-workshop:${GIT_SHA}"
```

## Build / Deploy Command Templates

repo root の `Dockerfile` を staging service/job 共通 image の正本とする。`requirements-app.txt` を install し、`src` と既存全文エディタ bridge に必要な `docs/samples/monthly-reports/tools` だけを copy し、`eb_app.main:app` を起動する。

Dockerfile 方式の template:

```bash
GIT_SHA="$(git rev-parse --short=12 HEAD)"
IMAGE="asia-northeast1-docker.pkg.dev/gen-lang-client-0360012476/monthly-report-workshop/monthly-report-workshop:${GIT_SHA}"

gcloud builds submit \
  --tag "${IMAGE}" \
  --project gen-lang-client-0360012476
```

Service deploy template:

```bash
gcloud run deploy monthly-report-workshop-staging \
  --image "${IMAGE}" \
  --region asia-northeast1 \
  --service-account monthly-report-staging@gen-lang-client-0360012476.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --set-env-vars EB_ENV=staging,EB_AUTH_MODE=supabase,EB_ALLOWED_EMAIL_DOMAIN=tomonokai-corp.com,SUPABASE_JWT_AUDIENCE=authenticated,EB_GOOGLE_TOKEN_ENCRYPTION_KEY_VERSION=staging-v1,EB_APP_VERSION="${GIT_SHA}" \
  --set-env-vars SUPABASE_URL="<SUPABASE_STAGING_URL>",SUPABASE_ANON_KEY="<SUPABASE_STAGING_ANON_KEY>",GOOGLE_OAUTH_CLIENT_ID="<GOOGLE_OAUTH_CLIENT_ID>",OPENROUTER_MODEL_REPORT="<REPORT_MODEL>",OPENROUTER_MODEL_LIGHT="<LIGHT_MODEL>",EB_MONTHLY_REPORT_PROMPT_VERSION="<PROMPT_VERSION>" \
  --set-secrets EB_MONTHLY_REPORT_DATABASE_URL=mrf-staging-eb-monthly-report-database-url:latest,SUPABASE_JWT_SECRET=mrf-staging-supabase-jwt-secret:latest,GOOGLE_OAUTH_CLIENT_SECRET=mrf-staging-google-oauth-client-secret:latest,EB_GOOGLE_TOKEN_ENCRYPTION_KEY=mrf-staging-google-token-encryption-key:latest,OPENROUTER_API_KEY=mrf-staging-openrouter-api-key:latest
```

Worker Job deploy template:

```bash
gcloud run jobs deploy monthly-report-worker-staging \
  --image "${IMAGE}" \
  --region asia-northeast1 \
  --service-account monthly-report-staging@gen-lang-client-0360012476.iam.gserviceaccount.com \
  --memory 1Gi \
  --cpu 1 \
  --task-timeout 1800 \
  --max-retries 0 \
  --command python \
  --args=-m,eb_app.monthly_reports.worker_entry,--max-jobs,1,--lease-timeout-seconds,900 \
  --set-env-vars EB_ENV=staging,EB_AUTH_MODE=supabase,EB_ALLOWED_EMAIL_DOMAIN=tomonokai-corp.com,SUPABASE_JWT_AUDIENCE=authenticated,EB_GOOGLE_TOKEN_ENCRYPTION_KEY_VERSION=staging-v1,EB_APP_VERSION="${GIT_SHA}" \
  --set-env-vars SUPABASE_URL="<SUPABASE_STAGING_URL>",SUPABASE_ANON_KEY="<SUPABASE_STAGING_ANON_KEY>",GOOGLE_OAUTH_CLIENT_ID="<GOOGLE_OAUTH_CLIENT_ID>",OPENROUTER_MODEL_REPORT="<REPORT_MODEL>",OPENROUTER_MODEL_LIGHT="<LIGHT_MODEL>",EB_MONTHLY_REPORT_PROMPT_VERSION="<PROMPT_VERSION>" \
  --set-secrets EB_MONTHLY_REPORT_DATABASE_URL=mrf-staging-eb-monthly-report-database-url:latest,SUPABASE_JWT_SECRET=mrf-staging-supabase-jwt-secret:latest,GOOGLE_OAUTH_CLIENT_SECRET=mrf-staging-google-oauth-client-secret:latest,EB_GOOGLE_TOKEN_ENCRYPTION_KEY=mrf-staging-google-token-encryption-key:latest,OPENROUTER_API_KEY=mrf-staging-openrouter-api-key:latest
```

## Smoke Checks

Service URL:

```bash
SERVICE_URL="$(gcloud run services describe monthly-report-workshop-staging --region asia-northeast1 --format='value(status.url)')"
```

MVP staging public `/health` smoke:

```bash
curl -fsS "${SERVICE_URL}/health"
```

Expected response:

```json
{"status":"ok"}
```

通常UI / OAuth到達確認:

```bash
curl -I "${SERVICE_URL}/monthly-reports/jobs"
curl -I "${SERVICE_URL}/auth/google"
```

合格条件:

- `/health` が 200 を返す
- `/monthly-reports/jobs` が 200 または未ログイン向けの期待した画面遷移を返す
- `/auth/google` が 200 または 302 で Supabase/Google 認可フローへ進める

Note: Cloud Run の既知制限により `/healthz` など `z` で終わる一部 URL path は予約パスと衝突し、container に到達せず Google Frontend の 404 になることがある。staging/prod の外形監視では `/health` を使い、ローカル互換 route として `/healthz` は残す。

後続で private endpoint smoke を別途持つ場合だけ、GitHub Actions の `CLOUD_RUN_SMOKE_BEARER_TOKEN` や `gcloud auth print-identity-token` を使う。

## Worker Job Smoke

queued job がない状態で worker entry が起動できること:

```bash
gcloud run jobs execute monthly-report-worker-staging \
  --region asia-northeast1 \
  --wait
```

合格条件:

- queued job なしなら `status=no_job` で 0 終了
- 生成対象 job ありなら `status=succeeded` または期待した failure classification
- `status=failed` または `manual_recovery_required` は Cloud Run Jobs として非 0 終了を検知
- summary に本文、ソース本文、Google API response、OpenRouter response、prompt 全文、token、`error_message` が出ていない
- `claimed_job_id`, `job_id`, `job_status`, `job_stage`, `manual_recovery_job_count`, `manual_recovery_stages` だけで一次判断できる

2026-05-19 の staging 確認では execution `monthly-report-worker-staging-fpfks` が success で終了した。以後の運用では、この正常系を「Cloud Run Jobは起動でき、PII-safe summaryだけで一次判定できる」基準サンプルとして扱う。

## Post-smoke Monitoring Hookup

worker smoke 成功だけでは本番運用の監視配線は閉じない。staging green 後は次を同じ変更セットで確認する。

1. Cloud Monitoring に `monthly-report-staging-worker-manual-recovery` を作成し、`manual_recovery_required` または job execution failure を通知できるようにする。
2. `monthly-report-staging-worker-failed-spike` を作成し、1時間で3件以上の worker failed を stage/error_type 単位で通知する。
3. `monthly-report-staging-worker-fetch-sources-stale` を作成し、lease timeout 超過の `running/fetch_sources` または retry 上限到達を通知する。
4. 通知先は staging 初期運用者のメールまたは Slack 相当 1 系統へ接続し、本文・ソース本文・provider response・token・Secret を載せない。
5. alert 本文か documentation フィールドから [security-operations.md](security-operations.md) の手動回復runbook節と、この runbook の worker smoke 節へ辿れるようにする。

helper script:

```powershell
pwsh ./scripts/staging/monthly_report_staging_monitoring.ps1 `
  -NotificationChannels "projects/gen-lang-client-0360012476/notificationChannels/<channel-id>" `
  -RunbookUrl "https://github.com/gucchon001/EA_three-inteview_PJT/blob/main/docs/monthly-report-workshop/staging-deploy-runbook.md" `
  -SecurityOperationsUrl "https://github.com/gucchon001/EA_three-inteview_PJT/blob/main/docs/monthly-report-workshop/security-operations.md"
```

実反映時だけ `-Apply` を付ける。script は preview でも `monthly_report_worker_failed_count` metric と3つの policy JSON を生成し、apply 時には log-based metric の upsert と alert policy の create/update まで行う。`monthly-report-staging-worker-fetch-sources-stale` は、現在のworker summary契約に合わせて `job_stage=fetch_sources` かつ `status=failed/retry_scheduled` を一次検知条件にする。

手動確認メモとして検証ログへ残す最小項目:

- policy 名
- 条件の要約
- 通知先
- 参照 runbook
- 正常系基準 execution: `monthly-report-worker-staging-fpfks`

## Staging Live E2E Checklist

1. Supabase staging DB に migration を適用する。
2. RLS policy と通常ユーザー JWT での read 境界を確認する。
3. Cloud Run service の `/health` が通る。
4. `/monthly-reports/jobs` と `/auth/google` が browser から到達できることを確認する。
5. Supabase Auth Redirect URLs に staging `/auth/callback` を登録する。
6. Google OAuth client の redirect URI に Supabase callback を登録する。
7. `tomonokai-corp.com` の staging テストユーザーで `/auth/google` からログインする。
8. `/auth/callback` 後、provider refresh token が `/api/auth/google-oauth/supabase-session` 経由で暗号化保存される。
9. `/monthly-report-workshop/e2e` または通常 UI で staging テスト job を作成する。
10. Google Docs / Sheets の staging テストソースを取得し、source snapshot が保存される。
11. Cloud Run Job を実行し、OpenRouter 生成、validation、draft artifact 保存まで通す。
12. 通常 UI の detail/status/preview/sources/validation fragment が staging URL で表示できる。
13. final Markdown 保存、承認、HTML export の非破壊 smoke を行う。
14. Cloud Logging に本文、ソース本文、Secret、token、provider response が出ていないことを確認する。
15. GitHub Actions `Monthly Report Operational Guardrails` の manual smoke を `CLOUD_RUN_SMOKE_URL=${SERVICE_URL}/health` で実行する。

## Verification Commands Before Deploy

Secret なしで実行できる確認:

```bash
pytest \
  tests/test_health.py \
  tests/test_monthly_report_worker_entry.py \
  tests/test_monthly_report_cloud_logging.py \
  tests/test_monthly_report_pii_safety.py \
  -q
```

差分確認:

```bash
git diff -- docs/monthly-report-workshop/staging-deploy-runbook.md
```

staging green 後に production 昇格準備へ進む場合:

```bash
git diff -- docs/monthly-report-workshop/staging-deploy-runbook.md docs/monthly-report-workshop/production-promotion-checklist.md
```

## 未決事項 / Blockers

- ユーザー提供 credential は、このWindows作業環境では `config/gen-lang-client-0360012476-457924b0f2ae.json` として存在のみ確認済み。中身は読まない。実デプロイでは可能なら service account key ではなく impersonation へ切り替える。
- root `Dockerfile` のローカル Docker image build と `/healthz` smoke は2026-05-18に確認済み。Cloud Run staging の外形 smoke は `/health` を使う。
- staging の正式 Cloud Run URL は初回 deploy 後に確定する。確定後、Supabase Redirect URLs と GitHub `CLOUD_RUN_SMOKE_URL` を更新する。
- staging を private Cloud Run service としてしか公開できない組織制約がある場合、現行MVPの Supabase/Google OAuth callback と通常ブラウザUI smoke は成立しない。IAP/LB配下の別構成を追加設計するか、MVP staging の公開方針を再決定する必要がある。
- staging Supabase project / region / DB URL / anon key / JWT secret は operator が Dashboard で設定する。
- Google OAuth consent、OAuth client、Authorized redirect URI は operator が Google Cloud Console で設定する。
- OpenRouter API key、model、利用上限は operator が OpenRouter dashboard で設定する。
- production promotion checklist は [production-promotion-checklist.md](production-promotion-checklist.md) を正とする。same-image deploy、env/secret/redirect 分離、`/health` smoke、rollback、browser OAuth blocker をそこで管理する。

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-18 | MVP staging デプロイ準備 runbook を追加 |
| 2026-05-18 | root `Dockerfile` / `requirements-app.txt` を staging packaging 正本として反映 |
| 2026-05-18 | ローカルDockerで staging image build と `/healthz` smoke が通ったことを反映 |
| 2026-05-19 | Cloud Run 予約 URL path 制限を踏まえ、staging/prod の外形 health smoke を `/health` に変更 |
| 2026-05-18 | MVP staging は public Cloud Run ingress 前提であること、browser/OAuth smoke、pre-deploy prerequisites、private service時の blocker を追記 |
| 2026-05-19 | staging green の確認済み image / revision / worker execution / live E2E job を反映し、worker監視alertの最小接続手順と production promotion checklist への参照を追加 |
| 2026-05-19 | alert policy / notification channel / runbook URL 差し込み用の staging monitoring helper script を追加 |
