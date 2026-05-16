# 開発計画書

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツールの開発計画
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- 関連文書: `requirements.md`, `functional-spec.md`, `test-plan.md`, `decision-log.md`, `AUTOMATION_NORTH_STAR.md`
- 最終更新: 2026-05-14

## 現在位置

2026-05-14時点では、移行計画書から開発ドキュメント初版を作成し、MVP実装の土台に着手済み。

実装済み・確認済みの範囲:

- FastAPIへ月次レポートAPIスタブを登録済み: `POST /api/monthly-reports/jobs`, `GET /api/monthly-reports/jobs`, `GET /api/monthly-reports/jobs/{job_id}`, `POST /api/monthly-reports/jobs/{job_id}/cancel`
- ジョブ状態モデル、prefix付き公開ID、モックジョブストアを実装済み
- `EB_ENABLE_MOCK_UI=1` のときに、レポート工房のジョブ一覧・新規作成・詳細・推敲エディタ・status fragment のモックUIを表示可能
- ローカル開発用モック認証の基本ユーザーを実装済み
- 非mock環境向けにSupabase JWT secretによるBearer token検証を実装済み。`aud=authenticated`、メールドメイン `tomonokai-corp.com`、不正token 401、ドメイン外 403、secret未設定 503 を確認済み
- 非mock環境ではジョブ作成時の `owner_user_id` をJWT `sub` から決め、一般ユーザーの一覧・詳細・成果物・検証・LLM呼び出しログ・stage操作を自分のジョブに制限する境界を実装済み。ローカルmockでは従来どおり全件参照を許可
- Supabase Postgres向け初期migrationとRLS migrationを作成済み。主要テーブルでRLSを有効化し、ジョブ所有者・credential所有者ベースのpolicyを静的テストで確認済み
- Supabase CLIでローカルDBを起動し、初期migrationを適用済み。WindowsのAnalytics health checkを避けるため、ローカル設定ではAnalyticsを無効化
- `EB_MONTHLY_REPORT_DATABASE_URL` 設定時に、月次レポートAPIがPostgres storeを使う経路を実装済み
- 明示的なジョブ進行APIを実装済み: `POST /api/monthly-reports/jobs/{job_id}/start`, `POST /api/monthly-reports/jobs/{job_id}/complete-stage`, `POST /api/monthly-reports/jobs/{job_id}/fail`
- Mock/Postgres storeで `queued -> running -> succeeded` のstage進行と、失敗時の `failed`・`error_type`・`error_message` 記録を実装済み。Postgresでは `monthly_report_jobs.error_type` / `error_message` に失敗詳細を明示保存し、監査ログにも失敗イベントを残す
- ソーススナップショットと生成成果物の保存/一覧APIを実装済み。Mock storeとPostgres storeの両方で `monthly_report_sources` / `monthly_report_artifacts` へ接続する最小経路を確認済み
- Google Workspace REST APIクライアントを追加済み。`gws` CLIには依存せず、Docs API / Sheets APIから取得した本文・valuesをソーススナップショットとして保存する `POST /api/monthly-reports/jobs/{job_id}/fetch-google-sources` を実装済み。ローカル疎通はサーバ側 `EB_GOOGLE_WORKSPACE_ACCESS_TOKEN` のみで行い、リクエストbodyやエラー本文には出さない
- Google provider refresh tokenのFernet暗号化保存境界とPostgres `google_oauth_credentials` upsertを実装済み。保存済みrefresh tokenからGoogle OAuth token endpointでaccess tokenを再取得し、`/fetch-google-sources` に渡せる解決経路を追加済み
- 認証済みユーザーに紐づくGoogle provider refresh token保存API `POST /api/auth/google-oauth/credentials` を追加済み。Supabase Auth callbackで取得したrefresh tokenを、このAPI経由で暗号化保存する前提
- Supabase session由来のGoogle provider refresh token保存ブリッジ `POST /api/auth/google-oauth/supabase-session` を追加済み。payloadのSupabase user id、provider、provider email、refresh token、scopeをサーバ側adapterで検証し、現在ユーザーID/メールと一致する場合だけ保存する。refresh tokenはrepr/レスポンス/エラー本文に出さない
- 検証結果の保存/一覧APIを実装済み。`monthly_report_validations` へ保存し、Mock/Postgres/API経由で確認済み
- ジョブ作成時に `prompt_version`, `template_hash`, `resolved_model_report`, `source_bundle_hash`, `app_version` などの再現性メタを保存・返却する経路を実装済み
- 月次レポートAPIに認証依存関係を接続済み。ローカルmockは固定ユーザー、非mockはSupabase JWT secretでBearer tokenを検証する
- 3件同時実行制限はStore側の `create_job_with_active_limit` へ寄せ、Postgresではユーザー単位のadvisory lockを使う経路を実装済み
- 編集画面に成果物保存パネルと `app_version` 表示を追加済み
- 再生成ジョブは対象月・世帯・作成者に加えて、template / prompt / model / source bundle / app version の再現性メタを引き継ぐ
- 静的POCの `build_prompts` を `src/eb_app/monthly_reports/llm_messages.py` へ共通化し、CLIは薄いラッパとして同じ関数を呼ぶ形に変更済み
- `prompt_scope_notes` をジョブ作成API、Mock/Postgres store、再生成コピー、レスポンスに追加済み。ローカルSupabaseには `202605140002_add_monthly_report_prompt_scope_notes.sql` を適用済み
- `src/eb_app/monthly_reports/workflow.py` で `build_messages -> provider mock -> validate -> persist` を1ジョブ通電済み。開発用API `POST /api/monthly-reports/jobs/{job_id}/run-mock` からも通せる
- OpenRouter APIキーのキー情報エンドポイント疎通は確認済み。OpenRouter `chat/completions` 用provider抽象はHTTPモックで実装済み。工房本体の `POST /api/monthly-reports/jobs/{job_id}/run-openrouter` から実ネットワーク通電し、`succeeded` / `draft_markdown` / `non_empty_markdown` 保存まで確認済み
- `llm_call_logs` へLLM呼び出しメタを保存する経路を実装済み。Mock/Postgres storeと `GET /api/monthly-reports/jobs/{job_id}/llm-calls` で、本文・プロンプト全文を出さずにhash、requested/resolved model、token、finish reason、error_typeを確認できる
- 非同期実行へ進める前段として、Store共通の `claim_next_queued_job()` と `src/eb_app/monthly_reports/worker.py` の `run_next_queued_monthly_report_job()` を実装済み。Postgresでは `FOR UPDATE SKIP LOCKED` で最古のqueued jobを原子的にclaimし、claim済みjobは `run_claimed_monthly_report_job()` で二重startせず実行する
- Economics 複数生徒MTGの匿名化フィクスチャを `tests/fixtures/monthly_reports/economics_multistudent_scope/` に追加し、`prompt_scope_notes` が根拠ソースより前にプロンプトへ入る回帰テストへ接続済み
- 決定的バリデーション `required_headings`, `forbidden_terms`, `multistudent_scope_exclusion` の第一弾を実装済み。テンプレートから抽出した `## 01...` 形式の必須見出し欠落、配布面禁止語、または `prompt_scope_notes` に明記された `対象外...様` のdraft混入がある場合、artifact保存前に `validation_failed` として停止する
- 静的POCの `HANDOFF_STATIC_POC_TUNING.md` をP0/P1/P2へ組み込み、`build_prompts` の塊順を工房側 `build_messages` の実装前提に追加済み
- クラウド本番リージョンは `asia-northeast1`（東京）を基本とする方針を決定済み
- focused pytestは `111 passed, 1 skipped`、Cloud Logging/PII/workflow/API/Auth focusedは `65 passed`、Cloud Logging/PII/workflow/API focusedは `42 passed`、直近統合focusedは `54 passed`、月次レポートAPI focusedは `22 passed`、schema focusedは `5 passed`、PII/Auth focusedは `27 passed`、PII/Auth/OAuth/GWS/API/backend/worker focusedは `86 passed, 1 skipped`、Postgres統合テストは `16 passed`。`.pytest_cache` 書き込み権限warningのみ確認

### 実装体制（Phase 1以降）

- Phase 1実装オーナー: FastAPI基盤、認証、ジョブ実行、Google Workspace連携の全体責任
- Backend & Data Agent: `src/eb_app/monthly_reports/*` のジョブ/ストア/API実装、RLS・保存ポリシー
- Auth & OAuth Agent: Supabase JWT検証、ドメイン制限、Google OAuth refresh token保存、provider token再取得
- LLM Pipeline Agent: `build_messages` / `call_llm` / `llm_call_logs` / provider抽象と失敗分類
- Validation & Safety Agent: 決定的バリデーション、PII/secret抑止、Cloud Logging allowlist、監査イベント
- UI/HTMX Agent: ジョブ一覧、進捗、プレビュー、推敲、フィードバック、再生成UI
- QA・運用エージェント: focused pytest運用、CI接続、E2E手順、pre-e2e-setup整備

### 次のE2E優先順（Phase 1以降）

- 最優先: Supabase Google provider実E2E取得 → `google-oauth/supabase-session` 保存 → `fetch-google-sources` → `run-openrouter` → `validation` → `artifact保存` を1ジョブで通す
- 優先: worker常駐実行接続、3件制限の実環境再現、再現性メタ継承（prompt/version/template/model/source hash）、LLM失敗時の再試行/再生成導線をE2Eで閉じる
- 仕上げ: 編集後Markdown保存、再生成API/UI、モデル版比較、HTMLエクスポート/保存/送付の最小導線、Playwright最小シナリオで体験を通す

## マイルストーン

| フェーズ | 状況 | 成果物 | 完了条件 |
|---|---|---|---|
| Phase 0: 整備 | 進行中 | プロンプト断片正本化、prompt_version、ジョブ表現スタブ | スクリプトとアプリが同じプロンプト断片を参照できる |
| Phase 1: MVP | 骨格実装済み・OAuth未通電・LLM少量通電済み | Supabase Postgres、OAuth取得、ジョブ保存、モックLLM、Markdown生成、検証、フィードバック | 実案件でチューニング記録を残しながら生成できる |
| Phase 2: 品質 | テスト骨格あり・実検証一部接続 | 決定的バリデーション拡充、pytest、provider mock、GitHub Actions、エラーハンドリング | CIでモック生成パイプラインが通る |
| Phase 3: MVP体験完成 | モック着手 | 現行HTML全文エディタ相当の推敲、HTMLエクスポート、ファイル保存、送付エクスポート、再生成、版切替、Playwright | 現行全文エディタの必須操作をサーバ保存前提で内包し、Playwrightで確認できる |
| Phase 4: 統合 | 未着手 | Supabaseポータル統合、ジョブ履歴一本化 | ポータル計画と矛盾しない形で統合 |

## Phase 0 タスク

| ID | 状態 | タスク |
|---|---|---|
| P0-01 | 済 | `monthly_report_draft_openrouter.py` の `build_prompts` を `src/eb_app/monthly_reports/llm_messages.py` などへ抽出し、CLIと工房workerが同じ関数を呼ぶ形にする |
| P0-02 | 未着手 | `src/eb_app/prompts/monthly/` を作成し、system、artifact指示、family-facing tone、validation repairなどのプロンプト断片を置く |
| P0-03 | 設計済み・未実装 | `prompt_version` を `monthly-report-vYYYYMMDD.N` 形式で管理し、静的レシピID・template_hash・Git SHAと対応付ける仕組みを作る |
| P0-04 | 済 | `POST /api/monthly-reports/jobs` のモック応答スタブを作る |
| P0-05 | 済 | ジョブ状態モデルをコードに定義する |
| P0-06 | 済 | `build_messages` の塊順テストを追加する。契約、`prompt_scope_notes`、根拠ソース、構造参考、語感参考、artifact指示の順を固定する |
| P0-07 | 一部完了 | 静的レシピ `prompts.scope_reminder` を工房ジョブの正式フィールド `prompt_scope_notes` へ変換し、手入力でも指定できる層を用意する |

## Phase 1 タスク

| ID | 状態 | タスク |
|---|---|---|
| P1-01 | 一部完了 | Supabase Auth Google providerとドメイン制限。FastAPI側のJWT secret検証とメールドメイン制限は実装済み、実Supabase Auth Google providerからのE2E token取得は未確認 |
| P1-02 | 一部完了 | ローカル開発用モック認証 |
| P1-03 | 一部完了 | Supabase Postgresの初期スキーマ、接続設定、RLS migration。主要テーブルのRLS有効化と所有者policyは静的テスト済み、実Supabase Auth roleでのDB-level E2Eは後続 |
| P1-04 | 一部完了 | Google provider refresh tokenのFernet暗号化保存とCloud Run Secret鍵管理。暗号化保存/復号/refresh境界、保存API、provider/email/scope検証付きSupabase session保存ブリッジは実装済み。実Supabase Auth callbackでのprovider token取得処理は未実装 |
| P1-05 | 一部完了 | ユーザーOAuthによるSheets / Docs取得。REST APIクライアント、保存API、暗号化済みrefresh tokenからのaccess token解決は実装済み、Supabase Auth provider token取得の実環境検証は未実施 |
| P1-06 | 一部完了 | ソーススナップショット保存 |
| P1-07 | 一部完了 | 非同期ジョブ作成、3件制限、明示的なstage進行API。DB-backed workerのclaim境界は実装済み、常駐worker/Cloud Run実行方式は未着手 |
| P1-08 | 一部完了 | OpenRouter呼び出し抽象。まずprovider mockで `call_llm` を通し、その後少量 `chat/completions` で工房本体から疎通確認する |
| P1-09 | 一部完了 | Markdown草稿保存 |
| P1-10 | 一部完了 | 最低限の決定的バリデーション。空出力、必須見出し、配布面禁止語、複数生徒スコープ混入の第一弾を実装済み |
| P1-11 | 一部着手 | ジョブ一覧・詳細・プレビュー画面 |
| P1-12 | 一部完了 | フィードバック保存 |
| P1-13 | 済 | 肥大化時にSupabase Storageへ移すための `storage_path` カラムを初期スキーマに含める |

## Phase 2 タスク

| ID | 状態 | タスク |
|---|---|---|
| P2-01 | 一部完了 | ゴールデンフィクスチャ整備。Economics 複数生徒MTGの匿名化版を追加し、プロンプト構築テストへ接続済み |
| P2-02 | 済 | provider mockで結合テスト。`build_messages -> call_llm mock -> validate -> persist` を1ジョブで通す |
| P2-03 | 一部完了 | バリデーションルール拡充。`non_empty_markdown`, `required_headings`, `forbidden_terms`, `multistudent_scope_exclusion` 第一弾を実装済み |
| P2-04 | 一部完了 | 失敗stageとerror_typeの体系化 |
| P2-05 | 一部完了 | PII/secret抑止テスト。OpenRouter、Google Workspace、Google OAuth token refresh、validation失敗時に本文・token・secret・外部API本文が外向きエラーへ出ないことを確認済み。Cloud Logging向け構造化ログallowlistとworkflow失敗/成功時の実ログ出力検査も実装済み。Cloud Run上の実ログ検索確認は後続 |
| P2-06 | 未着手 | GitHub Actionsでpytestを実行 |
| P2-07 | 一部完了 | 匿名化済みゴールデンフィクスチャ作成 |
| P2-08 | 一部完了 | 複数生徒MTG混入防止テスト。`prompt_scope_notes` により対象外の別姓＋様の評価文が家庭向け本文へ混入しないことを確認 |

## Phase 3 タスク

| ID | 状態 | タスク |
|---|---|---|
| P3-01 | 未着手 | 編集後Markdown保存 |
| P3-02 | 未着手 | 再生成API/UI |
| P3-03 | 未着手 | 管理者向けprompt/model override |
| P3-04 | モック着手 | 現行HTML全文エディタ由来のiframe編集領域と1行ツールバー |
| P3-05 | モック着手 | HTMLソース直接編集 |
| P3-06 | モック着手 | HTMLエクスポート |
| P3-07 | モック着手 | ファイル保存・ファイルから開く |
| P3-08 | モック着手 | 送付エクスポート |
| P3-09 | 未着手 | 生成物と最終編集後HTML/Markdownの簡易テキスト差分表示 |
| P3-10 | 未着手 | Playwrightによるエディタ体験・保存・差分・送付エクスポートE2E |
| P3-11 | 未着手 | 既存静的プレビュー経路との接続 |

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

## 依存関係

- Supabaseスキーマ案は初期migrationとして作成済み。Postgres storeも追加済み。次はRLS、実Supabase Auth検証、実ジョブ永続化の拡張が必要。
- 月次レポートAPIは認証依存関係を通す。ローカルMVPでは `owner_user_id` 暫定値を許可し、Supabase Auth接続時は認証ユーザーIDへ差し替える。
- prompt_version管理が決まらないと、チューニング比較が曖昧になる。
- U-025は解決済み。静的POCの `prompts.scope_reminder` は工房ジョブ/APIでは `prompt_scope_notes` とする。初期投入はレシピ由来 + 手入力可能、householdメタからの自動生成は後続に回す。
- ジョブ状態モデル、モックAPI、DB永続化、3件制限、`prompt_scope_notes` 保存、provider mock通電、実OpenRouter少量通電、LLM呼び出しメタ保存、DB-backed workerのclaim境界は骨格実装済み。次は常駐worker/Cloud Run実行方式と、実案件ソースでのチューニング比較UIが必要。
- OpenRouter呼び出し抽象は実装済み。キー情報エンドポイントと `chat/completions` の工房本体通電は確認済み。
- 実Supabase Auth + Google OAuth + Google Workspace read flowのライブE2E前設定は [pre-e2e-setup.md](pre-e2e-setup.md) を参照する。
- Auth & OAuth Agentの初手として、`/auth/google` と `/auth/callback` のE2Eブリッジを追加済み。`SUPABASE_URL` / `SUPABASE_ANON_KEY` だけをブラウザへ渡し、Supabase sessionの `provider_refresh_token` は `/api/auth/google-oauth/supabase-session` へ送って暗号化保存する。
- 実装体制として、Phase 1以降は実装オーナー＋Backend/Auth/LLM/Validation/UI/QAの役割分担を固定し、同一ファイルの同時編集を避ける運用で進める。
- 次のE2E優先順は「Google provider実E2E」「worker常駐実行」「再現性メタ継承」「再生成体験」「最小Playwright導線」の順で固定。

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
| 2026-05-16 | Auth & OAuth Agentの初手として `/auth/google`・`/auth/callback` のE2Eブリッジ、Supabase公開設定、pre-e2e手順、focusedテスト結果を反映 |
