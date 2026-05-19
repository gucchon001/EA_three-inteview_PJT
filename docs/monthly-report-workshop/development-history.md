# 開発履歴

## 位置づけ

- 正本/補助資料の区分: `development-plan.md` から分離した詳細な進捗ログ・改訂履歴
- 起点: [development-plan.md](development-plan.md)
- 関連文書: [verification-log.md](verification-log.md), [decision-log.md](decision-log.md)
- 最終更新: 2026-05-17

## 運用ルール

- 現在の優先順位、フェーズ、未完了タスクは [development-plan.md](development-plan.md) を正とする。
- この文書は、過去の詳細な実装ログと改訂履歴を保存するための補助資料とする。
- 新しい日次レベルの細かい作業ログは必要な場合だけ追記し、計画本文には現在状態と次アクションだけを残す。

## 詳細な現在位置ログ（移動前の現在位置）

2026-05-16時点では、移行計画書から開発ドキュメント初版を作成し、MVP実装の土台に着手済み。2026-05-16の方針レビューで、HTML断片UI、Cookie+CSRF、Supabase RLS主境界、Cloud Run worker lease、冪等性、Storage/保持削除、監視、プロンプトインジェクション対策、人間承認ゲートをMVP前後の横断ゲートとして追加した。

実装済み・確認済みの範囲:

- FastAPIへ月次レポートAPIスタブを登録済み: `POST /api/monthly-reports/jobs`, `GET /api/monthly-reports/jobs`, `GET /api/monthly-reports/jobs/{job_id}`, `POST /api/monthly-reports/jobs/{job_id}/cancel`
- ジョブ状態モデル、prefix付き公開ID、モックジョブストアを実装済み
- `EB_ENABLE_MOCK_UI=1` のときに、レポート工房のジョブ一覧・新規作成・詳細・推敲エディタ・status fragment のモックUIを表示可能
- ローカル開発用モック認証の基本ユーザーを実装済み
- 非mock環境向けにSupabase JWT secretによるBearer token検証を実装済み。`aud=authenticated`、メールドメイン `tomonokai-corp.com`、不正token 401、ドメイン外 403、secret未設定 503 を確認済み
- 非mock環境ではジョブ作成時の `owner_user_id` をJWT `sub` から決め、一般ユーザーの一覧・詳細・成果物・検証・LLM呼び出しログ・stage操作を自分のジョブに制限する境界を実装済み。ローカルmockでは従来どおり全件参照を許可
- Supabase Postgres向け初期migrationとRLS migrationを作成済み。主要テーブルでRLSを有効化し、ジョブ所有者・credential所有者ベースのpolicyを静的テストで確認済み
- 2026-05-16の方針更新により、RLSは将来統合用の補助境界ではなく主境界として効かせる方向へ寄せる。通常ユーザーリクエストではユーザーJWT付きSupabase Clientを第一候補とし、service role/direct DBはworker・管理・migration・保持期間削除に限定する計画へ更新済み
- Supabase CLIでローカルDBを起動し、初期migrationを適用済み。WindowsのAnalytics health checkを避けるため、ローカル設定ではAnalyticsを無効化
- `EB_MONTHLY_REPORT_DATABASE_URL` 設定時に、月次レポートAPIがPostgres storeを使う経路を実装済み
- 明示的なジョブ進行APIを実装済み: `POST /api/monthly-reports/jobs/{job_id}/start`, `POST /api/monthly-reports/jobs/{job_id}/complete-stage`, `POST /api/monthly-reports/jobs/{job_id}/fail`
- Mock/Postgres storeで `queued -> running -> succeeded` のstage進行と、失敗時の `failed`・`error_type`・`error_message` 記録を実装済み。Postgresでは `monthly_report_jobs.error_type` / `error_message` に失敗詳細を明示保存し、監査ログにも失敗イベントを残す
- ソーススナップショットと生成成果物の保存/一覧APIを実装済み。Mock storeとPostgres storeの両方で `monthly_report_sources` / `monthly_report_artifacts` へ接続する最小経路を確認済み
- Google Workspace REST APIクライアントを追加済み。`gws` CLIには依存せず、Docs API / Sheets APIから取得した本文・valuesをソーススナップショットとして保存する `POST /api/monthly-reports/jobs/{job_id}/fetch-google-sources` を実装済み。ローカル疎通はサーバ側 `EB_GOOGLE_WORKSPACE_ACCESS_TOKEN` のみで行い、リクエストbodyやエラー本文には出さない
- Google provider refresh tokenのFernet暗号化保存境界とPostgres `google_oauth_credentials` upsertを実装済み。保存済みrefresh tokenからGoogle OAuth token endpointでaccess tokenを再取得し、`/fetch-google-sources` に渡せる解決経路を追加済み
- 認証済みユーザーに紐づくGoogle provider refresh token保存API `POST /api/auth/google-oauth/credentials` を追加済み。Supabase Auth callbackで取得したrefresh tokenを、このAPI経由で暗号化保存する前提
- Supabase session由来のGoogle provider refresh token保存ブリッジ `POST /api/auth/google-oauth/supabase-session` を追加済み。payloadのSupabase user id、provider、provider email、refresh token、scopeをサーバ側adapterで検証し、現在ユーザーID/メールと一致する場合だけ保存する。refresh tokenはrepr/レスポンス/エラー本文に出さない
- ライブE2E用の開発画面 `/monthly-report-workshop/e2e` を追加済み。Supabase sessionのBearer tokenでジョブ作成、Google source取得、OpenRouter実行、sources/artifacts/validations/llm-calls確認を1画面から順に実行できる
- 2026-05-16の方針更新により、Bearer token前提のE2E画面は移行期/検証用として維持しつつ、通常UIは `/monthly-reports/*` のHTMLページ/HTML断片、HTTPOnly/Secure/SameSite Cookie + CSRFへ寄せる
- 通常UIの第一弾として、`/monthly-reports`, `/monthly-reports/jobs`, `/monthly-reports/jobs/new`, `POST /monthly-reports/jobs`, `/monthly-reports/jobs/{job_id}`, `POST /monthly-reports/jobs/{job_id}/run`, `/monthly-reports/jobs/{job_id}/fragments/status`, `/monthly-reports/jobs/{job_id}/fragments/sources`, `/monthly-reports/jobs/{job_id}/fragments/preview`, `/monthly-reports/jobs/{job_id}/fragments/validation`, `POST /monthly-reports/jobs/{job_id}/fragments/sources`, `POST /monthly-reports/jobs/{job_id}/fragments/google-sources`, `POST /monthly-reports/jobs/{job_id}/fragments/feedback` を追加済み。ジョブ一覧・作成・詳細・ソース確認/手動保存/Google取得・生成開始・モック生成完了・OpenRouter生成・status/preview/validation/feedback fragmentはHTMLを返し、通常UIから `/api/monthly-reports/*` をDOM更新目的で使わないテストを追加済み
- HTML actionの第一弾として、`POST /monthly-reports/jobs`, `POST /monthly-reports/jobs/{job_id}/run`, `POST /monthly-reports/jobs/{job_id}/fragments/sources`, `POST /monthly-reports/jobs/{job_id}/fragments/google-sources`, `POST /monthly-reports/jobs/{job_id}/fragments/feedback` にCSRF token検証を追加済み。`GET /monthly-reports/jobs/new` と `GET /monthly-reports/jobs/{job_id}` は `HTTPOnly`, `SameSite=Lax`, `/monthly-reports` pathのCSRF cookieとhidden inputを発行し、非local環境では `Secure` を付ける。既存cookieがある場合は再利用し、tokenなしPOSTはHTML error fragmentで403を返す
- 検証結果の保存/一覧APIを実装済み。`monthly_report_validations` へ保存し、Mock/Postgres/API経由で確認済み
- ジョブ作成時に `prompt_version`, `template_hash`, `resolved_model_report`, `source_bundle_hash`, `app_version` などの再現性メタを保存・返却する経路を実装済み
- 月次レポートAPIに認証依存関係を接続済み。ローカルmockは固定ユーザー、非mockはSupabase JWT secretでBearer tokenを検証する
- 3件同時実行制限はStore側の `create_job_with_active_limit` へ寄せ、Postgresではユーザー単位のadvisory lockを使う経路を実装済み
- 編集画面に成果物保存パネルと `app_version` 表示を追加済み
- 再生成ジョブは対象月・世帯・作成者に加えて、template / prompt / model / source bundle / app version の再現性メタを引き継ぐ
- 静的POCの `build_prompts` を `src/eb_app/monthly_reports/llm_messages.py` へ共通化し、CLIは薄いラッパとして同じ関数を呼ぶ形に変更済み
- `prompt_scope_notes` をジョブ作成API、HTML新規作成フォーム、Mock/Postgres store、再生成コピー、レスポンスに追加済み。静的レシピ `prompts.scope_reminder` から工房ジョブ投入用 `prompt_scope_notes` への変換helperも追加済み。ローカルSupabaseには `202605140002_add_monthly_report_prompt_scope_notes.sql` を適用済み
- `src/eb_app/monthly_reports/workflow.py` で `build_messages -> provider mock -> validate -> persist` を1ジョブ通電済み。開発用API `POST /api/monthly-reports/jobs/{job_id}/run-mock` からも通せる
- OpenRouter APIキーのキー情報エンドポイント疎通は確認済み。OpenRouter `chat/completions` 用provider抽象はHTTPモックで実装済み。工房本体の `POST /api/monthly-reports/jobs/{job_id}/run-openrouter` から実ネットワーク通電し、`succeeded` / `draft_markdown` / `non_empty_markdown` 保存まで確認済み
- `llm_call_logs` へLLM呼び出しメタを保存する経路を実装済み。Mock/Postgres storeと `GET /api/monthly-reports/jobs/{job_id}/llm-calls` で、本文・プロンプト全文を出さずにhash、requested/resolved model、token、finish reason、error_typeを確認できる
- 非同期実行へ進める前段として、Store共通の `claim_next_queued_job()` と `src/eb_app/monthly_reports/worker.py` の `run_next_queued_monthly_report_job()` を実装済み。Postgresでは `FOR UPDATE SKIP LOCKED` で最古のqueued jobを原子的にclaimし、claim済みjobは `run_claimed_monthly_report_job()` で二重startせず実行する。worker入口には `owner_user_id` filterを追加し、同一DB内の別ユーザー/別E2E残ジョブを拾わない実行単位を指定できる
- Cloud Run worker本番化は、lease timeout、heartbeat/updated_at、stale `fetch_sources` 再claim、再試行上限、手動再実行入口、協調的キャンセル、主要POST系Idempotency-Keyまで実装済み。後段stage stuck jobは自動再claimせず、worker entryの `manual_recovery_required` summaryと非0終了で運用検知する。保持削除/監査と連動した手動回復runbookは `security-operations.md` に具体化済み。残りは実Cloud Run smoke結果の記録、監視alertとの接続、必要なら管理操作入口の実装
- Economics 複数生徒MTGの匿名化フィクスチャを `tests/fixtures/monthly_reports/economics_multistudent_scope/` に追加し、`prompt_scope_notes` が根拠ソースより前にプロンプトへ入る回帰テストへ接続済み
- 決定的バリデーション `required_headings`, `forbidden_terms`, `multistudent_scope_exclusion` の第一弾を実装済み。テンプレートから抽出した `## 01...` 形式の必須見出し欠落、配布面禁止語、または `prompt_scope_notes` に明記された `対象外...様` のdraft混入がある場合、artifact保存前に `validation_failed` として停止する
- 静的POCの `HANDOFF_STATIC_POC_TUNING.md` をP0/P1/P2へ組み込み、`build_prompts` の塊順を工房側 `build_messages` の実装前提に追加済み
- クラウド本番リージョンは `asia-northeast1`（東京）を基本とする方針を決定済み
- 2026-05-16 ライブE2E通電完了: ローカル Supabase Google provider ログイン → `provider_refresh_token` 取得 → `/api/auth/google-oauth/supabase-session` 経由でFernet暗号化保存（`google_oauth_credentials.encrypted_provider_refresh_token` 228byte、`encryption_key_version=local-v1`）→ 月次レポートジョブ作成 → `fetch-google-sources` → `run-openrouter` → 決定的バリデーション → 失敗時 `monthly_report_jobs.error_type=validation_failed` + `monthly_report_validations` 保存 → `llm_call_logs` に `resolved_model=anthropic/claude-4.6-sonnet-...` / token / hash 記録、まで実ブラウザで通電
- 2026-05-16 ローカル Supabase Auth の Google provider 設定を `supabase/config.toml` の `[auth.external.google]` ブロック + `additional_redirect_urls` に `http://127.0.0.1:8000/auth/callback` 追加 + `enable_signup = true`（初回 Google ログインを signup 扱いで通すため）で実装。Google Cloud Console 側は OAuth consent + Web client（redirect URI `http://127.0.0.1:56321/auth/v1/callback`）を手動作成。Docs/Sheets/Drive API は `gen-lang-client-0360012476` で有効化済み
- 2026-05-16 FastAPI の Supabase JWT 検証を JWKS 経由の ES256/RS256 対応に拡張。`src/eb_app/auth/dependencies.py` で `alg` ヘッダを見て HS256 は symmetric secret（テスト互換）、ES256/RS256 は `<SUPABASE_URL>/auth/v1/.well-known/jwks.json` から取得した公開鍵で検証する。ローカル Supabase が新 signing keys（ES256）で発行する access token が `Bearer` 検証を通過することを実機確認済み
- 2026-05-16 ライブE2E結果のジョブレスポンスで `prompt_version`, `template_hash`, `model_report`, `resolved_model_report`, `source_bundle_hash`, `app_version` が null のまま返ることを確認。`llm_call_logs` には `resolved_model` が記録されているため、`/run-openrouter` 経由でジョブ本体（`monthly_report_jobs`）への再現性メタ書き戻しが未実装の状態。Phase 1 完了条件にギャップあり
- 2026-05-16 P1-17として、`OPENROUTER_MODEL_REPORT`, `EB_MONTHLY_REPORT_PROMPT_VERSION`, `EB_APP_VERSION` / `K_REVISION` / `GITHUB_SHA` 由来の既定値を設定へ追加し、`/run-openrouter` / `/run-mock` 実行前に欠けている `prompt_version`, `model_report`, `app_version` をジョブへ書き戻す経路を追加済み。さらに `run_next_queued_monthly_report_job()` / `run_claimed_monthly_report_job()` も同じ既定メタを受け取れるようにし、Cloud Run worker化時に設定値を注入できる入口を用意した。`template_hash`, `source_bundle_hash`, `resolved_model_report` はworkflow内の既存書き戻しを利用する。Mock store/API/worker focused、Postgres worker focused、2026-05-17ライブE2E初succeededでジョブ本体への永続化とレスポンス非nullを確認済み
- 2026-05-16 P1-18として、Supabase AuthのES256/RS256 JWKS検証経路をfocused testで固定済み。PyJWKClient相当のfakeから公開鍵を返し、ES256/RS256署名tokenが `/api/monthly-reports/jobs` を通過すること、JWKS tokenで `SUPABASE_URL` がない場合は503になることを確認済み。既存HS256 secret検証テストも併走する
- 2026-05-17 ライブE2E再確認: ローカル Supabase Google provider の保存済みrefresh tokenからGoogle access tokenを再取得し、実Google Docs 1件 + Sheets 2 rangeを `fetch-google-sources` で保存（3 sources）→ `run-mock` でartifact/validation/llm_call_logs保存 → `.env` の `OPENROUTER_API_KEY` / `OPENROUTER_MODEL_REPORT` を確認後、別ジョブで `run-openrouter` を実行し `status=succeeded`、`resolved_model_report=anthropic/claude-4.6-sonnet-20260217`、再現性メタ非null、artifact 1件、validation 2件、llm_call_logs 1件を確認済み。`.env` のOpenRouter設定確認では `^OPENROUTER_` 前方一致で見ること（`^(OPENROUTER_)=` のような誤った正規表現は `OPENROUTER_API_KEY` を拾えない）
- 2026-05-17 P1-16第一弾として、`CurrentUser` に検証済みSupabase access tokenを保持し、`src/eb_app/auth/supabase_client.py` にユーザーJWT付きSupabase anon client生成ヘルパーを追加済み。あわせて `src/eb_app/monthly_reports/rls.py` にPostgres `authenticated` role + `request.jwt.claim.sub` でRLSを評価するテスト用セッションヘルパーを追加し、実DBで「自分のjob/sourceのみ見える」「他ユーザー名義insertはRLSで拒否」「audit_logsはクライアント不可」を確認済み。通常APIの全面置換は後続で、direct DBはworker・管理・migration・保持削除に限定していく
- 2026-05-17 P1-16第二弾として、通常ユーザーの読み取り系を段階的にRLS経由へ寄せるため、ユーザーJWT付きSupabase clientを使う `SupabaseMonthlyReportReadStore` を追加し、JSON APIの `GET /jobs`, `GET /jobs/{job_id}`, `GET /sources`, `GET /artifacts`, `GET /validations`, `GET /llm-calls` と通常UI一覧の読み取りをRLS read store優先へ変更。mock/admin/設定不足時は既存storeへフォールバックし、書き込み・worker・管理系は次段階までdirect DBを維持する
- 2026-05-17 P2-09第一弾として、`POST /api/monthly-reports/jobs` と `/run-mock` / `/run-openrouter` に `Idempotency-Key` 対応を追加。ジョブ作成の二重送信は同一jobを返し、active limitを二重消費しない。生成開始の二重送信は同一キーなら初回応答を返す。さらに `monthly_report_idempotency_keys` migrationとPostgres store lookup/rememberを追加し、Cloud Run複数インスタンス/再起動でも永続化できる入口を用意した。migrationはローカル実DBへ適用し、Postgres focused testも通過済み
- 2026-05-17 P2-10第一弾として、workerに `WorkerRunResult` / `WorkerRunStatus` を追加し、既存 `run_next_queued_monthly_report_job()` の戻り値互換を保ったまま、claim後の実行サマリとprovider実行前キャンセル境界をfocused testで固定。さらにworker attempt/lease migration、stale `running/fetch_sources` 再claim、retryable failureのqueued復帰を実DB focused testで固定済み
- 2026-05-17 P3-01/P3-02として、通常UI詳細画面に `/monthly-reports/jobs/{job_id}/rerun` と `/monthly-reports/jobs/{job_id}/fragments/edited-markdown` 向けHTMXフォームを追加し、backend routeも実装。編集後Markdownは `final_markdown` artifactとして保存し、再生成actionは新しいqueued jobのstatus fragmentを返す。編集内容prefill、差分表示、再現性メタ比較は後続
- 2026-05-17 環境方針を一度「MVPは本番のみ、本番ポータル合流時にstaging / production分離」へ戻したが、2026-05-18に再更新し、MVPからstaging / productionの2環境を用意する方針へ変更した
- 2026-05-17 P2-09の `monthly_report_idempotency_keys` migrationをローカル実DBへ適用し、Postgres focused testで永続冪等性のlookup/rememberを確認済み
- 2026-05-17 P1-16第三弾として、通常HTML UIのGET detail/status/preview/sources/validation fragment読み取りをRLS read store優先へ移行。書き込み系HTML actionは次段階までdirect storeを維持する
- 2026-05-17 P2-09追加として、新規ジョブ作成フォームと生成開始フォームにhidden `idempotency_key` を追加し、HTML actionの二重送信をfocused testで固定。生成開始HTML actionは同一job/run_mode/idempotency_keyなら初回job状態を返す
- 2026-05-17 P2-10追加として、`worker_attempts`, `max_worker_attempts`, `worker_last_claimed_at` migrationを追加し、実DBへ適用済み。`claim_next_runnable_job()` でqueued jobとlease timeout後のstale `running/fetch_sources` jobをclaimでき、retryable failureは上限までqueuedへ戻す。Postgres focused testも実DBで通過済み
- 2026-05-17 P2-09追加として、source保存とGoogle source取得のJSON API/HTMX actionにIdempotency-Keyを追加。Google取得は同一キー再送時にGoogle Workspace APIを再実行せず、保存済みsources fragment/JSON responseを返す
- 2026-05-17 P2-10追加として、claimed worker jobのheartbeat/touch primitiveをMock/Postgres storeへ追加し、worker実行前に `updated_at` / `worker_last_claimed_at` を更新できるようにした。stale reclaim拡張前の誤回収防止をfocused testで固定
- 2026-05-17 P2-10追加として、stale reclaim対象を `fetch_sources` stageに限定するworker-facing protocolを明文化し、`call_llm` 以降の後段stageは古い `worker_last_claimed_at` でも自動再claimしないfocused testを追加。さらに `lease_timeout_seconds` 指定時はworker実行中にbest-effort heartbeatを継続し、遅いprovider call中もleaseを更新する。後段stageの再claimは成果物・検証・LLMログの冪等性が揃ってから解禁する
- 2026-05-17 P1-16第四弾として、HTML write actionのうち編集後Markdown保存と再生成でRLS read-store preflight認可を追加。実writeは既存direct storeのまま維持し、full RLS write化はP2-09完了後に回す
- 2026-05-17 P2-09追加として、artifact保存、feedback保存、編集後Markdown保存のJSON API/HTMX actionにIdempotency-Keyを追加。同一キー再送時は初回artifact/feedback/final_markdownだけを返し、二重保存しないfocused testを追加
- 2026-05-17 P2-09追加として、JSON APIのvalidation保存にもIdempotency-Keyを追加。同一キー再送時は初回validation responseを返し、severity/message違いの二重登録を防ぐ
- 2026-05-17 P2-10追加として、`python -m eb_app.monthly_reports.worker_entry` のCloud Run worker entryを追加。Postgres + OpenRouter設定から1件/複数件のqueued jobを処理し、PIIを含まないJSON summaryと失敗時非0終了を返す。runbookは `security-operations.md` に追記
- 2026-05-17 P2-10追加として、lease timeout超の後段 `running` jobがある場合にworkerが自動再claimせず `manual_recovery_required` summaryを返す境界を追加。summaryは `job_id`, `job_stage`, 件数、stage一覧だけに絞り、`error_message` や本文を出さない。Cloud Run Jobsでは非0終了で検知する
- 2026-05-17 P2-10追加として、stuck後段stageの手動回復runbookを `security-operations.md` に具体化。検知、構造化フィールドだけを見る安全確認、stage別のretry/requeue/cancel判断、監査ログmetadata、保持期間削除との相互作用、PII/secret漏えい時と多発時のエスカレーションを明記した
- 2026-05-17 P1-16第五弾として、HTML write actionのうちsource保存、Google source取得、feedback保存、生成開始にもRLS read-store preflight認可を追加。通常HTML UIの主要write actionはpreflight済みになった。実writeは既存direct storeのまま維持し、full RLS write化とdirect DB用途棚卸しを次段階へ回す
- 2026-05-17 P1-16第六弾として、通常ユーザー向けJSON write API（source/artifact/validation/feedback、Google source取得、start/complete/fail/cancel、run-mock/run-openrouter、rerun）にもRLS read-store preflight認可を追加。JSON読み取り・HTML読み取り・主要write preflightはRLS経由になり、残るdirect DBは実write本体、worker、管理、migration、保持削除、E2E/内部互換APIの境界棚卸しへ進む
- 2026-05-18 P1-16第七弾として、feedback保存を最初のfull RLS write POCに変更。通常Supabaseユーザーはuser-JWT Supabase client経由で `monthly_report_feedback` へinsertし、mock/adminはdirect fallbackを維持する。HTML feedbackとJSON feedbackのfocused testで、RLS store `record_feedback` 経由を確認済み
- 2026-05-17 P2-13第一弾として、`.github/workflows/monthly-report-operational-guardrails.yml` を追加。PR/pushではSupabase Dockerや実Secretなしで、migration SQLの危険操作静的チェック、RLS policy存在確認、schema/PII/logging/worker entry focused testを実行する。Cloud Run smokeは `workflow_dispatch` の `run_cloud_run_smoke=true` 時だけ動く手動ゲートとし、`CLOUD_RUN_SMOKE_URL` と任意の `CLOUD_RUN_SMOKE_BEARER_TOKEN` repository secretがある場合だけHTTP 2xx/3xxを確認する
- 2026-05-17 P2-12追加として、`python -m eb_app.monthly_reports.retention_entry` のCloud Run Jobs向けentryを追加。既定dry-run、`--delete` 明示時のみ物理削除、JSON summary、DB URL不足/失敗時の非0終了、PII-safe出力をsecret不要unit testで固定済み
- 2026-05-17 P3-06/P3-12第一弾として、ジョブ詳細に承認/HTMLエクスポートのGET fragment panelを追加。未生成・未承認などのブロック理由をHTML断片で表示し、通常UIからJSONをDOM更新目的で使わないことをfocused testで固定。POST保存・export artifact作成は後続
- 2026-05-17 P3-06/P3-12第二弾として、通常UIに `POST /monthly-reports/jobs/{job_id}/fragments/approval` と `POST /monthly-reports/jobs/{job_id}/fragments/export` を追加。承認はCSRF、RLS read preflight、Idempotency-Key、生成成功、validation errorなし、最新配布artifact hash一致を要求し、承認済みartifactからのみ `export_html` artifactを作成する
- 2026-05-17 P3-05第一弾として、通常UIに `GET/POST /monthly-reports/jobs/{job_id}/fragments/html-source` を追加。最新 `export_html` artifactをtextareaで表示し、CSRF、RLS read preflight、Idempotency-Key、空本文拒否、最新export hash一致を満たす場合だけ編集済みHTMLを新しい `export_html` artifactとして保存する
- 2026-05-17 P3-04第一弾として、HTMLソース編集fragmentにiframeプレビューと1行ツールバーを追加。export済みHTMLをソース編集しながら、同じ断片内で表示確認できる最小導線を用意した
- 2026-05-17 P3-07第一弾として、最新 `export_html` artifactを `GET /monthly-reports/jobs/{job_id}/download/export-html` からHTML attachmentとして保存できる導線を追加。未export時は404、通常UI distribution panelから保存リンクを出す
- 2026-05-17 P3-08第一弾として、通常UIに `GET/POST /monthly-reports/jobs/{job_id}/fragments/distribution` を追加。承認済みHTML exportを手動送付用 `distribution_package` artifactとして固定し、CSRF、RLS read preflight、Idempotency-Key、最新export hash一致を要求する。実メール送信はまだ行わない
- 2026-05-17 P3-03第一弾として、新規ジョブ作成UIに管理者向け `prompt_version` / `model_report` / `model_light` override欄を追加。一般ユーザーには表示せず、フォーム値を直接送られても保存しないため、通常利用ルートのチューニング権限をadminに限定した
- 2026-05-17 P3-03第二弾として、詳細画面の再生成フォームにもadmin限定の `rerun_prompt_version` / `rerun_model_report` / `rerun_model_light` override欄を追加。一般ユーザーには表示せず、フォーム値を直接送られても元ジョブのメタ継承に限定する。モデル変更時は `resolved_model_report` を空にして再解決対象にする
- 2026-05-17 P3-02/P3-03追加として、`GET /monthly-reports/jobs/{job_id}/fragments/rerun-comparison` を追加。比較先ジョブIDを指定すると、`prompt_version`, `template_key/hash`, `model_report/light/resolved`, `source_bundle_hash`, `app_version`, `prompt_scope_notes` を横並びで表示し、changed/sameをHTML断片で確認できる
- 2026-05-17 P3-13追加として、承認/export/html source/distributionの入力フォーム付きパネルは定期pollingをやめ、編集保存・承認・export成功時の `monthly-report-refresh` イベントで更新する方式に変更。入力途中のcheckbox/comment/textareaが再描画で消える事故を避ける
- 2026-05-17 P3-13追加として、共通HTMX補助断片に `htmx-error-banner` を追加。`htmx:responseError` / `htmx:sendError` / `htmx:timeout` を拾い、通信または処理失敗を画面下部のalertで表示する
- 2026-05-17 P3-10第三弾として、自己完結Playwright smokeをHTML exportで止めず、送付用 `distribution_package` 固定と `rerun-comparison` の比較フォーム送信まで拡張。HTMX stubも `form[hx-get]` を扱えるようにし、比較UIをブラウザ操作で確認する
- 2026-05-17 P3-10/P3-13追加として、自己完結Playwright smokeに詳細画面の実リロードを挟み、`status`, `final_markdown` preview/edit textarea, 承認状態, `export_html`, distribution導線が復元されることを確認する
- 2026-05-17 P3-13追加として、自己完結Playwright smokeに複数タブ編集競合シナリオを追加。Aタブ保存後、Bタブの古い `base_content_hash` による保存が409で拒否され、最新 `final_markdown` がAタブ内容のまま維持されることを確認する
- 2026-05-17 P3-11第一弾として、既存 `docs/samples/monthly-reports/tools/monthly_report_full_editor.html` を `/monthly-reports/legacy-full-editor` から同一オリジンで開ける互換ルートを追加し、HTMLソース編集パネルから「既存全文エディタ」へ接続した。まずは比較・手動検証用の導線で、artifactの自動投入は後続
- 2026-05-17 P3-11第二弾として、`/monthly-reports/jobs/{job_id}/legacy-full-editor` を追加。最新 `export_html` artifactを既存全文エディタのlocalStorageキーへUTF-8 base64 bridgeで投入し、`/monthly-reports/legacy-full-editor` へ遷移する。HTMLソース編集パネルから「exportを既存エディタで開く」導線を追加
- 2026-05-17 P3-13第一弾として、編集Markdown保存時にフォーム側の `base_content_hash` がある場合だけ最新preview artifact hashと比較し、別タブ保存などで古くなった編集保存を409で拒否する。生成前から開いていたフォームのようにbase hashが空の保存は通常操作として通し、Idempotency-Key再送は競合判定前に初回結果を返す
- 2026-05-17 Google Sheets通常UIをrange手入力から、Spreadsheet URL/IDだけで `student` と `lesson plan` の使用範囲全体を取得する方式へ変更。シート名が異なる場合に備え、Sheets API metadataからシート名一覧を取得して基本情報/学習計画表シートを選択する `sheet-selector` fragmentを追加
- 2026-05-17 文字起こし・Google Docs/Sheets取得後の確認導線として、通常UIに `取得内容を要約` HTMX actionを追加。保存済みsourcesをOpenRouter light modelで要約し、`取得内容サマリー`、`対象・期間・科目の確認`、`ズレ/不足の可能性` を表示する。結果は `source_summary_markdown` artifact と `llm_call_logs.prompt_kind=source_summary` として保存し、本文生成前の取り込みズレ確認に使う
- 2026-05-17 通常UI詳細画面のローカル手動検証で、空手動ソース保存、空Sheets URLのsheet-selector、succeeded jobへの生成開始、active job上限、ローディング状態を点検。空本文保存を422で止め、空ソースは要約対象から除外し、実Google Docs/Sheets取得後の要約が実データを読むことを確認。さらに `queued` 以外の生成ボタンをdisabled化し、再生成の二重押しをIdempotency-Keyで固定。共通HTMXローディングは `beforeSend` で開始し、キャンセルされたリクエストでボタンがdisabledのまま残らないよう修正
- 2026-05-17 P3-10第一弾として、手動Playwright検証を `tests/test_monthly_report_playwright_smoke.py` に再利用可能化。既定はskip、`MONTHLY_REPORT_PLAYWRIGHT_SMOKE=1` + `MONTHLY_REPORT_JOB_ID` でローカル実サーバのdetail画面を検証し、`MONTHLY_REPORT_SHEET_URL` がある場合はsheet-selector実行まで確認する
- 2026-05-17 P3-10第二弾として、secret不要の自己完結Playwright smokeを追加。テスト内でFastAPI/Uvicornを起動し、HTMXをローカルstubして、detail page → 手動ソース保存 → mock生成 → final Markdown保存 → 承認 → HTML exportまで連続確認する
- 2026-05-17 P1-11追加として、ジョブ一覧に次の操作、source/artifact件数、最新artifact種別/hash、validation error数を表示。詳細画面には現在位置サマリー、次の操作、ソース/成果物/承認/export状態、ショートカット導線を追加し、プレビューは `draft_markdown` / `final_markdown` の表示中種別を明示。編集保存フォームは最新preview artifactでprefillする
- 2026-05-17 P3-01/P3-02追加として、ジョブ詳細の「プレビュー / 編集」を2ペイン化。左に配布面プレビュー、右に編集Markdownを置き、`final_markdown` を優先表示、未保存変更、base hash、保存済み/ドラフト状態を表示する
- 2026-05-17 P1-14追加として、通常HTML UIに `POST /monthly-reports/jobs/{job_id}/cancel` を追加。CSRF、RLS read preflight、Idempotency-Keyを必須にし、queued/runningのみキャンセル可能、完了済みジョブはHTML error fragmentを返す。status fragmentにはerror_type/error_messageを表示する
- 2026-05-17 P2-11追加として、`Gemini メモ` / `Google Meetメモ` / Google生成メモ系の配布面メタ語彙をdraft artifact側で狭くsanitizationし、source evidence内の同語彙は許容するfocused testを追加済み
- 2026-05-17 P1-15追加として、`eb_auth_session` HTTPOnly Cookieから検証済みSupabase JWTを受ける移行ブリッジを追加。Bearer token互換はE2E/内部JSON向けに維持する。server-side session refresh/rotationは後続
- 2026-05-17 UIコンポーネント方針として、Tailwind CSS + DaisyUIをレポート工房の標準にし、FlowbiteはMVP標準依存にしないことを決定。業務画面はtable/section中心、カードは繰り返し単位に限定し、HTMX errorもDaisyUI alert断片で返す
- 2026-05-17 P3-14第一弾として、alert/status/validation/feedback/sources/preview fragmentsをDaisyUI `alert` / `badge` / `table` / `prose` 中心へ標準化。router/storeには触れずHTML UI focused testで通過
- 2026-05-17 Phase 2並行実装として、GitHub Actionsの安全なfocused pytest workflowを追加。実Google/OpenRouter secretやSupabase Dockerを要求せず、mock/test envで月次レポート主要テスト、Supabase user client、validation safetyを実行する
- 2026-05-17 P2-11第一弾として、生成draft側に残った明示的なプロンプトインジェクション文言と内部/管理メモ露出を決定的validationで検出し、`validation_failed` として停止する focused test を追加
- 2026-05-17 E2E画面でRLS/Google OAuth/OpenRouter成功サンプルを記録。job `mrj_2b15b194636a4457b590e3ef73afa5b2` は `/monthly-report-workshop/e2e` からGoogle Doc 1件取得、OpenRouter実行、`status=succeeded`、`prompt_version=monthly-report-v20260517.1`、`resolved_model_report=anthropic/claude-4.6-sonnet-20260217`、artifact/validation/llm_call_logs保存まで通過。出力内に残った `Gemini メモ` / `Google Meetメモ` 系の配布面語彙チューニングはP2-11の後続サンプル蓄積後にまとめて扱う
- 最新の広いmock focused suiteは `179 passed, 1 skipped`、RLS実DB/schema focusedは `8 passed`。`.pytest_cache` やLF→CRLF warningのみで、機能失敗は未確認

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-13 | 初版作成 |
| 2026-05-14 | 実装済みのAPIスタブ、ジョブモデル、モックUI、モック認証、Supabase初期migration、focused pytest結果に合わせて進捗を更新 |
| 2026-05-14 | Supabase CLIローカル起動、Postgres store、DB経由APIテスト、フィードバック保存APIの進捗を反映 |
| 2026-05-14 | クラウド本番リージョン `asia-northeast1`（東京）を反映 |
| 2026-05-14 | 明示的なジョブ進行API、失敗記録、Mock/Postgresテスト結果を反映 |
| 2026-05-14 | ジョブ失敗詳細を `monthly_report_jobs` の明示カラムへ保存する方針と実装状況を反映 |
| 2026-05-14 | ソーススナップショット・生成成果物の保存/一覧APIとテスト結果を反映 |
| 2026-05-14 | レビュー反映として、検証結果API、再現性メタ保存、API/機能仕様/アクティビティ図の整合を反映 |
| 2026-05-14 | 認証依存関係、Store側3件制限、編集画面の成果物保存パネルを反映 |
| 2026-05-14 | Phase 1/2の現在地表現を具体化し、再生成ジョブが再現性メタを引き継ぐ実装状況を反映 |
| 2026-05-14 | HANDOFF_STATIC_POC_TUNING.md を踏まえ、静的POCの build_prompts / scope_reminder / EconomicsゴールデンをP0/P1/P2へ組み込み |
| 2026-05-14 | `prompt_scope_notes` を正式フィールド名として反映し、U-025の残論点を初期投入方法へ絞り込み |
| 2026-05-14 | `prompt_scope_notes` の初期投入方針をレシピ由来 + 手入力可能に決定し、U-025を解決済みとして反映 |
| 2026-05-14 | 静的POCの `build_prompts` 共通化、`prompt_scope_notes` 保存/再生成コピー、Supabase migration適用、テスト結果を反映 |
| 2026-05-14 | provider mockによる1ジョブ通電、開発用 `/run-mock` API、OpenRouter provider抽象、テスト結果を反映 |
| 2026-05-14 | `/run-openrouter` API、OpenRouter実provider少量通電、接続エラー処理、テスト結果を反映 |
| 2026-05-14 | `llm_call_logs` 保存/取得API、provider成功/失敗時のhash/メタ記録、テスト結果を反映 |
| 2026-05-14 | Store共通のqueued job claim境界、Postgres `FOR UPDATE SKIP LOCKED`、worker実行関数、Economics匿名化フィクスチャとテスト結果を反映 |
| 2026-05-14 | `multistudent_scope_exclusion` 第一弾とPhase 2のバリデーション進捗を反映 |
| 2026-05-14 | `required_headings` 第一弾と最新テスト結果を反映 |
| 2026-05-14 | `forbidden_terms` 第一弾と最新テスト結果を反映 |
| 2026-05-14 | Google Workspace REST APIクライアント、`/fetch-google-sources`、P1-05の一部完了、最新テスト結果を反映 |
| 2026-05-14 | Google provider refresh tokenのFernet暗号化保存、Postgres credential store、access token refresh経路、最新テスト結果を反映 |
| 2026-05-14 | Google provider refresh token保存API、Auth/OAuth focused検証、最新テスト結果を反映 |
| 2026-05-14 | Supabase session経由のGoogle provider refresh token保存ブリッジ、user id一致チェック、最新テスト結果を反映 |
| 2026-05-14 | Supabase JWT secretによるBearer token検証、ドメイン制限、最新テスト結果を反映 |
| 2026-05-15 | Supabase session保存adapterのprovider/email/scope検証、PII/secret外向きエラー抑止テスト、最新テスト結果を反映 |
| 2026-05-15 | 非mock環境のジョブ所有者決定と一般ユーザーアクセス制限、最新テスト結果を反映 |
| 2026-05-15 | Supabase RLS migration、所有者ベースpolicy、schema/Postgres focusedテスト結果を反映 |
| 2026-05-15 | ライブE2E前設定ガイドへの参照を追加 |
| 2026-05-15 | Cloud Logging向け構造化ログallowlist、workflowログ接続、実ログ出力テスト結果を反映 |
| 2026-05-16 | `agents.md` のPhase 1以降の実装エージェント構成と次のE2E優先順を現在位置・依存関係へ反映 |
| 2026-05-16 | ローカル Supabase Google provider 設定（config.toml `[auth.external.google]`、`enable_signup=true`、redirect URLs）と FastAPI 側 ES256/RS256 JWKS 検証経路を実装。実ブラウザでログイン→refresh token暗号化保存→1ジョブE2E通電（validation_failed まで）を確認し、P1-01/P1-04/P1-05 をローカル完了へ更新。P1-17（再現性メタ書き戻し）・P1-18（ES256 focused test）を追加 |
| 2026-05-16 | Auth & OAuth Agentの初手として `/auth/google`・`/auth/callback` のE2Eブリッジ、Supabase公開設定、pre-e2e手順、focusedテスト結果を反映 |
| 2026-05-16 | `/monthly-report-workshop/e2e` のライブE2E画面を追加し、ジョブ作成からGoogle取得、OpenRouter実行、artifact/validation確認までの開発導線を反映 |
| 2026-05-16 | HTML断片UI、Cookie+CSRF、RLS主境界、worker lease、冪等性、Storage/保持削除、監視、プロンプトインジェクション、人間承認ゲートをPhase 1〜3の計画へ追加 |
| 2026-05-16 | P1-14の第一弾として `/monthly-reports/*` のHTML一覧・新規・作成・詳細・status fragmentとfocusedテストを追加 |
| 2026-05-16 | P1-15の第一弾としてHTML action用CSRF cookie + hidden token検証とfocusedテストを追加 |
| 2026-05-16 | P1-14を継続し、通常UIに生成開始・preview・validation・feedback HTML fragmentを追加。P1-15のCSRF対象を生成開始・フィードバック保存へ拡張 |
| 2026-05-16 | P1-17の第一弾として `/run-openrouter` / `/run-mock` 実行前の再現性メタ既定値補完を追加し、OpenRouter経路のfocused testを追加 |
| 2026-05-16 | P1-17を継続し、`run_next_queued_monthly_report_job()` / `run_claimed_monthly_report_job()` に再現性メタ既定値を渡せる入口とworker focused testを追加 |
| 2026-05-16 | P1-17をPostgres worker focusedまで拡張し、workerの `owner_user_id` filter、Postgres永続化テスト、`.env` 読み込みガイドを追加 |
| 2026-05-16 | P1-18としてES256/RS256 JWKS検証のfocused testを追加し、HS256既存検証との併走を確認 |
| 2026-05-17 | ライブE2E初succeededを受けてP1-17を済へ更新し、P1-14として通常HTML UIのソース確認/手動保存/Google取得fragment、モック生成/OpenRouter生成完了導線、focusedテストを追加 |
| 2026-05-17 | 保存済みGoogle OAuth credentialからの実Google Docs/Sheets取得、モック生成、実OpenRouter生成のAPIライブE2E再確認結果を追記 |
| 2026-05-17 | P0-03として `prompt_version` 形式検証と静的レシピID/template_hash/Git SHA/app versionのメタデータregistryを追加し、focusedテスト結果を反映 |
| 2026-05-17 | P1-16第二弾として通常ユーザー読み取り系をSupabase RLS read store優先へ移行。P2-06 GitHub Actions focused pytest、P2-11 prompt injection/internal memo validation第一弾を追加 |
| 2026-05-17 | P2-13第一弾としてGitHub Actionsにsecret不要のmigration/static schema/RLS guardrailを追加し、Cloud Run smokeはmanual dispatch限定の手順へ分離 |
| 2026-05-17 | P3-06/P3-12第二弾としてPOST承認とPOST HTML exportを通常UIへ追加し、承認hash、再承認必須、未承認export拒否、Idempotency-Keyをfocused testで固定 |
| 2026-05-17 | E2E画面でjob `mrj_2b15b194636a4457b590e3ef73afa5b2` のRLS/Google OAuth/OpenRouter成功サンプルを記録。`Gemini メモ` / `Google Meetメモ` 系の配布面語彙チューニングはP2-11後続へ延期 |
| 2026-05-17 | P1-16第一弾としてユーザーJWT付きSupabase client生成ヘルパー、RLS実効Postgresセッションヘルパー、RLS focused testsを追加 |
| 2026-05-17 | `agents.md` と開発計画を最新化。Phase 0を済、Phase 1をライブE2E成功済みのMVP骨格、Phase 2を進行中、Phase 3を次着手へ整理し、次の開発優先順をP2-09→P2-10→P1-16継続→P3-01/P3-02→P3-06/P3-12へ更新 |
| 2026-05-17 | P2-09第一弾（job作成/run-mock/run-openrouterのIdempotency-Key対応、Postgres永続化migration/store入口）、P2-10第一弾（WorkerRunResultとキャンセル境界）、P3-01/P3-02（編集保存/再生成HTMXフォームとbackend route）を追加 |
| 2026-05-17 | MVPは本番のみへ戻し、staging / production の2環境分離は本番ポータル合流タイミングで用意する方針へ修正 |
| 2026-05-18 | 環境方針を再更新し、MVPからstaging / productionの2環境を用意する方針へ変更。stagingでmigration/RLS/OAuth/OpenRouter/HTML UI smoke/ライブE2Eを確認してからproductionへ昇格する |
| 2026-05-17 | P2-09 idempotency migrationを実DBへ適用しPostgres focused test通過。P1-16第三弾としてHTML GET detail/fragmentsをRLS read store優先へ移行 |
| 2026-05-17 | 並列実装でP2-09 HTML hidden idempotency、P2-10 worker lease/attempt/retry、P2-11 Gemini/Meet語彙sanitization、P1-15 auth cookie bridgeを追加。関連focused 111件、Postgres実DB 12件通過 |
| 2026-05-17 | UIコンポーネント方針を追加。Tailwind CSS + DaisyUIを標準、Flowbiteは保留、業務画面はtable/section中心、カードは繰り返し単位に限定 |
| 2026-05-17 | P3-06/P3-12の次スライスとして、承認ゲートとHTMLエクスポートの通常UI fragment契約、ブロック条件、Idempotency-Key、承認対象hash失効、focused UI受け入れ条件をscreen-design/functional-spec/development-planへ具体化 |
| 2026-05-17 | P2-12第一弾として保持期間削除planner/executor、Postgres repository、dry-run/delete監査metadata、OAuth credential削除runbook、secret不要unit testを追加 |
| 2026-05-17 | P2-14第一弾としてMVP監視runbookを追加。Cloud Run、worker、OpenRouter、Google API/OAuth、429/CSRF/403、費用上限のmetric・alert・初動・確認場所を整理 |
| 2026-05-17 | P3-09差分fragmentをdetail画面へ接続し、source-summaryを同一Idempotency-Key内でロック、sheet-selectorをPOST+CSRFへ変更。通常UI focused 55件通過 |
