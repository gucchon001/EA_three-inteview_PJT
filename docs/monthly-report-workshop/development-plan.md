# 開発計画書

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツールの開発計画
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- 関連文書: `requirements.md`, `functional-spec.md`, `test-plan.md`, `decision-log.md`, `AUTOMATION_NORTH_STAR.md`
- 最終更新: 2026-05-17

## 現在位置

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
- Cloud Run worker本番化には、lease timeout、heartbeat/updated_at、stuck job再claim、再試行上限、手動再実行、協調的キャンセル、Idempotency-Keyまたはjob input hashによる二重実行防止が未実装
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
- 2026-05-17 環境方針を再確認し、MVPは本番のみへ戻した。staging / production の2環境分離は、本番ポータルへ合流するタイミングで用意する
- 2026-05-17 P2-09の `monthly_report_idempotency_keys` migrationをローカル実DBへ適用し、Postgres focused testで永続冪等性のlookup/rememberを確認済み
- 2026-05-17 P1-16第三弾として、通常HTML UIのGET detail/status/preview/sources/validation fragment読み取りをRLS read store優先へ移行。書き込み系HTML actionは次段階までdirect storeを維持する
- 2026-05-17 P2-09追加として、新規ジョブ作成フォームと生成開始フォームにhidden `idempotency_key` を追加し、HTML actionの二重送信をfocused testで固定。生成開始HTML actionは同一job/run_mode/idempotency_keyなら初回job状態を返す
- 2026-05-17 P2-10追加として、`worker_attempts`, `max_worker_attempts`, `worker_last_claimed_at` migrationを追加し、実DBへ適用済み。`claim_next_runnable_job()` でqueued jobとlease timeout後のstale `running/fetch_sources` jobをclaimでき、retryable failureは上限までqueuedへ戻す。Postgres focused testも実DBで通過済み
- 2026-05-17 P2-09追加として、source保存とGoogle source取得のJSON API/HTMX actionにIdempotency-Keyを追加。Google取得は同一キー再送時にGoogle Workspace APIを再実行せず、保存済みsources fragment/JSON responseを返す
- 2026-05-17 P2-10追加として、claimed worker jobのheartbeat/touch primitiveをMock/Postgres storeへ追加し、worker実行前に `updated_at` / `worker_last_claimed_at` を更新できるようにした。stale reclaim拡張前の誤回収防止をfocused testで固定
- 2026-05-17 P1-16第四弾として、HTML write actionのうち編集後Markdown保存と再生成でRLS read-store preflight認可を追加。実writeは既存direct storeのまま維持し、full RLS write化はP2-09完了後に回す
- 2026-05-17 P2-09追加として、artifact保存、feedback保存、編集後Markdown保存のJSON API/HTMX actionにIdempotency-Keyを追加。同一キー再送時は初回artifact/feedback/final_markdownだけを返し、二重保存しないfocused testを追加
- 2026-05-17 P2-10追加として、`python -m eb_app.monthly_reports.worker_entry` のCloud Run worker entryを追加。Postgres + OpenRouter設定から1件/複数件のqueued jobを処理し、PIIを含まないJSON summaryと失敗時非0終了を返す。runbookは `security-operations.md` に追記
- 2026-05-17 P1-16第五弾として、HTML write actionのうちsource保存、Google source取得、feedback保存、生成開始にもRLS read-store preflight認可を追加。通常HTML UIの主要write actionはpreflight済みになった。実writeは既存direct storeのまま維持し、full RLS write化とdirect DB用途棚卸しを次段階へ回す
- 2026-05-17 P2-11追加として、`Gemini メモ` / `Google Meetメモ` / Google生成メモ系の配布面メタ語彙をdraft artifact側で狭くsanitizationし、source evidence内の同語彙は許容するfocused testを追加済み
- 2026-05-17 P1-15追加として、`eb_auth_session` HTTPOnly Cookieから検証済みSupabase JWTを受ける移行ブリッジを追加。Bearer token互換はE2E/内部JSON向けに維持する。server-side session refresh/rotationは後続
- 2026-05-17 UIコンポーネント方針として、Tailwind CSS + DaisyUIをレポート工房の標準にし、FlowbiteはMVP標準依存にしないことを決定。業務画面はtable/section中心、カードは繰り返し単位に限定し、HTMX errorもDaisyUI alert断片で返す
- 2026-05-17 P3-14第一弾として、alert/status/validation/feedback/sources/preview fragmentsをDaisyUI `alert` / `badge` / `table` / `prose` 中心へ標準化。router/storeには触れずHTML UI focused testで通過
- 2026-05-17 Phase 2並行実装として、GitHub Actionsの安全なfocused pytest workflowを追加。実Google/OpenRouter secretやSupabase Dockerを要求せず、mock/test envで月次レポート主要テスト、Supabase user client、validation safetyを実行する
- 2026-05-17 P2-11第一弾として、生成draft側に残った明示的なプロンプトインジェクション文言と内部/管理メモ露出を決定的validationで検出し、`validation_failed` として停止する focused test を追加
- 2026-05-17 E2E画面でRLS/Google OAuth/OpenRouter成功サンプルを記録。job `mrj_2b15b194636a4457b590e3ef73afa5b2` は `/monthly-report-workshop/e2e` からGoogle Doc 1件取得、OpenRouter実行、`status=succeeded`、`prompt_version=monthly-report-v20260517.1`、`resolved_model_report=anthropic/claude-4.6-sonnet-20260217`、artifact/validation/llm_call_logs保存まで通過。出力内に残った `Gemini メモ` / `Google Meetメモ` 系の配布面語彙チューニングはP2-11の後続サンプル蓄積後にまとめて扱う
- 最新の広いmock focused suiteは `179 passed, 1 skipped`、RLS実DB/schema focusedは `8 passed`。`.pytest_cache` やLF→CRLF warningのみで、機能失敗は未確認

### 実装体制（Phase 1以降）

- Phase 1実装オーナー: FastAPI基盤、認証、ジョブ実行、Google Workspace連携の全体責任
- Backend & Data Agent: `src/eb_app/monthly_reports/*` のジョブ/ストア/API実装、RLS・保存ポリシー
- Auth & OAuth Agent: Supabase JWT検証、ドメイン制限、Google OAuth refresh token保存、provider token再取得
- LLM Pipeline Agent: `build_messages` / `call_llm` / `llm_call_logs` / provider抽象と失敗分類
- Validation & Safety Agent: 決定的バリデーション、PII/secret抑止、Cloud Logging allowlist、監査イベント
- UI/HTMX Agent: ジョブ一覧、進捗、プレビュー、推敲、フィードバック、再生成UI
- QA・運用エージェント: focused pytest運用、CI接続、E2E手順、pre-e2e-setup整備

### 達成済みゲート（Phase 1以降）

- ✅ 達成: Supabase Google provider実E2E取得 → `google-oauth/supabase-session` 保存 → `fetch-google-sources` → `run-openrouter` → `validation` → `artifact保存`（validation_failed 経路）を1ジョブで通電（2026-05-16）
- ✅ 達成（focused + ライブE2E）: `/run-openrouter` / `/run-mock` / claimed worker完了時に `monthly_report_jobs` へ `prompt_version`, `template_hash`, `model_report`, `resolved_model_report`, `source_bundle_hash`, `app_version` を書き戻し、Mock/Postgres focused testと2026-05-17ライブE2Eでnull化を防ぐ
- ✅ 達成: ES256/RS256 JWKS検証経路の自動テスト追加。HS256既存テストとの併走で回帰を防ぐ
- ✅ 達成（一部）: 通常UIの第一弾を `/monthly-reports/*` のHTML page/action/fragmentへ寄せ、ジョブ一覧・作成・詳細・生成開始・preview・validation・feedbackでJSON API直接DOM更新を外した
- ✅ 達成（一部）: HTML action用CSRF cookie + hidden token検証をジョブ作成・生成開始・フィードバック保存へ追加し、Bearer token前提経路との役割分担を開始した
- ✅ 達成（一部）: Supabase RLSを主境界にするため、ユーザーJWT付きSupabase Client経路を作成し、通常ユーザー読み取り系とHTML detail fragmentをRLS read store優先へ移行。主要HTML write actionはRLS read preflight認可まで追加済み
- ✅ 達成: ライブE2Eを実Google Docsで成功（緑）させ、決定的バリデーションを通過する1ジョブを保存。本データでのチューニング比較土台を作成
- 優先: worker常駐実行接続、lease/stuck再claim/retry/冪等性、3件制限の実環境再現、LLM失敗時の再試行/再生成導線をE2Eで閉じる
- 優先: Storage移行policy、保持期間削除ジョブ、監視・費用上限アラート、プロンプトインジェクション検証、人間承認ゲートを設計・テストへ入れる
- 仕上げ: 編集後Markdown保存、再生成API/UI、モデル版比較、HTMLエクスポート/保存/送付の最小導線、Playwright最小シナリオで体験を通す

### 今後の開発計画（2026-05-17更新）

直近の開発は、ライブE2Eで確認済みの「OAuth取得・Google source保存・OpenRouter生成・artifact/validation/llm_call_logs保存」を土台に、通常UIと運用境界を固める。新しいモデル/語彙チューニングは、サンプルを増やしてからP2-11でまとめて扱う。

| 順位 | タスク | 理由 | 完了条件 |
|---|---|---|---|
| 1 | P2-10 worker本番化 継続 | Cloud Run worker entry後に、true mid-LLM heartbeatと後段stage stuck扱いを固定する | mid-LLM heartbeat方針、後段stuck扱いのfocused testまたは明示的保留条件がある |
| 2 | P1-16 RLS継続 | 通常ユーザー操作をRLS clientへ寄せ、direct DBをworker/管理/migration/保持削除へ狭める | full RLS write化の安全な順序、direct DB用途棚卸し、worker/管理境界の明文化が通る |
| 3 | P3-14 UI標準化 継続 | fragments標準化後、detail/list/new本体のDaisyUI化で通常UIの品質を上げる | detail/list/newがtable/form/steps/alert中心になり、HTML UI focused testが通る |
| 4 | P3-01/P3-02 編集保存・再生成UI 継続 | MVP体験として生成後の推敲、保存、再生成比較が必要 | 最新artifact prefill、再現性メタ比較、差分表示のfocused testが通る |
| 5 | P3-06/P3-12 エクスポート・承認ゲート | 家庭向けレポートでは生成成功と送付可能を分ける必要がある | HTMLエクスポート、人間承認、送付前チェックの最小導線をPlaywrightまたはfocused UI testで確認 |

並行で進めやすいタスク:

- P2-11: `Gemini メモ` / `Google Meetメモ` 系を含む入力由来メタ語彙のチューニング。ただし、成功サンプルを複数蓄積してから forbidden / safe replacement / warning に分類する。
- P2-13: GitHub Actions第二弾として migration適用チェック、RLS/static schemaチェック、Cloud Run smoke test手順を追加する。
- Phase 4: 本番ポータル合流時に staging / production のCloud Run・Supabase・Secret分離、staging E2E、production promotion checklistを整備する。
- P2-14: OpenRouter token cost、Google API quota、job failed率、429、CSRF拒否、費用上限の監視設計を文書化する。
- P3-10: Playwright最小シナリオを、実装済み区間から段階的に追加する。

## マイルストーン

| フェーズ | 状況 | 成果物 | 完了条件 |
|---|---|---|---|
| Phase 0: 整備 | 済 | プロンプト断片正本化、prompt_version、ジョブ表現スタブ | スクリプトとアプリが同じプロンプト断片を参照できる |
| Phase 1: MVP | 骨格実装済み・ライブE2E成功・通常UI/RLS第一弾済み | Supabase Postgres、OAuth取得、ジョブ保存、モックLLM、Markdown生成、検証、フィードバック、HTML断片UI、Cookie+CSRF、RLS主境界 | 実案件でチューニング記録を残しながら生成できる。残りは通常UIの編集/再生成/承認へ寄せる |
| Phase 2: 品質 | 進行中 | 決定的バリデーション拡充、pytest、provider mock、GitHub Actions、エラーハンドリング、冪等性、worker lease、保持削除、監視 | CIでモック生成パイプラインが通り、二重送信・stuck job・PII/secret・プロンプトインジェクション・保持削除を検証できる |
| Phase 3: MVP体験完成 | 次着手 | 現行HTML全文エディタ相当の推敲、HTMLエクスポート、ファイル保存、送付エクスポート、再生成、版切替、人間承認ゲート、Playwright | 現行全文エディタの必須操作をサーバ保存前提で内包し、承認後の送付/エクスポートまでPlaywrightで確認できる |
| Phase 4: 統合 | 未着手 | Supabaseポータル統合、ジョブ履歴一本化 | ポータル計画と矛盾しない形で統合 |

## Phase 0 タスク

| ID | 状態 | タスク |
|---|---|---|
| P0-01 | 済 | `monthly_report_draft_openrouter.py` の `build_prompts` を `src/eb_app/monthly_reports/llm_messages.py` などへ抽出し、CLIと工房workerが同じ関数を呼ぶ形にする |
| P0-02 | 済 | `src/eb_app/prompts/monthly/` を作成し、system、artifact指示、family-facing tone、validation repairなどのプロンプト断片を置く。`build_monthly_report_messages` は正本断片を読み込む |
| P0-03 | 済 | `src/eb_app/monthly_reports/prompt_versions.py` で `prompt_version` を `monthly-report-vYYYYMMDD.N` 形式として検証し、静的レシピID・template_hash・Git SHA・app versionを持つメタデータ/registryで対応付ける仕組みを追加済み |
| P0-04 | 済 | `POST /api/monthly-reports/jobs` のモック応答スタブを作る |
| P0-05 | 済 | ジョブ状態モデルをコードに定義する |
| P0-06 | 済 | `build_messages` の塊順テストを追加する。契約、`prompt_scope_notes`、根拠ソース、構造参考、語感参考、artifact指示の順を固定する |
| P0-07 | 済 | 静的レシピ `prompts.scope_reminder` を工房ジョブの正式フィールド `prompt_scope_notes` へ変換し、手入力でも指定できる層を用意する |

## Phase 1 タスク

| ID | 状態 | タスク |
|---|---|---|
| P1-01 | 済（ローカル） | Supabase Auth Google providerとドメイン制限。FastAPI側のJWT検証（HS256対称鍵 + ES256/RS256 JWKS）、メールドメイン制限、ローカルSupabase config.toml `[auth.external.google]` + `enable_signup=true` を実装。実ブラウザでログイン→Bearer検証通過まで2026-05-16に確認済み。Cloud Supabase（本番）への移行とDB-level Supabase Auth roleの実環境検証は後続 |
| P1-02 | 一部完了 | ローカル開発用モック認証 |
| P1-03 | 一部完了 | Supabase Postgresの初期スキーマ、接続設定、RLS migration。主要テーブルのRLS有効化と所有者policyは静的テスト済み、実Supabase Auth roleでのDB-level E2Eは後続 |
| P1-04 | 済（ローカル） | Google provider refresh tokenのFernet暗号化保存とCloud Run Secret鍵管理。暗号化保存/復号/refresh境界、保存API、provider/email/scope検証付きSupabase session保存ブリッジ、`/auth/callback` でのSupabase session → refresh token取得 → 暗号化保存（実DBで228byte暗号文 + `local-v1` version 確認）まで実装済み |
| P1-05 | 済（ローカル） | ユーザーOAuthによるSheets / Docs取得。REST APIクライアント、保存API、暗号化済みrefresh tokenからのaccess token解決、ライブE2Eでの `fetch-google-sources` 実行までを実機確認済み。実データでのDocs/Sheets内容E2Eチューニングは別途 |
| P1-06 | 一部完了 | ソーススナップショット保存 |
| P1-07 | 一部完了 | 非同期ジョブ作成、3件制限、明示的なstage進行API。DB-backed workerのclaim境界と `owner_user_id` filterは実装済み、常駐worker/Cloud Run実行方式は未着手 |
| P1-08 | 一部完了 | OpenRouter呼び出し抽象。まずprovider mockで `call_llm` を通し、その後少量 `chat/completions` で工房本体から疎通確認する |
| P1-09 | 一部完了 | Markdown草稿保存 |
| P1-10 | 一部完了 | 最低限の決定的バリデーション。空出力、必須見出し、配布面禁止語、複数生徒スコープ混入の第一弾を実装済み |
| P1-11 | 一部着手 | ジョブ一覧・詳細・プレビュー画面 |
| P1-12 | 一部完了 | フィードバック保存 |
| P1-13 | 済 | 肥大化時にSupabase Storageへ移すための `storage_path` カラムを初期スキーマに含める |
| P1-14 | 一部完了 | 通常UI用の `/monthly-reports/*` HTML page/action/fragmentルータを本番側へ追加し、ジョブ作成・ソース確認/手動保存/Google取得・生成開始・モック生成完了・OpenRouter生成・進捗・プレビュー・検証・フィードバック・エラーをHTML断片で返す。第一弾として一覧・新規・作成・詳細・sources/status/preview/validation/feedback fragment、Google Docs/Sheets取得HTML action、生成開始、モック生成、OpenRouter生成を実装済み。残りは再生成、キャンセル、失敗時専用エラー断片、編集保存導線 |
| P1-15 | 一部完了 | HTTPOnly/Secure/SameSite Cookie + CSRFを本番UI認証境界として実装し、Bearer token前提の経路をE2E/内部JSON API/移行互換へ限定する。HTML action用CSRF cookie + hidden token検証をジョブ作成・生成開始・ソース保存・Google取得・フィードバック保存へ追加済み。さらに `eb_auth_session` HTTPOnly CookieからSupabase JWTを検証する移行ブリッジを追加済み。残りはserver-side session refresh/rotation、Cookie失効/ログアウト、Bearer UI棚卸し |
| P1-16 | 一部完了 | Supabase RLSを主境界にするため、ユーザーJWT付きSupabase Client生成を導入し、service role/direct DBの用途をworker・管理・migration・保持削除へ限定する。第一弾として検証済みaccess tokenを `CurrentUser` に保持し、ユーザーJWT付きSupabase anon client生成ヘルパーとRLS実効Postgresテストを追加済み。第二弾として通常ユーザーのJSON読み取りAPI（jobs/detail/sources/artifacts/validations/llm-calls）と通常UI一覧をRLS read store優先へ移行済み。第三弾として通常HTML UIのGET detail/status/preview/sources/validation fragment読み取りをRLS read store優先へ移行済み。第四弾として編集後Markdown保存/再生成、第五弾としてsource保存/Google source取得/feedback保存/生成開始のHTML write actionへRLS read preflight認可を追加済み。残りはfull RLS write化、direct DB用途棚卸し、worker/管理/migration/保持削除境界の固定 |
| P1-17 | 済 | `/run-openrouter` / `run-mock` / `workflow.run_claimed_monthly_report_job` 完了時に `monthly_report_jobs` の `prompt_version`, `template_hash`, `model_report`, `resolved_model_report`, `source_bundle_hash`, `app_version` を書き戻し、ジョブレスポンスとPostgres双方でnullにならないことをMock/Postgres focused testと2026-05-17ライブE2Eで固定済み |
| P1-18 | 済 | Supabase ES256/RS256 JWT検証のfocused testを追加。`PyJWKClient` 相当をfakeし、ES256/RS256 keypairでtoken発行→API認証通過を確認。HS256 既存テスト（`test_auth_mock.py`）との併走で回帰を防ぐ |

## Phase 2 タスク

| ID | 状態 | タスク |
|---|---|---|
| P2-01 | 一部完了 | ゴールデンフィクスチャ整備。Economics 複数生徒MTGの匿名化版を追加し、プロンプト構築テストへ接続済み |
| P2-02 | 済 | provider mockで結合テスト。`build_messages -> call_llm mock -> validate -> persist` を1ジョブで通す |
| P2-03 | 一部完了 | バリデーションルール拡充。`non_empty_markdown`, `required_headings`, `forbidden_terms`, `multistudent_scope_exclusion` 第一弾を実装済み |
| P2-04 | 一部完了 | 失敗stageとerror_typeの体系化 |
| P2-05 | 一部完了 | PII/secret抑止テスト。OpenRouter、Google Workspace、Google OAuth token refresh、validation失敗時に本文・token・secret・外部API本文が外向きエラーへ出ないことを確認済み。Cloud Logging向け構造化ログallowlistとworkflow失敗/成功時の実ログ出力検査も実装済み。Cloud Run上の実ログ検索確認は後続 |
| P2-06 | 一部完了 | GitHub Actionsでpytestを実行。第一弾として `.github/workflows/monthly-report-focused-tests.yml` を追加し、secret不要・Supabase Docker不要の安全なfocused suiteをPython 3.12で実行する |
| P2-07 | 一部完了 | 匿名化済みゴールデンフィクスチャ作成 |
| P2-08 | 一部完了 | 複数生徒MTG混入防止テスト。`prompt_scope_notes` により対象外の別姓＋様の評価文が家庭向け本文へ混入しないことを確認 |
| P2-09 | 一部完了 | POST系API/HTML actionにIdempotency-Keyまたはjob input hashを導入し、二重送信・リロード・worker再試行時の挙動を固定する。job作成、`run-mock`、`run-openrouter`、source保存、Google source取得、artifact保存、feedback保存、編集後Markdown保存の冪等性を実装し、Google取得の同一キー再送では外部APIを再実行しないfocused testも追加済み。Postgres永続化用 `monthly_report_idempotency_keys` migration/storeとHTML hidden keyも追加済み。残りはvalidation保存や将来export/approval actionの冪等性 |
| P2-10 | 一部完了 | Cloud Run worker本番化に向け、lease timeout、heartbeat/updated_at、stuck job再claim、retry上限、手動再実行、協調的キャンセルを実装・テストする。worker実行結果サマリ、provider実行前キャンセル境界、worker attempt/max attempt、lease timeout後のstale `running/fetch_sources` reclaim、retryable failureのqueued復帰、worker heartbeat/touch primitive、Cloud Run worker entry/runbookを実装し、実DB Postgres focused testも通過済み。残りはtrue mid-LLM heartbeat方針、後段stageの安全なstuck扱い |
| P2-11 | 一部完了 | Google Docs/Sheets由来のプロンプトインジェクション、内部メモ露出、送付禁止語、対象外生徒混入の検証を拡充する。明示的なプロンプトインジェクション文言、内部/管理メモ露出、`Gemini メモ` / `Google Meetメモ` / Google生成メモ系配布面メタ語彙のsanitizationをfocused testで固定済み。残りはE2Eサンプルを増やした語彙variant追加と承認ゲート連動 |
| P2-12 | 未着手 | 保持期間削除ジョブを設計・実装し、ドライラン件数確認、削除後確認、監査ログ、OAuth credential削除runbookを含める |
| P2-13 | 未着手 | GitHub Actionsにmigration適用チェック、RLS/static schemaチェック、Cloud Run smoke test手順を追加する |
| P2-14 | 未着手 | Cloud Run/OpenRouter/Google API/job failed率/429/CSRF拒否/費用上限の監視・アラートを設計する |

## Phase 3 タスク

| ID | 状態 | タスク |
|---|---|---|
| P3-01 | 一部完了 | 編集後Markdown保存。通常UI詳細画面にHTMX保存フォームとbackend routeを追加し、`final_markdown` artifact保存とpreview fragment更新をfocused testで固定済み。最新artifact prefillは後続 |
| P3-02 | 一部完了 | 再生成API/UI。通常UI詳細画面にHTMX再生成フォームとbackend routeを追加し、新しいqueued jobのstatus fragment返却をfocused testで固定済み。再現性メタ比較表示、差分表示は後続 |
| P3-03 | 未着手 | 管理者向けprompt/model override |
| P3-04 | モック着手 | 現行HTML全文エディタ由来のiframe編集領域と1行ツールバー |
| P3-05 | モック着手 | HTMLソース直接編集 |
| P3-06 | モック着手 | HTMLエクスポート |
| P3-07 | モック着手 | ファイル保存・ファイルから開く |
| P3-08 | モック着手 | 送付エクスポート |
| P3-09 | 未着手 | 生成物と最終編集後HTML/Markdownの簡易テキスト差分表示 |
| P3-10 | 未着手 | Playwrightによるエディタ体験・保存・差分・送付エクスポートE2E |
| P3-11 | 未着手 | 既存静的プレビュー経路との接続 |
| P3-12 | 未着手 | 生成成功、検証OK、編集保存済み、承認済み、送付/エクスポート済みを分ける人間承認ゲートを実装する |
| P3-13 | 未着手 | 複数タブ編集、保存競合、HTMX polling失敗、長時間生成中のリロード復帰をUI仕様・Playwrightで確認する |
| P3-14 | 一部完了 | Tailwind CSS + DaisyUIのUIコンポーネント標準化。第一弾としてalert/status/validation/feedback/sources/preview fragmentsをDaisyUI `alert` / `badge` / `table` / `prose` 中心へ整理済み。残りはジョブ一覧、新規作成、detail page本体、approvalをtable/form/steps/modal中心へ整理する |

## 現時点の検証

| 日付 | コマンド | 結果 |
|---|---|---|
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py -q` | 43 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py -q` | 56 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `EB_MONTHLY_REPORT_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:56322/postgres pytest tests/test_monthly_report_postgres_store.py tests/test_monthly_report_api_postgres.py -q` | 3 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_monthly_report_api.py tests/test_monthly_report_backend.py -q` | 26 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `EB_MONTHLY_REPORT_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:56322/postgres pytest tests/test_monthly_report_postgres_store.py tests/test_monthly_report_api_postgres.py -q` | 5 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_monthly_report_schema_files.py -q` | 3 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `EB_MONTHLY_REPORT_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:56322/postgres pytest tests/test_monthly_report_postgres_store.py tests/test_monthly_report_api_postgres.py -q` | 5 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py -q` | 60 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_monthly_report_api.py -q` | 14 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `EB_MONTHLY_REPORT_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:56322/postgres pytest tests/test_monthly_report_postgres_store.py -q` | 4 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `EB_MONTHLY_REPORT_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:56322/postgres pytest tests/test_monthly_report_api_postgres.py -q` | 3 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_monthly_report_api.py -q` | 15 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `EB_MONTHLY_REPORT_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:56322/postgres pytest tests/test_monthly_report_postgres_store.py -q` | 5 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `EB_MONTHLY_REPORT_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:56322/postgres pytest tests/test_monthly_report_api_postgres.py -q` | 3 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_monthly_report_api.py -q` | 24 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_monthly_report_backend.py tests/test_monthly_report_api.py -q` | 28 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `EB_MONTHLY_REPORT_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:56322/postgres pytest tests/test_monthly_report_postgres_store.py tests/test_monthly_report_api_postgres.py -q` | 8 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_mock_ui.py -q` | 25 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_monthly_report_llm_messages.py -q` | 2 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_monthly_report_schema_files.py -q` | 32 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `EB_MONTHLY_REPORT_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:56322/postgres pytest tests/test_monthly_report_postgres_store.py tests/test_monthly_report_api_postgres.py -q` | 8 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py tests/test_monthly_report_llm_messages.py -q` | 68 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `python scripts/monthly_report_draft_openrouter.py --help` | CLIが共通 `llm_messages` モジュールをimportできることを確認 |
| 2026-05-14 | `pytest tests/test_monthly_report_workflow.py -q` | 4 passed。provider mock通電とOpenRouter provider HTTPモックを確認 |
| 2026-05-14 | `pytest tests/test_monthly_report_workflow.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_monthly_report_llm_messages.py -q` | 33 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py tests/test_monthly_report_llm_messages.py tests/test_monthly_report_workflow.py -q` | 73 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `POST /api/monthly-reports/jobs/{job_id}/run-openrouter` via TestClient + `.env` | OpenRouter実provider通電成功。`status=succeeded`, `draft_markdown` 1件, validation info 1件。キーと本文全文は出力せず |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py tests/test_monthly_report_llm_messages.py tests/test_monthly_report_workflow.py -q` | 79 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_monthly_report_backend.py tests/test_monthly_report_workflow.py tests/test_monthly_report_api.py -q` | 38 passed。LLMログ保存と取得APIを確認 |
| 2026-05-14 | `EB_MONTHLY_REPORT_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:56322/postgres pytest tests/test_monthly_report_postgres_store.py tests/test_monthly_report_api_postgres.py -q` | 9 passed。Postgres `llm_call_logs` 保存を確認 |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py tests/test_monthly_report_llm_messages.py tests/test_monthly_report_workflow.py -q` | 80 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_monthly_report_llm_messages.py tests/test_monthly_report_fixtures.py -q` | 4 passed。Economics 複数生徒MTGの匿名化フィクスチャと `prompt_scope_notes` のプロンプト挿入順を確認 |
| 2026-05-14 | `pytest tests/test_monthly_report_backend.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_api.py -q` | 42 passed。worker claim境界、claim済みjob実行、API既存経路を確認 |
| 2026-05-14 | `EB_MONTHLY_REPORT_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:56322/postgres pytest tests/test_monthly_report_postgres_store.py tests/test_monthly_report_api_postgres.py -q` | 10 passed。Postgres `FOR UPDATE SKIP LOCKED` claim境界を確認 |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py tests/test_monthly_report_llm_messages.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_fixtures.py -q` | 86 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_monthly_report_workflow.py -q` | 8 passed。`multistudent_scope_exclusion` 第一弾を確認 |
| 2026-05-14 | `pytest tests/test_monthly_report_backend.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_api.py -q` | 43 passed。複数生徒混入検知追加後もAPI/worker focusedが通過 |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py tests/test_monthly_report_llm_messages.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_fixtures.py -q` | 87 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_monthly_report_workflow.py -q` | 9 passed。`required_headings` 第一弾を確認 |
| 2026-05-14 | `pytest tests/test_monthly_report_backend.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_api.py -q` | 44 passed。必須見出し検証追加後もAPI/worker focusedが通過 |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py tests/test_monthly_report_llm_messages.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_fixtures.py -q` | 88 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_monthly_report_workflow.py -q` | 10 passed。`forbidden_terms` 第一弾を確認 |
| 2026-05-14 | `pytest tests/test_monthly_report_backend.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_api.py -q` | 45 passed。禁止語検証追加後もAPI/worker focusedが通過 |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py tests/test_monthly_report_llm_messages.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_fixtures.py -q` | 89 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_monthly_report_google_workspace.py -q` | 5 passed。Google Workspace REST APIクライアント、ID抽出、Docs/Sets取得、token非露出エラーを確認 |
| 2026-05-14 | `pytest tests/test_monthly_report_google_workspace.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py -q` | 52 passed。GWS取得API追加後もbackend/API/worker focusedが通過 |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py tests/test_monthly_report_llm_messages.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_fixtures.py tests/test_monthly_report_google_workspace.py -q` | 96 passed。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `EB_MONTHLY_REPORT_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:56322/postgres pytest tests/test_google_oauth_credentials.py tests/test_monthly_report_postgres_store.py tests/test_monthly_report_api_postgres.py -q` | 16 passed。Postgres `google_oauth_credentials` への暗号化refresh token upsertを確認 |
| 2026-05-14 | `pytest tests/test_google_oauth_credentials.py tests/test_monthly_report_google_workspace.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py -q` | 58 passed, 1 skipped。OAuth/GWS/API/backend/worker focusedが通過 |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py tests/test_monthly_report_llm_messages.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_fixtures.py tests/test_monthly_report_google_workspace.py tests/test_google_oauth_credentials.py -q` | 102 passed, 1 skipped。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_auth_google_oauth.py -q` | 3 passed。Google provider refresh token保存APIの設定チェック、認証必須、保存呼び出しを確認 |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_auth_google_oauth.py tests/test_google_oauth_credentials.py tests/test_monthly_report_google_workspace.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py -q` | 72 passed, 1 skipped。Auth/OAuth/GWS/API/backend/worker focusedが通過 |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_auth_google_oauth.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py tests/test_monthly_report_llm_messages.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_fixtures.py tests/test_monthly_report_google_workspace.py tests/test_google_oauth_credentials.py -q` | 105 passed, 1 skipped。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_auth_google_oauth.py -q` | 5 passed。Google provider refresh token保存APIに加え、Supabase session保存ブリッジのuser id一致/不一致を確認 |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_auth_google_oauth.py tests/test_google_oauth_credentials.py tests/test_monthly_report_google_workspace.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py -q` | 74 passed, 1 skipped。Auth/OAuth/GWS/API/backend/worker focusedが通過 |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_auth_google_oauth.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py tests/test_monthly_report_llm_messages.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_fixtures.py tests/test_monthly_report_google_workspace.py tests/test_google_oauth_credentials.py -q` | 107 passed, 1 skipped。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-14 | `pytest tests/test_auth_mock.py::test_monthly_report_api_accepts_supabase_jwt_user tests/test_auth_mock.py::test_monthly_report_api_rejects_supabase_jwt_wrong_domain tests/test_auth_mock.py::test_monthly_report_api_rejects_invalid_supabase_jwt tests/test_auth_mock.py::test_monthly_report_api_requires_supabase_jwt_secret_when_token_is_present -q` | 4 passed。Supabase JWT検証、ドメイン制限、secret未設定時503を確認 |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_auth_google_oauth.py tests/test_google_oauth_credentials.py tests/test_monthly_report_google_workspace.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py -q` | 78 passed, 1 skipped。Supabase JWT検証追加後もAuth/OAuth/GWS/API/backend/worker focusedが通過 |
| 2026-05-14 | `pytest tests/test_auth_mock.py tests/test_auth_google_oauth.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py tests/test_monthly_report_llm_messages.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_fixtures.py tests/test_monthly_report_google_workspace.py tests/test_google_oauth_credentials.py -q` | 111 passed, 1 skipped。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-15 | `pytest tests/test_monthly_report_pii_safety.py -q` | 4 passed。OpenRouter/GWS/OAuth/validation失敗時のPII/secret外向きエラー抑止を確認 |
| 2026-05-15 | `pytest tests/test_auth_mock.py tests/test_auth_google_oauth.py tests/test_monthly_report_pii_safety.py -q` | 27 passed。Supabase session adapterとPII/secret抑止のfocusedが通過 |
| 2026-05-15 | `pytest tests/test_auth_mock.py tests/test_auth_google_oauth.py tests/test_monthly_report_pii_safety.py tests/test_google_oauth_credentials.py tests/test_monthly_report_google_workspace.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py -q` | 85 passed, 1 skipped。PII/Auth/OAuth/GWS/API/backend/worker focusedが通過 |
| 2026-05-15 | `pytest tests/test_monthly_report_api.py::test_monthly_report_api_uses_supabase_user_as_owner_and_filters_other_users -q` | 1 passed。非mock環境でJWT subをownerにし、他ユーザーの一覧・詳細・操作から隠すことを確認 |
| 2026-05-15 | `pytest tests/test_monthly_report_api.py -q` | 22 passed。所有者アクセス制限追加後も月次レポートAPI focusedが通過 |
| 2026-05-15 | `pytest tests/test_auth_mock.py tests/test_auth_google_oauth.py tests/test_monthly_report_pii_safety.py tests/test_google_oauth_credentials.py tests/test_monthly_report_google_workspace.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py -q` | 86 passed, 1 skipped。所有者アクセス制限追加後もPII/Auth/OAuth/GWS/API/backend/worker focusedが通過 |
| 2026-05-15 | `pytest tests/test_monthly_report_schema_files.py -q` | 5 passed。RLS有効化と所有者policyのmigration静的テストが通過 |
| 2026-05-15 | `EB_MONTHLY_REPORT_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:56322/postgres pytest tests/test_google_oauth_credentials.py tests/test_monthly_report_postgres_store.py tests/test_monthly_report_api_postgres.py -q` | 16 passed。RLS migration追加後もPostgres store/API focusedが通過 |
| 2026-05-15 | `pytest tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_auth_mock.py tests/test_auth_google_oauth.py tests/test_monthly_report_pii_safety.py -q` | 54 passed。schema/API/Auth/PII focusedが通過 |
| 2026-05-15 | `pytest tests/test_monthly_report_cloud_logging.py -q` | 4 passed。Cloud Logging向け構造化ログallowlistとworkflowのprovider/validation失敗ログがPII/secretを含まないことを確認 |
| 2026-05-15 | `pytest tests/test_monthly_report_cloud_logging.py tests/test_monthly_report_pii_safety.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_api.py -q` | 42 passed。Cloud Logging/PII/workflow/API focusedが通過 |
| 2026-05-15 | `pytest tests/test_monthly_report_cloud_logging.py tests/test_monthly_report_pii_safety.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_api.py tests/test_auth_mock.py tests/test_auth_google_oauth.py -q` | 65 passed。Cloud Logging/PII/workflow/API/Auth focusedが通過 |
| 2026-05-16 | `pytest tests/test_monthly_report_html_ui.py -q` | 3 passed。通常UIのHTML page/action/status fragment境界を確認。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-16 | `pytest tests/test_monthly_report_html_ui.py tests/test_monthly_report_api.py tests/test_mock_ui.py -q` | 50 passed。HTML UI追加後もJSON APIとmock UIのfocusedが通過。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-17 | `pytest tests/test_monthly_report_recipe_conversion.py tests/test_monthly_report_html_ui.py tests/test_monthly_report_api.py tests/test_monthly_report_llm_messages.py -q` | 48 passed。静的レシピ `prompts.scope_reminder` → `prompt_scope_notes` 変換、HTML手入力保存、API、LLM message挿入順を確認 |
| 2026-05-16 | `pytest tests/test_monthly_report_html_ui.py -q` | 4 passed。HTML actionのCSRF token必須化を確認。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-16 | `pytest tests/test_auth_mock.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py tests/test_monthly_report_html_ui.py -q` | 86 passed。HTML UI/CSRF追加後もauth/schema/API/backend/mock focusedが通過。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-16 | `pytest tests/test_monthly_report_html_ui.py -q` | 8 passed。通常UIの生成開始、preview、validation、feedback HTML fragmentとCSRF境界を確認。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-16 | `pytest tests/test_monthly_report_html_ui.py tests/test_monthly_report_api.py tests/test_mock_ui.py -q` | 55 passed。HTML fragment拡張後もJSON APIとmock UIのfocusedが通過。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-17 | `pytest tests/test_monthly_report_html_ui.py -q` | 19 passed。通常HTML UIのソース確認/手動保存/Google取得fragment、Google取得設定不足/秘匿エラー、CSRF拒否/Secure cookie/複数タブtoken再利用、モック生成/OpenRouter生成完了導線、status=succeeded、preview artifact、validation fragment、再現性メタ保存を確認 |
| 2026-05-17 | `pytest tests/test_auth_mock.py tests/test_monthly_report_google_workspace.py tests/test_monthly_report_worker.py tests/test_monthly_report_workflow.py tests/test_monthly_report_api.py tests/test_monthly_report_html_ui.py tests/test_mock_ui.py -q` | 105 passed。HTML UI Google取得/OpenRouter生成、CSRF hardening、Auth/API/worker/workflow/mock UI focusedが通過 |
| 2026-05-17 | `pytest tests/test_monthly_report_prompt_versions.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_api.py::test_monthly_report_api_run_openrouter_fills_missing_reproducibility_meta -q` | 32 passed。P0-03の `monthly-report-vYYYYMMDD.N` 検証、静的レシピID/template_hash/Git SHA/app versionメタデータ対応付け、既存workflow/worker/API再現性メタ経路の回帰なしを確認 |
| 2026-05-17 | `pytest tests/test_supabase_user_client.py -q` | 3 passed。ユーザーJWT付きSupabase anon client生成、設定不足503、access token不足401を確認 |
| 2026-05-17 | `EB_MONTHLY_REPORT_DATABASE_URL=... pytest tests/test_monthly_report_rls_postgres.py -q` | 3 passed。Postgres `authenticated` role + `request.jwt.claim.sub` でRLSを評価し、job/source所有者filter、他ユーザー名義insert拒否、audit_logs非公開を確認 |
| 2026-05-17 | `pytest tests/test_auth_mock.py tests/test_supabase_user_client.py -q` | 21 passed。CurrentUser access_token追加後も既存Supabase JWT/Mock認証テストが通過 |
| 2026-05-17 | `EB_MONTHLY_REPORT_DATABASE_URL=... pytest tests/test_monthly_report_rls_postgres.py tests/test_monthly_report_schema_files.py -q` | 8 passed。RLS migration静的確認と実DB RLS評価テストが通過 |
| 2026-05-16 | `pytest tests/test_monthly_report_api.py::test_monthly_report_api_run_openrouter_fills_missing_reproducibility_meta -q` | 1 passed。`/run-openrouter` 実行時に欠けていた `prompt_version`, `model_report`, `app_version` を設定由来で書き戻し、`template_hash`, `source_bundle_hash`, `resolved_model_report` もレスポンス/詳細でnullにならないことを確認 |
| 2026-05-16 | `pytest tests/test_monthly_report_api.py tests/test_monthly_report_html_ui.py tests/test_mock_ui.py -q` | 56 passed。P1-17第一弾後もAPI/HTML UI/mock UI focusedが通過。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-16 | `pytest tests/test_monthly_report_workflow.py tests/test_monthly_report_backend.py -q` | 26 passed。workflow/backend focusedが通過。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-16 | `pytest tests/test_monthly_report_worker.py::test_run_next_queued_monthly_report_job_fills_missing_reproducibility_meta -q` | 1 passed。claimed worker経路で `prompt_version`, `model_report`, `app_version` を注入し、`template_hash`, `source_bundle_hash`, `resolved_model_report` とともにジョブへ残ることを確認 |
| 2026-05-16 | `pytest tests/test_monthly_report_worker.py tests/test_monthly_report_workflow.py tests/test_monthly_report_api.py -q` | 37 passed。P1-17 worker経路追加後もworker/workflow/API focusedが通過。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-16 | `pytest tests/test_auth_mock.py tests/test_monthly_report_api.py -q` | 37 passed。ES256/JWKS分岐をdependencies.pyへ追加後、HS256既存テストが回帰なしで通過 |
| 2026-05-16 | `pytest tests/test_auth_mock.py -q` | 18 passed。ES256/RS256 JWKS token、JWKS設定不足503、HS256既存token検証をfocused testで確認。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-16 | `pytest tests/test_auth_mock.py tests/test_monthly_report_api.py -q` | 41 passed。JWKS focused追加後も月次レポートAPI所有者境界を含むAuth/API focusedが通過。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-16 | ブラウザ実E2E（uvicorn 127.0.0.1:8000 + ローカル Supabase 127.0.0.1:56321 + 実Google OAuth） | Google ログイン→`/auth/callback` 表示 `credential_id=goc_c77721c7f4c44619af79b0aa8142c687` / Postgres `google_oauth_credentials` 行追加（user_id=`ab8bafb6-...`, scope全部入り, encryption_key_version=`local-v1`, 暗号文228byte）。続けて `/monthly-report-workshop/e2e` で 1ジョブ作成→`fetch-google-sources` 空sources→`run-openrouter`（OpenRouter `anthropic/claude-4.6-sonnet-...`, 10,750入力/225出力token, 5.8s）→`validation_failed`（`required_headings` ルール）→`monthly_report_validations` 1行記録→`llm_call_logs` 1行記録（hashのみ） |
| 2026-05-17 | ブラウザ実E2E **初 succeeded**（実 Google Docs + 実 OpenRouter + 決定論的バリデーション） | job `mrj_aa9c...` が `status=succeeded`。`template_hash`, `source_bundle_hash`, `resolved_model_report`, `model_report`, `prompt_version`, `app_version` すべて非null。`forbidden_terms_sanitized` info で `担当CA→担当` 自動置換を記録。`non_empty_markdown` info OK。artifacts に `draft_markdown`（content_hash `sha256:b8ee...`）1件保存。llm_calls: `anthropic/claude-4.6-sonnet-20260217` 実呼び出し, 15,171入力/4,014出力token, 81s。広林様フィジックス月次レポートの構造（01〜07、推敲ログ、人間チェックリスト）を生成。 |
| 2026-05-17 | APIライブE2E（実 Google Docs/Sheets + 保存済みGoogle OAuth + 実 OpenRouter） | job `mrj_529b2fe35c874c99a2325946859dfae3` が `status=succeeded`。Google source 3件保存、`resolved_model_report=anthropic/claude-4.6-sonnet-20260217`、`prompt_version` / `template_hash` / `source_bundle_hash` 非null。artifacts 1件、validations 2件、llm_calls 1件（hashのみ）を確認。 |
| 2026-05-17 | E2E画面ライブ成功サンプル（RLS/Google OAuth/OpenRouter） | job `mrj_2b15b194636a4457b590e3ef73afa5b2` が `status=succeeded`。Google Doc source 1件、artifact `draft_markdown` 1件、validation info 2件（`forbidden_terms_sanitized`, `non_empty_markdown`）、llm_call_logs 1件を保存。`prompt_version=monthly-report-v20260517.1`、`template_hash` / `source_bundle_hash` 非null、`model_report=anthropic/claude-sonnet-4.6`、`resolved_model_report=anthropic/claude-4.6-sonnet-20260217`、`app_version=local-dev`。成果物内の `Gemini メモ` 系配布語彙は後続P2-11 tuningへ回す |
| 2026-05-17 | `pytest tests/test_auth_mock.py tests/test_auth_google_oauth.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py tests/test_monthly_report_llm_messages.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_fixtures.py tests/test_monthly_report_google_workspace.py tests/test_google_oauth_credentials.py tests/test_monthly_report_pii_safety.py tests/test_monthly_report_cloud_logging.py tests/test_monthly_report_html_ui.py tests/test_monthly_report_prompt_versions.py tests/test_monthly_report_recipe_conversion.py tests/test_supabase_user_client.py tests/test_monthly_report_validation_safety.py -q` | **179 passed, 1 skipped**。RLS read store移行、Phase 2 CI対象suite、プロンプトインジェクション/内部メモ露出validationを含むmock focusedが通過 |
| 2026-05-17 | `EB_MONTHLY_REPORT_DATABASE_URL=... pytest tests/test_monthly_report_rls_postgres.py tests/test_monthly_report_schema_files.py -q` | **8 passed**。実DB RLS評価とRLS migration静的確認が通過 |
| 2026-05-17 | `pytest tests/test_monthly_report_api.py tests/test_monthly_report_html_ui.py -q` | **58 passed**。source保存/Google source取得のJSON API・HTMX action冪等性、RLS read preflight、DaisyUI fragment標準化後のHTML UIが通過 |
| 2026-05-17 | `pytest tests/test_monthly_report_api.py tests/test_monthly_report_html_ui.py tests/test_monthly_report_worker.py tests/test_monthly_report_worker_entry.py -q` | **83 passed**。source保存/Google source取得/feedback保存/生成開始HTML actionのRLS read preflight追加後もAPI・HTML UI・worker focusedが通過 |
| 2026-05-17 | `pytest tests/test_monthly_report_worker.py -q` | **12 passed**。worker heartbeat/touch primitive追加後もworker focusedが通過 |
| 2026-05-17 | `.env 読込後 pytest tests/test_monthly_report_postgres_store.py -q` | **13 passed**。Postgres idempotency、worker attempt/lease/retry、heartbeat/touch primitiveが実DBで通過 |
| 2026-05-17 | `pytest tests/test_monthly_report_api.py tests/test_monthly_report_html_ui.py tests/test_monthly_report_worker.py tests/test_monthly_report_worker_entry.py -q` | **79 passed**。artifact/feedback/edited-markdown冪等性、Cloud Run worker entry、既存API/HTML UI/worker focusedが通過 |
| 2026-05-17 | `.env 読込後 pytest tests/test_monthly_report_postgres_store.py -q` | **13 passed**。worker entry追加後もPostgres store実DB focusedが通過 |
| 2026-05-16 | 全focused suite（mock）: `pytest tests/test_auth_mock.py tests/test_auth_google_oauth.py tests/test_monthly_report_schema_files.py tests/test_monthly_report_api.py tests/test_monthly_report_backend.py tests/test_mock_ui.py tests/test_monthly_report_llm_messages.py tests/test_monthly_report_workflow.py tests/test_monthly_report_worker.py tests/test_monthly_report_fixtures.py tests/test_monthly_report_google_workspace.py tests/test_google_oauth_credentials.py tests/test_monthly_report_pii_safety.py tests/test_monthly_report_cloud_logging.py tests/test_monthly_report_html_ui.py -q` | **142 passed, 1 skipped**。P1-17（再現性メタ書き戻し）・P1-18（ES256/RS256 JWKS focused）含む全mock focusedが通過。`.pytest_cache` 書き込み権限warningのみ |
| 2026-05-16 | Postgres統合suite: `EB_MONTHLY_REPORT_DATABASE_URL=... pytest tests/test_google_oauth_credentials.py tests/test_monthly_report_postgres_store.py tests/test_monthly_report_api_postgres.py -q` | **17 passed**。`test_postgres_worker_fills_missing_reproducibility_meta`（P1-17 Postgres経路）含む全Postgres focusedが通過 |

## 依存関係

- Supabaseスキーマ案は初期migrationとして作成済み。Postgres storeも追加済み。次はRLS、実Supabase Auth検証、実ジョブ永続化の拡張が必要。
- 月次レポートAPIは認証依存関係を通す。ローカルMVPでは `owner_user_id` 暫定値を許可し、Supabase Auth接続時は認証ユーザーIDへ差し替える。2026-05-16以降の本番UI方針はCookie+CSRF、内部/E2E/移行期JSON APIはBearer token互換とする。
- 通常UIはHTML page/action/fragmentを優先する。既存JSON APIはworker/E2E/管理/将来連携用として残すが、UIのDOM更新はHTML断片で行う。
- RLSは主境界へ寄せる。ユーザーJWT付きSupabase Client経路の導入前は、direct DB/API側認可が暫定境界であることを明示し、本番UI完成条件にしない。
- P1-16第五弾で通常ユーザーJSON読み取りAPI、通常UI一覧、HTML detail/status/preview/sources/validation fragment読み取り、主要HTML write actionのRLS read preflight認可まで移行済み。次はfull RLS write化の順序設計と、Postgres direct storeの呼び出し元をworker・管理・migration・保持削除へ狭める。
- prompt_version管理が決まらないと、チューニング比較が曖昧になる。
- U-025は解決済み。静的POCの `prompts.scope_reminder` は工房ジョブ/APIでは `prompt_scope_notes` とする。初期投入はレシピ由来 + 手入力可能、householdメタからの自動生成は後続に回す。
- ジョブ状態モデル、モックAPI、DB永続化、3件制限、`prompt_scope_notes` 保存、provider mock通電、実OpenRouter少量通電、LLM呼び出しメタ保存、DB-backed workerのclaim境界は骨格実装済み。次は常駐worker/Cloud Run実行方式と、実案件ソースでのチューニング比較UIが必要。
- OpenRouter呼び出し抽象は実装済み。キー情報エンドポイントと `chat/completions` の工房本体通電は確認済み。
- 実Supabase Auth + Google OAuth + Google Workspace read flowのライブE2E前設定は [pre-e2e-setup.md](pre-e2e-setup.md) を参照する。
- Auth & OAuth Agentの初手として、`/auth/google` と `/auth/callback` のE2Eブリッジを追加済み。`SUPABASE_URL` / `SUPABASE_ANON_KEY` だけをブラウザへ渡し、Supabase sessionの `provider_refresh_token` は `/api/auth/google-oauth/supabase-session` へ送って暗号化保存する。
- `/monthly-report-workshop/e2e` はライブE2E用の開発導線として使う。`/auth/callback` でcredential保存後、同じSupabase sessionで `create job -> fetch-google-sources -> run-openrouter -> result確認` を実行する。
- 実装体制として、Phase 1以降は実装オーナー＋Backend/Auth/LLM/Validation/UI/QAの役割分担を固定し、同一ファイルの同時編集を避ける運用で進める。
- 次の開発優先順は「artifact/feedback冪等性」「worker Cloud Run entry/runbookとmid-LLM heartbeat方針」「通常ユーザーwrite actionのRLS preflight継続」「detail/list/newのDaisyUI標準化」「エクスポート/承認ゲート」「最小Playwright導線」の順で固定。

## 環境変数ガイド

手動設定が必要な環境変数は `.env` を正とし、値はログ・ドキュメント・完了報告に出さない。ローカルPostgres/Supabase込みのfocused testでは、少なくとも `EB_MONTHLY_REPORT_DATABASE_URL` をプロセス環境へ読み込む。

| 用途 | 必須キー | 備考 |
|---|---|---|
| Postgres store/API focused test | `EB_MONTHLY_REPORT_DATABASE_URL` | 未設定時は `tests/test_monthly_report_postgres_store.py` / `tests/test_monthly_report_api_postgres.py` がskipされる |
| ローカルmock認証 | `EB_AUTH_MODE=mock` | UI/API focused testは原則mockで実行する |
| Supabase Auth/JWKS E2E | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET` | `SUPABASE_JWT_SECRET` はHS256互換テスト用、ES256/RS256はJWKS経由 |
| OpenRouter実通電 | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL_REPORT` | 通常のpytestでは実APIを叩かず、provider mockを使う |
| 通常HTML UIのGoogle取得 | `EB_GOOGLE_WORKSPACE_ACCESS_TOKEN` または `EB_MONTHLY_REPORT_DATABASE_URL`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `EB_GOOGLE_TOKEN_ENCRYPTION_KEY` | 前者は暫定ローカル経路。後者は保存済みGoogle OAuth refresh tokenからaccess tokenを再取得する本来経路 |
| 再現性メタ | `EB_MONTHLY_REPORT_PROMPT_VERSION`, `EB_APP_VERSION` | 未設定時はコード既定値を使う。Cloud Runでは `K_REVISION` / `GITHUB_SHA` も `app_version` 候補 |

PowerShellで `.env` を現在プロセスに読み込んでfocused testを実行する例:

```powershell
Get-Content .env | Where-Object { $_ -match '^\s*[^#][^=]+=' } | ForEach-Object {
  $name, $value = $_ -split '=', 2
  [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), 'Process')
}
pytest tests/test_monthly_report_postgres_store.py -q
```

## 未決事項

[decision-log.md](decision-log.md) を正とする。2026-05-13時点でMVP設計に必要な主要未決事項は解決済み。

## 受け入れ条件

- 各フェーズに状態列と完了条件がある。
- MVPに必要なタスクがPhase 1に入っている。
- テスト計画と対応するタスクがPhase 2にある。

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
| 2026-05-17 | E2E画面でjob `mrj_2b15b194636a4457b590e3ef73afa5b2` のRLS/Google OAuth/OpenRouter成功サンプルを記録。`Gemini メモ` / `Google Meetメモ` 系の配布面語彙チューニングはP2-11後続へ延期 |
| 2026-05-17 | P1-16第一弾としてユーザーJWT付きSupabase client生成ヘルパー、RLS実効Postgresセッションヘルパー、RLS focused testsを追加 |
| 2026-05-17 | `agents.md` と開発計画を最新化。Phase 0を済、Phase 1をライブE2E成功済みのMVP骨格、Phase 2を進行中、Phase 3を次着手へ整理し、次の開発優先順をP2-09→P2-10→P1-16継続→P3-01/P3-02→P3-06/P3-12へ更新 |
| 2026-05-17 | P2-09第一弾（job作成/run-mock/run-openrouterのIdempotency-Key対応、Postgres永続化migration/store入口）、P2-10第一弾（WorkerRunResultとキャンセル境界）、P3-01/P3-02（編集保存/再生成HTMXフォームとbackend route）を追加 |
| 2026-05-17 | MVPは本番のみへ戻し、staging / production の2環境分離は本番ポータル合流タイミングで用意する方針へ修正 |
| 2026-05-17 | P2-09 idempotency migrationを実DBへ適用しPostgres focused test通過。P1-16第三弾としてHTML GET detail/fragmentsをRLS read store優先へ移行 |
| 2026-05-17 | 並列実装でP2-09 HTML hidden idempotency、P2-10 worker lease/attempt/retry、P2-11 Gemini/Meet語彙sanitization、P1-15 auth cookie bridgeを追加。関連focused 111件、Postgres実DB 12件通過 |
| 2026-05-17 | UIコンポーネント方針を追加。Tailwind CSS + DaisyUIを標準、Flowbiteは保留、業務画面はtable/section中心、カードは繰り返し単位に限定 |
