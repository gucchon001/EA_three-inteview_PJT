# セキュリティ・運用設計書

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツールのセキュリティ・運用設計
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- 関連文書: `requirements.md`, `data-design.md`, `api-definition.md`
- 最終更新: 2026-05-19

## 認証

- MVPはSupabase AuthのGoogle providerを使う。
- `tomonokai-corp.com` ドメインのユーザーだけを許可する。
- Supabase AuthのセッションをFastAPI側で検証し、メールまたはGoogle provider由来の情報でドメイン制限を行う。
- ドメイン不一致は403として扱う。
- SSR/HTMX本番UIではPKCE flowと `HTTPOnly`, `Secure`, `SameSite=Lax` Cookieを正とする。アクセストークンをブラウザJSやlocalStorageで常用しない。
- 移行期のSupabase callback bridgeは、Supabase access tokenをサーバ側で検証した後に `eb_auth_session` Cookieを `HTTPOnly`, `Secure`（local/dev/test以外）, `SameSite=Lax` でセットする。以後の通常UI認証はこのCookieを優先経路へ寄せる。
- POST/PUT/DELETE相当の画面操作はCSRF対策を通す。初期方針はサーバ生成CSRF tokenをCookieまたはセッションと対応付け、HTMXフォームからhidden inputまたは `X-CSRF-Token` で送る方式とする。
- Bearer token検証はE2E、内部JSON API、管理スクリプト、移行中の互換経路として扱い、通常UI境界の主方式にしない。

### ローカル開発

- ローカル環境ではGoogle/Supabase Authの実ログインを使わず、開発用モック認証を使う。
- モック認証は `EB_AUTH_MODE=mock` のような明示的な環境変数でのみ有効にする。
- モックユーザーのメールは `tomonokai-corp.com` ドメインに固定する。
- 管理者モックユーザーは `y-haraguchi@tomonokai-corp.com` を既定にする。互換用に `mock-admin@tomonokai-corp.com` と `mock-user@tomonokai-corp.com` も残す。
- ローカルで保存済みGoogle OAuth credentialを実Google取得に使う場合、`EB_MOCK_USER_EMAIL=y-haraguchi@tomonokai-corp.com` と、保存済みSupabase Auth user UUIDを `EB_MOCK_USER_ID` に設定する。メールアドレスをDBのUUID列へ渡さない。
- 本番で `mock` を有効にして起動しようとした場合は、アプリ起動時に失敗させる。
- モック認証はGoogle provider tokenを持たないため、Google API取得もfixtureまたは手動アップロード相当のモックに切り替える。
- 月次レポートAPIは認証依存関係を必ず通す。ローカルmockでは固定ユーザーを返す。非mockの通常UIはCookieセッション、移行期のJSON API/E2EはBearer tokenをSupabase JWT secretで検証する。

### OAuth開始・callback

Supabase AuthのOAuth開始・callbackは認証基盤側の責務とし、月次レポートAPI定義には含めない。月次レポートAPIは、認証済みユーザーと必要なGoogle API credentialが取得済みである前提で動作する。

FastAPI側の移行期JSON API/E2E検証はHS256のSupabase JWT secretを使う。`SUPABASE_JWT_SECRET` が未設定の非mock環境では503、Bearer token不正は401、許可ドメイン外のメールは403とする。audienceは `SUPABASE_JWT_AUDIENCE`、許可ドメインは `EB_ALLOWED_EMAIL_DOMAIN` で上書きできるが、既定値はそれぞれ `authenticated` と `tomonokai-corp.com` とする。

## Google API認可

- Sheets / Docs / Drive APIはユーザーOAuthに基づきサーバ側で取得する。
- ブラウザにサービスアカウント鍵を置かない。
- Supabase AuthのGoogle providerで追加スコープを要求する。
- Google API読取に使うprovider token / provider refresh tokenは、Supabase Authセッションとは別にサーバ側で安全に扱う。
- Supabase Authはprovider tokenを自動永続化・自動更新する前提にしない。アプリ側でprovider refresh tokenを暗号化保存し、必要時にGoogle OAuth token endpointで更新する。

### OAuthスコープ

| 用途 | スコープ |
|---|---|
| ログイン | `openid` |
| メール | `email` |
| プロフィール | `profile` |
| Sheets読取 | `https://www.googleapis.com/auth/spreadsheets.readonly` |
| Docs読取 | `https://www.googleapis.com/auth/documents.readonly` |
| Drive読取 | `https://www.googleapis.com/auth/drive.readonly` |

MVPでは書き込みスコープを持たない。

ローカルの `EB_AUTH_MODE=mock` では、通常は実Google API呼び出しを行わない。Google API連携の単体・結合テストはfixtureまたは明示的な開発用スタブを使う。

MVP初期の疎通確認用に限り、サーバ側環境変数 `EB_GOOGLE_WORKSPACE_ACCESS_TOKEN` を設定した場合、`POST /api/monthly-reports/jobs/{job_id}/fetch-google-sources` からGoogle Docs / Sheets REST APIを呼び出せる。この値はフロント、リクエストbody、ログ、エラー本文へ出さない。本番ではこの環境変数を正規経路にせず、暗号化保存したユーザーOAuth provider token / refresh tokenからサーバ側でaccess tokenを取得する。

### provider refresh token

- Googleのrefresh token取得のため、OAuth開始時に `access_type=offline` と `prompt=consent` を指定する。
- 保存先はSupabase Postgresの専用テーブルとし、アプリ側で暗号化して保存する。
- 暗号方式はPython実装ではFernetを初期実装とする。暗号鍵は `EB_GOOGLE_TOKEN_ENCRYPTION_KEY`、鍵バージョンは `EB_GOOGLE_TOKEN_ENCRYPTION_KEY_VERSION` で管理する。
- 暗号鍵はCloud Run Secretに置き、DBには暗号文のみ保存する。
- ユーザー連携解除、退職、管理者削除時に削除する。
- 取得できない場合は再同意フローへ誘導する。

保存済みrefresh tokenからGoogle OAuth token endpointを呼び、access tokenを再取得する。`GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` とrefresh tokenは、リクエストbody、フロント、ログ、エラー本文に出さない。Google OAuth token refresh失敗時のエラー本文もHTTP statusのみを返す。

アプリ側の保存入口として `POST /api/auth/google-oauth/credentials` を用意する。Supabase Auth callbackまたはサーバ側セッション処理で取得したprovider refresh tokenを、このAPI経由で現在ユーザーに紐づけて暗号化保存する。レスポンスにはcredential id、scope、鍵バージョンのみを返し、refresh token平文は返さない。

Supabase sessionからprovider refresh tokenを受け渡すサーバ側ブリッジとして `POST /api/auth/google-oauth/supabase-session` を用意する。このAPIはpayloadの `supabase_user_id` とFastAPI側で検証した現在ユーザーIDが一致する場合だけ保存し、不一致は403にする。providerはGoogleに限定し、任意で渡されるprovider emailも現在ユーザーのメールと一致する場合だけ受け付ける。OAuth開始・callback自体はSupabase Auth側の責務のままとし、ブリッジAPIにもrefresh token平文をレスポンス・ログ・エラー本文へ出さない。

## Secrets

| Secret | 保存先 | ブラウザ露出 |
|---|---|---|
| `OPENROUTER_API_KEY` | Cloud Run Secret / 環境変数 | 禁止 |
| OAuth client secret | Secret Manager等 | 禁止 |
| DB接続情報 | Secret Manager等 | 禁止 |
| Google provider refresh token | Supabase Postgres暗号化保存 | 禁止 |
| Google token encryption key | Cloud Run Secret | 禁止 |
| Supabase JWT secret | Cloud Run Secret | 禁止 |

## PII保護

- Cloud Loggingへ本文、ソース本文、氏名、スコアを生出力しない。
- ログは `job_id`, `stage`, `duration_ms`, `size_bytes`, `hash`, `error_type` を中心にする。
- Cloud Run標準出力へ出す構造化ログは allowlist 方式で組み立てる。`prompt_text`, `source_text`, `draft_markdown`, `error_message`, `api_key`, `access_token`, `refresh_token`, `client_secret`, 外部APIレスポンス本文などは、渡されてもログpayloadへ入れない。
- OpenRouter、Google Workspace、Google OAuth token refreshの失敗時はHTTP statusと分類だけを外向きエラーに使い、APIキー、access token、refresh token、client secret、プロンプト本文、Google/APIレスポンス本文を含めない。
- 検証失敗時の `error_message` は欠落見出し名・禁止語名・対象外生徒名など、原因特定に必要な最小情報に留め、draft本文全体や生ソース本文を埋め込まない。
- MVPではソーススナップショットと生成物をSupabase Postgresに保存し、権限のあるユーザーだけが読めるようにする。
- サイズが重くなった場合はSupabase Storageへ分離し、Storage側のアクセス制御をPostgresの権限設計と合わせる。

## 権限

| ロール | 権限 |
|---|---|
| 一般ユーザー | 自分のジョブ作成・閲覧・編集 |
| 管理者 | 全ジョブ閲覧、設定、チューニング、失敗調査 |

MVPではロール定義を最小化してよいが、Supabase Postgresを採用し、将来のポータル統合時にRBAC/RLSへ寄せられるよう、`created_by` と監査ログを必須にする。

管理者向けチューニング設定は管理者ロールにだけ公開する。一般ユーザーは固定プリセットで生成し、任意モデル・prompt_version・Auto Routerの選択はできない。

非mock環境では、ジョブ作成時の所有者はJWTの `sub` を使う。一般ユーザーのジョブ一覧・詳細・成果物・検証・LLM呼び出しログ・stage操作は自分のジョブだけに制限し、他ユーザーのジョブIDは404として扱う。ローカルmockでは既存モック開発の利便性を優先し、全ジョブ参照を許可する。

Postgres側は主要テーブルでRLSを有効化する。レポート工房はSupabase RLSを主境界として効かせる方針に寄せる。アプリの通常ユーザーリクエストでは、リクエストごとに検証済みユーザーJWT付きSupabase Clientを生成し、`monthly_report_jobs.created_by = auth.uid()::text` と親ジョブ所有者を基準にしたselect/insert/update policyを通すことを第一候補とする。

service role / direct DB接続は、worker、管理処理、migration、保持期間削除、RLSでは表現しにくいサーバ専用処理に限定する。これらの経路ではAPI側の所有者チェック、監査ログ、操作種別のallowlistを必須にし、通常UIリクエストの読み書き境界にはしない。`audit_logs` はclient accessなし、`google_oauth_credentials` は `user_id = auth.uid()` のみ許可する。

## Cloud Run

MVPのCloud Run環境は staging / production の2環境を用意する。productionリージョンは `asia-northeast1`（東京）とし、stagingも同リージョンを既定にする。関連するArtifact Registry、Secret Manager、Cloud Logging / Monitoring、将来利用するCloud Tasks等も、原則として同リージョンまたは同一国内/近接リージョンに寄せる。

実Supabase Auth + Google OAuth + Google Workspace read flowのライブE2E前設定は [pre-e2e-setup.md](pre-e2e-setup.md) を参照する。Supabaseプロジェクトを新規作成する場合は、Cloud Runの東京リージョンとデータ所在方針に矛盾しないリージョンを選ぶ。

今回プロジェクトの完了条件は、レポート工房MVPがstaging環境で稼働し、migration、RLS、Google OAuth、OpenRouter、HTML UI smoke、ライブE2E、Cloud Run Jobs worker smokeを検証ログへ残すこととする。production昇格は後続スコープとして、staging確認済みrevisionとmigrationを昇格し、Secret・OAuth redirect URI・E2Eデータは環境間で混ぜない。

| 環境 | 用途 | データ/Secret |
|---|---|---|
| local | 開発・focused test・必要時の実機OAuth E2E | `.env` とローカルSupabase。実値はログ・文書へ出さない |
| MVP staging | レポート工房MVPのE2E、migration、RLS、OAuth、OpenRouter smoke、HTML UI smoke | staging用Supabase、staging用Secret、テストDocs/Sheets |
| MVP production | レポート工房MVPの実運用 | production用Supabase、production用Secret、実データ |
| portal staging | 本番ポータル合流前の統合E2E、migration、RLS、OAuth、OpenRouter smoke | portal staging用Supabase、staging用Secret、テストDocs/Sheets |
| portal production | ポータル合流後の実運用 | portal production用Supabase、production用Secret、実データ |

| 項目 | 初期方針 |
|---|---|
| タイムアウト | 900秒 |
| CPU | 1 vCPU |
| メモリ | 1GiB |
| 同時実行 | concurrency 10 |
| 最小インスタンス | 0 |
| 最大インスタンス | 3 |
| Secret | Cloud Run環境変数またはSecret参照 |
| ログ | Cloud Loggingに構造化ログ |

MVPからstaging / productionで分けるもの:

- Cloud Run service name（例: `monthly-report-workshop-staging`, `monthly-report-workshop-production`）
- Supabase project / database URL / anon key / JWT/JWKS issuer
- Google OAuth client またはAuthorized redirect URI
- OpenRouter API keyまたは利用上限
- Google token encryption key と key version
- Cloud Logging / Monitoring のalert policy

長時間生成は、MVPではDBジョブ + HTMXポーリングで扱う。Cloud Tasks、Pub/Sub、Cloud Run Jobsなどの導入は、タイムアウト・再試行・負荷の課題が見えた時点で後続検討とする。

Cloud Run上でworkerを動かす場合は、実行方式を本番前に固定する。最低限、job claimのlease timeout、heartbeat/updated_at、stuck job再claim、再試行上限、手動再実行、協調的キャンセル、Idempotency-Keyまたはjob input hashによる二重実行防止を設計・テスト対象にする。

### Worker実行runbook（MVP初期）

MVP初期のworker entryは `python -m eb_app.monthly_reports.worker_entry` とする。HTTPサーバのプロセスメモリに依存せず、Postgres上の `queued` jobをclaimして1件または指定件数を処理する。Cloud Run Jobsまたは手動実行で使い、常駐サービス化は後続判断とする。

通常UIの `生成開始` / `取得してレポート生成` からは、Supabase通常ユーザーに限り service 側が Cloud Run Jobs REST API `projects.locations.jobs.run` を叩いて worker を自動起動する。execution override では `EB_WORKER_JOB_ID=<job_id>` を渡し、worker はその job だけを claim する。これにより、queued request が別ユーザーや別jobへ流れることを避ける。

必須環境変数:

- `EB_MONTHLY_REPORT_DATABASE_URL`
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL_REPORT`
- `EB_MONTHLY_REPORT_PROMPT_VERSION`
- `EB_APP_VERSION` または Cloud Run の `K_REVISION`

任意環境変数:

- `EB_WORKER_OWNER_USER_ID`: 特定ユーザー/検証ジョブだけを拾う場合に指定
- `EB_WORKER_JOB_ID`: 特定jobだけを処理する場合に指定。通常UIの自動triggerはこの override を使う
- `EB_WORKER_LEASE_TIMEOUT_SECONDS`: stale `running/fetch_sources` jobの再claim判定
- `EB_WORKER_MAX_JOBS`: 1実行で処理する最大job数。既定は1、0はno-jobまで継続
- `EB_WORKER_SLEEP_SECONDS`: ループ時のsleep秒数

Cloud Run service 側で worker 自動起動を有効にする任意環境変数:

- `EB_CLOUD_RUN_WORKER_JOB_PROJECT_ID`
- `EB_CLOUD_RUN_WORKER_JOB_REGION`
- `EB_CLOUD_RUN_WORKER_JOB_NAME`
- `EB_CLOUD_RUN_WORKER_TRIGGER_TIMEOUT_SECONDS`（既定15秒）
- `EB_CLOUD_RUN_WORKER_TRIGGER_ACCESS_TOKEN`（通常は未設定。metadata server以外で明示tokenを使うときだけ）

実行例:

```powershell
python -m eb_app.monthly_reports.worker_entry --max-jobs 1 --lease-timeout-seconds 900
```

Cloud Run Jobsでの初期作成例:

```bash
gcloud run jobs create monthly-report-worker \
  --image asia-northeast1-docker.pkg.dev/PROJECT/REPOSITORY/IMAGE:TAG \
  --region asia-northeast1 \
  --command python \
  --args=-m,eb_app.monthly_reports.worker_entry,--max-jobs,1,--lease-timeout-seconds,900 \
  --set-env-vars EB_MONTHLY_REPORT_PROMPT_VERSION=monthly-report-vYYYYMMDD.N,EB_APP_VERSION=GIT_SHA,OPENROUTER_MODEL_REPORT=anthropic/claude-sonnet-4.6 \
  --set-secrets EB_MONTHLY_REPORT_DATABASE_URL=monthly-report-database-url:latest,OPENROUTER_API_KEY=openrouter-api-key:latest
```

既存Jobのコマンドや環境変数だけを更新する例:

```bash
gcloud run jobs update monthly-report-worker \
  --region asia-northeast1 \
  --command python \
  --args=-m,eb_app.monthly_reports.worker_entry,--max-jobs,1,--lease-timeout-seconds,900 \
  --update-env-vars EB_MONTHLY_REPORT_PROMPT_VERSION=monthly-report-vYYYYMMDD.N,EB_APP_VERSION=GIT_SHA,OPENROUTER_MODEL_REPORT=anthropic/claude-sonnet-4.6
```

実行例:

```bash
gcloud run jobs execute monthly-report-worker --region asia-northeast1 --wait
```

検証用に対象ユーザーだけを拾う場合は、恒久設定ではなく検証専用Jobまたは一時更新で `EB_WORKER_OWNER_USER_ID` を指定する。複数ユーザーの本番queued jobを意図せず処理しないよう、初回smokeは検証用ユーザー/検証用jobだけがqueuedである状態で実行する。

出力は `status`, `claimed_job_id`, `job_id`, `job_status`, `job_stage`, `error_type`, `manual_recovery_job_count`, `manual_recovery_stages` のJSON summaryに限定し、`error_message` やprovider本文は出さない。`failed` または `manual_recovery_required` が含まれる場合は非0終了とし、Cloud Run Jobs側の失敗検知に使う。

期待するJSON summaryの例:

```json
[
  {
    "status": "succeeded",
    "claimed_job_id": "mrj_example",
    "job_id": "mrj_example",
    "job_status": "succeeded",
    "job_stage": "completed",
    "error_type": null,
    "manual_recovery_job_count": 0,
    "manual_recovery_stages": null
  }
]
```

queued jobがない場合は `status=no_job` で0終了してよい。検証時はこれを「worker entryは起動できたが、生成処理smokeではない」と扱い、別途検証jobを作って再実行する。`status=failed` または `status=manual_recovery_required` が1件でも含まれる場合は非0終了を期待値とし、Cloud Run Jobsの失敗として検知してから下記runbookへ進む。`manual_recovery_required` のsummaryでは `manual_recovery_job_count > 0`、`manual_recovery_stages` に `call_llm` / `validate` / `persist` などの後段stageが入ることを確認する。summaryに本文、ソース本文、provider request/response、token、`error_message` が出ていないこともsmokeの合格条件に含める。

現時点では、`--lease-timeout-seconds` 指定時にworker heartbeat threadが `touch_worker_job` をbest-effortで呼び、blockingなOpenRouter呼び出し中もlease更新を試みる。heartbeat失敗時は本文やproviderレスポンスをログへ出さず、worker本体の実行結果で判定する。stale reclaim対象は引き続き `fetch_sources` stageに限定し、`call_llm` / `validate` / `persist` など後段stageの自動再claimはartifact / validation / llm_call_logs の冪等性と手動回復runbookが揃ってから解禁する。

`--lease-timeout-seconds` 指定時にclaim可能jobがなく、lease timeoutを超えた後段 `running` jobが存在する場合、worker entryは自動再実行せず `manual_recovery_required` を返す。一次対応はJSON summaryの `job_id`, `job_stage`, `manual_recovery_job_count`, `manual_recovery_stages` とDB上のartifact / validation / llm_call_logs重複有無を確認し、手動でキャンセル、再生成ジョブ作成、または管理者判断の再実行を選ぶ。本文・ソース・providerレスポンスはsummaryやログへ出さない。

#### stuck後段stageの手動回復runbook

対象は `call_llm` / `validate` / `persist` など、`fetch_sources` 以外の後段stageで `running` のままlease timeoutを超えたjobである。これらはLLM call、artifact、validation、audit logの二重作成リスクがあるため、workerは自動再claimしない。

1. 検知
   - Cloud Run Jobsの非0終了、またはworker entryのPII-safe JSON summaryで `status=manual_recovery_required` を検知する。
   - 最初に見る値は `job_id`, `job_stage`, `manual_recovery_job_count`, `manual_recovery_stages`, `worker_last_claimed_at`, `worker_attempts` に限定する。
   - Cloud Logging / 通知 / Slack相当へ貼る場合も、本文、ソース本文、世帯キー、Google APIレスポンス、OpenRouterレスポンス、`error_message`、token、prompt全文は含めない。

2. 安全確認
   - 対象jobが本当に後段stageか確認する。`fetch_sources` なら通常のstale reclaim対象であり、この手順では処理しない。
   - `monthly_report_jobs.status`, `job_stage`, `worker_last_claimed_at`, `worker_attempts`, `max_worker_attempts`, `updated_at`, `error_type` を確認する。
   - 同じ `job_id` に紐づく `monthly_report_artifacts`, `monthly_report_validations`, `llm_call_logs`, `audit_logs` の件数と作成時刻だけを見る。本文・source payload・provider request/response本文は開かない。
   - 直近のworker logは構造化フィールドだけを見る。provider本文や外部API本文が出ていた場合はインシデントとして扱い、ログ保持/削除方針をSecurity/Opsへエスカレーションする。

3. 判断
   - `call_llm` で `llm_call_logs` がなく、artifact/validationもない場合: providerへ到達前または結果未保存の可能性が高い。管理者が再実行を選べる。ただし同一jobを直接 `queued` に戻すのは、Idempotency-Keyとattempt上限を確認してから行う。
   - `call_llm` で `llm_call_logs` があり、draft artifactがない場合: provider呼び出し済みで永続化前に停止した可能性がある。二重課金・二重生成を避けるため、原則は既存jobをキャンセルし、必要なら再生成ジョブを新規作成する。
   - `validate` でdraft artifactがあり、validationがない場合: draftを根拠にvalidationだけ再実行できる管理入口ができるまでは、既存jobをキャンセルし、新規再生成または手動検証へ回す。
   - `persist` でartifact/validationの一部がある場合: 二重成果物の危険が最も高い。既存jobはキャンセルまたは `manual_recovery_required` のまま保持し、Backend担当が個別に整合性を確認する。自動requeueは禁止する。
   - `worker_attempts >= max_worker_attempts`、または同一jobで2回目の後段stuckが起きた場合: retry/requeueせず、キャンセルまたは新規再生成を選ぶ。

4. 回復操作
   - キャンセル: ユーザーに「この生成は停止し、必要なら再生成する」旨をUI/運用連絡で伝える。監査ログには `monthly_report_worker_manual_cancel` として `job_id`, `job_stage`, `reason`, `operator_id_hash`, `artifact_count`, `validation_count`, `llm_call_count` だけを残す。
   - 新規再生成: 通常の再生成routeまたは管理者手順で新しいqueued jobを作る。元jobのartifactを再利用する場合も、本文はログへ出さず、元job idと新job idの対応だけを監査する。
   - 既存jobのrequeue/retry: 後段stageでは例外扱い。実施条件は「provider未到達または副作用なしを件数で確認済み」「attempt上限内」「同じIdempotency-Key / input hashで重複保存を抑止できる」「担当者2名またはPO/Ops承認済み」とする。操作後はworker entryを `--max-jobs 1` で対象ユーザーまたは対象条件に絞って起動する。
   - 成功確認: 回復後は `status`, `job_stage`, artifact件数、validation件数、llm_call_logs件数、最新audit logだけを確認し、本文は必要最小限の画面確認に留める。

5. 保持期間削除との相互作用
   - `manual_recovery_required` のjobは、保持期間削除の通常dry-runで件数に含めてよいが、調査中はdelete対象から一時除外する。除外ができない場合は削除を延期する。
   - 調査完了後にキャンセル済み・再生成済み・不要と判断したjobだけを保持期間削除runbookへ戻す。
   - retention dry-run/deleteの監査metadataには、stuck理由や本文抜粋ではなく、対象件数、cutoff、operator判断の有無だけを残す。

6. エスカレーション
   - provider本文、Google source本文、token、prompt全文、世帯キーがログやsummaryに出た疑いがある場合は、Security/Opsへ即時エスカレーションする。
   - 同一stageで3件以上、または30分以内に2件以上の `manual_recovery_required` が出た場合は、workerを一時停止し、直近deploy、OpenRouter/Google障害、DB接続、migration差分を確認する。
   - 個別判断で迷う場合は、既存jobをrequeueせずキャンセルまたは保留にし、新規再生成でユーザー体験を回復する。

### CI / Cloud Run smoke

GitHub Actionsの既定PR/pushでは実Secret、実Google API、実OpenRouter、Supabase Dockerを要求しない。`.github/workflows/monthly-report-operational-guardrails.yml` はmigration SQLに対して `drop table/schema` とRLS無効化の静的検出、RLS policy存在確認、`tests/test_monthly_report_schema_files.py` などのsecret不要focused testを実行する。

Cloud Run smokeは実環境URLや認証情報が必要なため、既定CIでは実行しない。必要時だけ `workflow_dispatch` で `run_cloud_run_smoke=true` を選び、repository secret `CLOUD_RUN_SMOKE_URL` に非破壊の確認URLを設定する。認証付きCloud Runの場合は短命またはローテーション可能な `CLOUD_RUN_SMOKE_BEARER_TOKEN` を任意で設定する。workflowはHTTP 2xx/3xxだけを確認し、レスポンス本文やSecret値をログへ出さない。

推奨URLは、将来 `/healthz` を追加した後はそのhealth endpointとする。それまでは認証前提の通常画面やE2E画面ではなく、非破壊で本文にPIIを含まないURLを個別に選ぶ。

Cloud Run Jobsのworker smokeはHTTP endpoint smokeとは別扱いにする。GitHub Actionsの `cloud-run-smoke` jobはCloud Run serviceの疎通確認だけを行い、worker jobのqueued生成、OpenRouter実行、manual recovery検知は運用者がCloud Run Jobsで手動実行して `verification-log.md` へ記録する。手動記録には、実行日時、job名、image tagまたはrevision、worker summaryのPII-safe fields、終了コード、確認したDB件数だけを残し、本文・ソース・Secret値は残さない。

## 構造化ログ

共通フィールド:

- `job_id`
- `user_id_hash`
- `stage`
- `status`
- `duration_ms`
- `error_type`
- `source_count`
- `source_size_bytes`
- `model`
- `prompt_version`
- `provider`
- `requested_model`
- `resolved_model`
- `prompt_kind`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `estimated_cost_usd`
- `daily_budget_usd`
- `http_status`
- `route`
- `method`
- `quota_service`
- `worker_attempts`

上記フィールドは `src/eb_app/monthly_reports/observability.py` の allowlist を正とする。本文、ソース本文、世帯キー、メールアドレス、provider request/response本文、token、API key、client secret はログpayloadとログベースmetric labelに入れない。

### P2-14 監視・費用guardrail契約

MVP初期の実装単位は、実Cloud Monitoringリソースを即作成する前に、ログ名・metric名・label・日次集計schemaをコードと文書で固定する。secret-freeな契約は `LOG_BASED_METRIC_DEFINITIONS` と `DAILY_LLM_COST_SUMMARY_CONTRACT` でテストする。

#### ログベースmetric

| Metric name | Type | Labels | Log filter |
|---|---|---|---|
| `monthly_report_worker_failed_count` | counter | `stage`, `error_type`, `resolved_model`, `prompt_version` | `(resource.type="cloud_run_revision" OR resource.type="cloud_run_job")` かつ `jsonPayload.component="monthly_report_workshop"` かつ `jsonPayload.event` が `monthly_report.provider_failed` / `monthly_report.validation_failed` |
| `monthly_report_llm_token_count` | counter | `provider`, `resolved_model`, `prompt_kind`, `prompt_version` | `monthly_report.provider_succeeded` かつ `jsonPayload.total_tokens>0` |
| `monthly_report_openrouter_error_count` | counter | `provider`, `resolved_model`, `error_type`, `http_status` | `monthly_report.provider_failed` |
| `monthly_report_google_api_error_count` | counter | `quota_service`, `error_type`, `http_status`, `stage` | `monthly_report.google_api_failed` |
| `monthly_report_auth_guardrail_reject_count` | counter | `route`, `method`, `http_status`, `error_type` | `monthly_report.auth_guardrail_rejected` かつ `http_status` が403/429 |

labelは低cardinalityを保つ。`job_id` は調査用ログには残してよいが、metric labelには使わない。`user_id_hash` も急増調査ではログ検索条件に留め、metric labelへ昇格しない。

#### Alert thresholds

| Alert | Threshold | Primary metric/query | 初動 |
|---|---:|---|---|
| Worker failed spike | 1時間で3件以上、またはfailed率10%以上 | `monthly_report_worker_failed_count` by `stage,error_type` | `error_type` をGoogle/OpenRouter/validation/persistへ分類し、同一stage連続ならworkerを一時停止する |
| Worker stuck/manual recovery | `manual_recovery_required` 1件以上 | Cloud Run Jobs終了コード + worker summary log | 後段stage手動回復runbookへ進み、artifact/validation/llm_call_logs件数だけ確認する |
| OpenRouter provider error | 15分で3件以上、またはprovider 5xx連続 | `monthly_report_openrouter_error_count` by `resolved_model,error_type,http_status` | provider障害か入力過大かを切り分け、必要なら新規OpenRouter実行を止める |
| Daily token/cost warning | 日次予算70%以上 | 日次summary `budget_ratio>=0.70` | 高token job、model、prompt_version、source sizeを確認し、モデル/入力切り詰めを検討 |
| Daily token/cost stop candidate | 日次予算90%以上 | 日次summary `budget_ratio>=0.90` | PO/Ops判断で新規生成停止、既存編集/閲覧だけ許可へ切替 |
| Google API quota/OAuth error | 1時間で3件以上 | `monthly_report_google_api_error_count` by `quota_service,http_status` | API別quota、refresh token失効、scope不足、鍵versionを確認 |
| Auth guardrail spike | 15分で10件以上 | `monthly_report_auth_guardrail_reject_count` by `http_status,error_type,route` | CSRF、Cookie、RLS preflight、3件制限、Idempotency-Key欠落を確認 |

#### Cloud Monitoring policy wiring

staging では 2026-05-19 の worker smoke execution `monthly-report-worker-staging-fpfks` を正常系の基準にする。HTTP smokeは service 疎通、worker smokeは JSON summary と終了コード、Cloud Monitoring alert policy は継続監視と手動回復入口の責務を持つ。

最低限作る policy:

1. `monthly-report-staging-worker-manual-recovery`
   - 条件: Cloud Run Job execution failure かつ worker summary に `status=manual_recovery_required`
   - 通知内容: job名、execution名、region、`job_id`, `job_stage`, `manual_recovery_job_count`, `manual_recovery_stages`
   - 初動: 本書の「stuck後段stageの手動回復runbook」へ進む
2. `monthly-report-staging-worker-failed-spike`
   - 条件: `monthly_report_worker_failed_count` が1時間で3件以上、または同一 `stage,error_type` が連続
   - 通知内容: stage、error_type、resolved_model、prompt_version
   - 初動: Google/OpenRouter/validation/persist のどこで増えているか切り分ける
3. `monthly-report-staging-worker-fetch-sources-stale`
   - 条件: `running/fetch_sources` が lease timeout 超過、または retry 上限到達
   - 通知内容: `job_id`, `worker_attempts`, `worker_last_claimed_at`
   - 初動: stale reclaim が進む前提か、同一 source 取得失敗が続いているかを確認する

通知先は staging では初期運用者のメールまたは Slack 相当 1 系統でよい。通知 payload に本文、ソース本文、prompt 全文、provider request/response、token、Secret を入れない。runbook URL は [staging-deploy-runbook.md](staging-deploy-runbook.md) の worker smoke / post-smoke monitoring 節と、本書の手動回復節を指す。Cloud Monitoring の documentation field へ差し込む URL はローカルパスではなく、GitHub blob など運用者がブラウザで辿れる URL を使う。helper は `scripts/staging/monthly_report_staging_monitoring.ps1` を正本にする。

#### 日次token/cost summary contract

日次集計は `llm_call_logs` と構造化ログを突き合わせ、1日1回 `monthly_report.llm_cost_daily_summary` として出す。実装前の契約は以下に固定する。

必須フィールド:

- `summary_date`: JST日付 `YYYY-MM-DD`
- `job_count`, `llm_call_count`
- `input_tokens`, `output_tokens`, `total_tokens`
- `estimated_cost_usd`
- `daily_budget_usd`
- `budget_ratio`
- `model_breakdown`: `resolved_model` ごとの call数、token、概算費用
- `prompt_version_breakdown`: `prompt_version` ごとの call数、token、概算費用
- `top_job_ids_by_tokens`: token上位job idとtoken数のみ。本文、世帯キー、氏名、メールは含めない

禁止フィールド:

- `household_key`, `user_email`, `source_text`, `prompt_text`, `draft_markdown`
- `provider_request_body`, `provider_response_body`
- `api_key`, `access_token`, `refresh_token`

概算費用はOpenRouterのbilling画面を正とし、アプリ側summaryは早期検知用の推定値として扱う。単価表が未設定またはモデル単価不明の場合は、`estimated_cost_usd=null` とし、token集計だけで70%/90%判断を補助する。

#### Budget guardrail停止手順

1. 70%到達: Opsが日次summary、OpenRouter billing、`llm_call_logs` のmodel別tokenを確認する。生成停止はしない。
2. 90%到達: PO/Opsが当日残予算と必要ジョブを確認し、必要なら新規OpenRouter実行を停止する。停止中もジョブ閲覧、編集後Markdown保存、承認、HTML exportは許可する。
3. 100%到達または異常課金疑い: 新規生成開始を停止し、queued jobを増やさない。running jobは二重課金を避けるため即時killではなくstageを確認してからキャンセル/継続判断する。
4. 復旧: 翌日予算または上限変更後、summaryとOpenRouter billingの差分を確認し、停止理由・解除時刻・operator id hashを監査ログへ残す。

監視・アラート:

MVP初期はCloud Monitoring / Cloud Logging、Supabase SQL、OpenRouter管理画面または `llm_call_logs`、Google Cloud Consoleのquota画面を組み合わせる。通知先は初期運用者のメールまたはSlack相当とし、本文・プロンプト・Google APIレスポンス本文・tokenは通知に含めない。

| Metric / event | Suggested alert | First triage action | Owner / where to inspect |
|---|---|---|---|
| Cloud Run 5xx率 | 5分で5xxが3件以上、または5xx率5%以上 | 直近deploy、環境変数、Secret参照、Cloud Run revision logsを確認する | Ops担当 / Cloud Run metrics, Cloud Logging |
| Cloud Run timeout / request latency | timeoutが1件以上、またはp95が30秒超（通常画面）・worker jobが想定上限超 | UI requestかworkerかを分け、workerならjob_idとstageを確認する | Ops担当 / Cloud Run request logs, `monthly_report_jobs` |
| Cloud Run memory / CPU逼迫 | memory 80%以上が15分継続、OOM kill 1件以上 | revisionのmemory、concurrency、入力source size、直近artifact sizeを確認する | Ops担当 / Cloud Run metrics, structured logs |
| worker failed率 | 1時間でfailedが3件以上、またはfailed率10%以上 | `error_type` / `stage` を集計し、Google / OpenRouter / validation / persistに分類する | Backend担当 / `monthly_report_jobs`, Cloud Logging |
| worker stuck / retry上限 | `running` / `fetch_sources` がlease timeout超、またはretry上限到達1件以上 | stale reclaim対象か、後段stageの手動回復対象かを確認し、重複artifact有無を見る | Backend担当 / worker logs, `worker_attempts`, `worker_last_claimed_at` |
| OpenRouter token / cost | 日次tokenまたは概算費用が予算の70% / 90%を超過 | 高token job、model、prompt_version、source_sizeを集計し、必要なら本文生成を一時停止する | LLM担当 / `llm_call_logs`, OpenRouter dashboard |
| OpenRouter timeout / provider error | 15分でtimeout/errorが3件以上、またはprovider 5xxが連続 | provider障害か入力過大かを切り分け、light/report model別に失敗率を見る | LLM担当 / `llm_call_logs`, Cloud Logging |
| Google API quota / 429 | quota errorまたはGoogle 429が1時間で3件以上 | API別（Docs/Sheets/Drive/OAuth）にquota画面を確認し、同一ジョブの再試行ループを止める | Auth/Ops担当 / Google Cloud quota, source fetch logs |
| OAuth refresh failure | refresh失敗が1時間で3件以上、または同一userで連続 | credential失効、scope不足、暗号鍵version、ユーザー退職/連携解除を確認する | Auth担当 / `google_oauth_credentials`, audit logs |
| app 429 | 15分で429が10件以上、または同一userで連続 | 3件同時制限、二重送信、Idempotency-Key欠落、UI連打を確認する | Backend/UI担当 / access logs, `monthly_report_idempotency_keys` |
| CSRF拒否 | 15分でCSRF拒否が5件以上 | cookie属性、hidden token、複数タブ、期限切れsession、外部フォーム投稿を確認する | Auth/UI担当 / HTML action logs |
| 403急増 | 15分で403が10件以上、または通常UIで急増 | RLS preflight、メールドメイン、cookie session、Bearer互換経路の混在を確認する | Auth/Backend担当 / auth logs, RLS read store logs |
| budget guardrail | 月次予算70%で注意、90%で新規OpenRouter実行を管理判断、100%で停止手順 | 期間内cost、token、model別内訳を確認し、上限到達時は新規生成を止めて既存編集/閲覧だけ許可する | Ops/PO / OpenRouter billing, `llm_call_logs`, budget alert |

残作業:

- Cloud Monitoring alert policyの実作成と通知先設定。少なくとも `monthly-report-staging-worker-manual-recovery`、`monthly-report-staging-worker-failed-spike`、`monthly-report-staging-worker-fetch-sources-stale` を作る。
- `llm_call_logs` から日次token / 概算費用を集計する定期jobまたは管理SQL。
- Google API quota / OAuth refresh失敗をstage別に集計するdashboard。
- budget guardrail到達時に新規OpenRouter実行を止めるfeature flagまたは管理操作入口。

## 監査ログ

保存対象:

- ログイン
- ジョブ作成
- ソース取得
- 生成開始
- 再生成
- 成果物編集
- フィードバック保存
- 管理者設定変更

## データ保持

| データ | 保持期間 |
|---|---:|
| ジョブメタ | 3年 |
| 生成Markdown / 最終編集Markdown | 3年 |
| ソーススナップショット | 1年 |
| LLMメタ / 検証結果 / フィードバック | 3年 |
| Cloud Logging構造化ログ | 6か月 |
| OAuthトークン | 利用中のみ |

保持期間到来時は物理削除を基本とする。品質集計に必要なメタデータのみ、個人・世帯・ソースを特定できない形に匿名化して残せる。

保持期間削除は運用ジョブとして実装する。対象はソーススナップショット、生成物、検証結果、フィードバック、LLMメタ、OAuthトークンで、削除前の対象件数ドライラン、削除後の件数確認、監査ログ記録を必須にする。退職・連携解除・管理者削除時のOAuth credential削除も同じrunbookに含める。

### 保持期間削除runbook（P2-12第一弾）

初期実装は `src/eb_app/monthly_reports/retention.py` の planner / executor を正とする。実行対象は allowlist で固定し、任意テーブル名や任意SQLを外部入力から受け取らない。

Cloud Run Jobs / 手動実行の入口は `python -m eb_app.monthly_reports.retention_entry` とする。既定はdry-runで、物理削除は `--delete --confirm-total-eligible-count <dry-runで確認した総対象件数>` を明示した場合だけ実行する。必要なら `--post-delete-expected-total-eligible-count <削除後に残る想定件数>` で削除後再dry-runの期待値も固定し、監査ログの actor は `--actor-id <ops-user-or-job>` で上書きできる。`--delete` だけでは `delete_confirmation_required` で非0終了し、直前dry-runの `total_eligible_count` と確認件数が一致しない場合も `delete_confirmation_mismatch` で削除しない。`--post-delete-expected-total-eligible-count` は `--delete` と組み合わせない限り拒否する。`EB_MONTHLY_REPORT_DATABASE_URL` が未設定、または実行失敗時はPII-safeなJSON error summaryを標準出力へ出し、非0終了する。

1. dry-runを実行し、`sources`, `artifacts`, `validations`, `feedback`, `llm_call_logs`, `jobs` の対象件数を確認する。dry-run結果は `audit_logs` に `monthly_report_retention_dry_run` として保存し、本文・ソース本文・世帯キー・OAuth tokenはmetadataへ入れない。
2. 件数が想定範囲であることを管理者が確認する。特に `sources` は1年、その他のジョブ/成果物/検証/フィードバック/LLMメタは3年の保持期間で判定する。
3. delete実行時は、dry-run JSONの `total_eligible_count` を `--confirm-total-eligible-count` に渡す。entryは削除直前にもう一度dry-runを行い、現在の総対象件数が確認件数と一致した場合だけ、同じplannerの順序で物理削除する。削除結果は `audit_logs` に `monthly_report_retention_delete` として、target別件数とcutoffのみを保存する。
4. 削除後は再度dry-runし、対象件数が0または `--post-delete-expected-total-eligible-count` で指定した想定残件数まで減っていることを確認する。
5. Supabase Storageへ本文・成果物を移した後は、Postgres metadata削除とStorage object削除を同一runbookへ追加する。それまではPostgres内の対象テーブルのみを削除対象とする。

実行例:

```bash
python -m eb_app.monthly_reports.retention_entry
python -m eb_app.monthly_reports.retention_entry --delete --confirm-total-eligible-count 12
python -m eb_app.monthly_reports.retention_entry --delete --confirm-total-eligible-count 12 --post-delete-expected-total-eligible-count 0 --actor-id ops-retention-manual
python -m eb_app.monthly_reports.retention_entry
```

OAuth credential削除は保持期間の定期削除とは分け、連携解除・退職・管理者削除のイベントで即時実施する。対象ユーザーを確認したうえで `google_oauth_credentials` の該当 `user_id` / `provider=google` を削除または `revoked_at` 付きで無効化し、`audit_logs` に `google_oauth_credential_deleted` または `google_oauth_credential_revoked` を記録する。監査metadataには `user_id_hash`, `provider`, `reason`, `deleted_count` だけを入れ、refresh token平文、暗号文、scope全文、client secret、Google APIレスポンス本文は入れない。Google側のアプリ連携解除が必要な場合は、管理者がGoogle Workspace / Google Accountの接続済みアプリ画面で失効を確認し、その結果だけを監査ログへ残す。

Supabase Storageへ成果物を移す場合は、bucket policy、オブジェクトprefix、signed URLの有効期限、配布用エクスポートの閲覧期限、保持期間到来時のStorage削除バッチをPostgresメタデータと同時に設計する。

## LLM入力安全

Google Docs/Sheetsから取得した本文は、ユーザーや教師が書いたデータであっても信頼済み命令として扱わない。promptではソース本文を「根拠データ」として区切り、システム指示・開発者指示・本文規約を上書きできないことを明示する。プロンプトインジェクションらしい文言、対象外生徒の混入、送付禁止語、内部メモの配布面露出は検証対象にする。

家庭向け送付・エクスポート前には人間承認ゲートを置く。生成成功、検証OK、編集保存済み、承認済み、送付/エクスポート済みを同一状態として扱わない。

## 未決事項

なし。上記のCookie+CSRF、RLS主境界、worker lease、保持期間削除、Storage policy、LLM入力安全は実装追跡事項として [development-plan.md](development-plan.md) で管理する。

## 受け入れ条件

- フロントにAPIキーやSAキーが露出しない。
- PIIをCloud Loggingへ出さずに調査できる。
- 403/429/失敗ジョブの運用が定義されている。

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-13 | 初版作成 |
| 2026-05-14 | Google Workspace REST API疎通用 `EB_GOOGLE_WORKSPACE_ACCESS_TOKEN` のローカル限定扱いを反映 |
| 2026-05-14 | Google provider refresh tokenのFernet暗号化保存とOAuth token refresh境界を反映 |
| 2026-05-14 | Google provider refresh token保存APIの責務と秘匿方針を反映 |
| 2026-05-14 | Supabase session経由のGoogle provider refresh token保存ブリッジとuser id一致チェックを反映 |
| 2026-05-14 | Supabase JWT secretによるBearer token検証、audience、許可ドメイン、Secret扱いを反映 |
| 2026-05-15 | provider/email/scope検証を含むSupabase session保存ブリッジとPII/secret外向きエラー抑止テストを反映 |
| 2026-05-15 | 非mock環境のジョブ所有者決定と一般ユーザーアクセス制限を反映 |
| 2026-05-15 | 月次レポート主要テーブルのRLS有効化と所有者ベースpolicyを反映 |
| 2026-05-15 | Cloud Logging向け構造化ログallowlistと実ログ出力のPII/secret抑止検査を反映 |
| 2026-05-15 | ライブE2E前設定ガイドへの参照とSupabaseリージョン選定方針を追加 |
| 2026-05-16 | 本番UIのCookie+CSRF、RLS主境界、service role限定、worker lease、保持期間削除、Storage policy、監視、LLM入力安全、人間承認ゲートを反映 |
| 2026-05-17 | MVP初期のworker entry/runbookを追加し、Cloud Run Jobsまたは手動実行での1件/複数件処理、必須環境変数、終了コード、manual recovery境界を明記 |
| 2026-05-17 | provider call中のbest-effort worker heartbeat実装に合わせ、stale reclaim対象とmanual recovery境界を更新 |
| 2026-05-17 | P2-13 CI第二弾として、secret不要のmigration/static schema/RLS guardrailとmanual dispatch限定のCloud Run smoke方針を追加 |
| 2026-05-17 | MVPは本番のみへ戻し、staging / production の2環境分離は本番ポータル合流タイミングで用意する方針へ修正 |
| 2026-05-17 | Supabase callback bridgeで検証済みaccess tokenからHTTPOnly auth session Cookieをセットする移行スライスを反映 |
| 2026-05-17 | P2-12第一弾として保持期間削除planner/executor、dry-run/delete監査ログ、OAuth credential削除runbookを追加 |
| 2026-05-17 | P2-14第一弾としてMVP監視runbookを追加。Cloud Run、worker、OpenRouter、Google API/OAuth、429/CSRF/403、費用上限のmetric・alert・初動・確認場所を整理 |
| 2026-05-17 | P2-10後段stuck job運用として、`manual_recovery_required` summaryと非0終了、手動回復時の確認項目を追加 |
| 2026-05-17 | P2-10後段stuck jobの手動回復runbookを、検知、安全確認、retry/requeue/cancel判断、監査、保持削除連動、エスカレーションまで具体化 |
| 2026-05-18 | P2-10 Cloud Run Jobs smoke/runbook接続として、worker jobの作成/更新/実行例、期待JSON summary、`manual_recovery_required` 非0終了、GitHub ActionsのHTTP smokeとの役割分担を追加 |
| 2026-05-18 | P2-14第二弾としてログベースmetric名・label・filter、alert threshold、日次token/cost summary contract、budget guardrail停止手順を固定 |
| 2026-05-19 | P2-10/P2-14運用導線として、worker smoke・manual recovery・stuck fetch_sources を Cloud Monitoring alert policy と runbook に結ぶ最小構成を追記 |
| 2026-05-18 | P2-12第二弾として、保持期間削除entryの `--delete --confirm-total-eligible-count` 契約、直前dry-run再照合、件数不一致時の非破壊終了を追加 |
| 2026-05-18 | MVPからstaging / productionの環境分離を設計対象へ戻したうえで、今回プロジェクトの完了条件はstaging動作確認までとし、production昇格は後続スコープへ分離 |
