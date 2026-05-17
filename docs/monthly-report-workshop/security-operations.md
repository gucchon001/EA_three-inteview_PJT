# セキュリティ・運用設計書

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツールのセキュリティ・運用設計
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- 関連文書: `requirements.md`, `data-design.md`, `api-definition.md`
- 最終更新: 2026-05-17

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
- 管理者モックユーザーは `mock-admin@tomonokai-corp.com`、一般モックユーザーは `mock-user@tomonokai-corp.com` とする。
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

MVPのCloud Run環境は本番のみとする。本番リージョンは `asia-northeast1`（東京）とする。関連するArtifact Registry、Secret Manager、Cloud Logging / Monitoring、将来利用するCloud Tasks等も、原則として同リージョンまたは同一国内/近接リージョンに寄せる。

実Supabase Auth + Google OAuth + Google Workspace read flowのライブE2E前設定は [pre-e2e-setup.md](pre-e2e-setup.md) を参照する。Supabaseプロジェクトを新規作成する場合は、Cloud Runの東京リージョンとデータ所在方針に矛盾しないリージョンを選ぶ。

staging / production の2環境分離は、レポート工房を本番ポータルへ合流するタイミングで用意する。その時点では、ポータル本番反映前のmigration、RLS、Google OAuth、OpenRouter、HTML UI smoke、ライブE2Eをstagingで確認する。

| 環境 | 用途 | データ/Secret |
|---|---|---|
| local | 開発・focused test・必要時の実機OAuth E2E | `.env` とローカルSupabase。実値はログ・文書へ出さない |
| MVP production | レポート工房MVPの実運用 | production用Supabase、production用Secret、実データ |
| portal staging | 本番ポータル合流前のE2E、migration、RLS、OAuth、OpenRouter smoke | portal staging用Supabase、staging用Secret、テストDocs/Sheets |
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

本番ポータル合流時にstaging / productionで分けるもの:

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

必須環境変数:

- `EB_MONTHLY_REPORT_DATABASE_URL`
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL_REPORT`
- `EB_MONTHLY_REPORT_PROMPT_VERSION`
- `EB_APP_VERSION` または Cloud Run の `K_REVISION`

任意環境変数:

- `EB_WORKER_OWNER_USER_ID`: 特定ユーザー/検証ジョブだけを拾う場合に指定
- `EB_WORKER_LEASE_TIMEOUT_SECONDS`: stale `running/fetch_sources` jobの再claim判定
- `EB_WORKER_MAX_JOBS`: 1実行で処理する最大job数。既定は1、0はno-jobまで継続
- `EB_WORKER_SLEEP_SECONDS`: ループ時のsleep秒数

実行例:

```powershell
python -m eb_app.monthly_reports.worker_entry --max-jobs 1 --lease-timeout-seconds 900
```

出力は `status`, `claimed_job_id`, `job_id`, `job_status`, `error_type` のJSON summaryに限定し、`error_message` やprovider本文は出さない。`failed` が含まれる場合は非0終了とし、Cloud Run Jobs側の失敗検知に使う。

現時点では、blockingなOpenRouter呼び出し中の真のmid-call heartbeatは未実装。`touch_worker_job` はclaim後・実行前のheartbeatであり、後段stageのstuck reclaim拡張は、artifact / validation / llm_call_logs の冪等性が揃ってから行う。

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

監視・アラート:

- Cloud Runの5xx率、timeout率、p95/p99レイテンシ、メモリ逼迫
- `monthly_report_jobs` のfailed率、stuck running件数、retry上限到達件数
- OpenRouter token使用量、概算費用、provider timeout/error率
- Google API quota/error率、OAuth refresh失敗率
- 429発生件数、CSRF拒否件数、403/404の急増

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
| 2026-05-17 | MVP初期のworker entry/runbookを追加し、Cloud Run Jobsまたは手動実行での1件/複数件処理、必須環境変数、終了コード、mid-call heartbeat未実装条件を明記 |
| 2026-05-17 | MVPは本番のみへ戻し、staging / production の2環境分離は本番ポータル合流タイミングで用意する方針へ修正 |
| 2026-05-17 | Supabase callback bridgeで検証済みaccess tokenからHTTPOnly auth session Cookieをセットする移行スライスを反映 |
