# API定義書

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツールのAPI定義
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- 関連文書: `functional-spec.md`, `screen-design.md`, `data-design.md`
- 最終更新: 2026-05-19

## 方針

- 通常画面は `/monthly-reports/*` のHTMLページとHTML断片で構成する。Jinja2 + HTMXの差し替え先にそのまま挿入できるレスポンスを返し、フロントJSでJSONからDOMを組み立てない。
- JSON APIは `/api/monthly-reports/*` に置く。用途は worker、E2E、管理スクリプト、将来連携に限定し、通常UIからDOM更新目的で直接叩かない。
- HTML fragment APIは `/monthly-reports/*/fragments/*` に置く。画面のPOST操作は原則としてHTML断片、リダイレクト、またはHXヘッダーで応答する。
- LLM生成は同期 `generate` ではなく、ジョブ作成と状態取得に分ける。
- Supabase Authで認証済みのユーザーのみアクセス可能とする。
- FastAPI側はSupabase Authセッションを検証し、`tomonokai-corp.com` ドメイン制限を適用する。
- ローカル環境では `EB_AUTH_MODE=mock` のときだけ開発用モックユーザーを注入する。
- 本番SSR/HTMX UIは `HTTPOnly`, `Secure`, `SameSite=Lax` Cookieを正とし、POST/PUT/DELETE相当の画面操作はCSRF対策を通す。Bearer token検証はE2E、内部API、移行中の互換経路として扱う。
- 月次レポートAPIは `get_current_user` 相当の依存関係を通す。移行期の非mock JSON APIではBearer tokenをSupabase JWT secretで検証し、`aud=authenticated` と `tomonokai-corp.com` ドメインを要求する。
- 非mock環境では、ジョブ作成時の `owner_user_id` はリクエストbodyではなく認証ユーザーIDから決める。ジョブ一覧・詳細・成果物・検証・LLM呼び出しログ・stage操作は、一般ユーザーには自分のジョブだけを返す。他ユーザーのジョブIDは404として扱う。admin roleは全ジョブ参照を許可する。
- POST系APIとHTML actionは二重送信・リロード・worker再試行に耐えるよう、Idempotency-Keyまたはjob input hashによる冪等性を設計する。
- DB主キーはUUIDとし、API・画面・ログではprefix付きIDを使う。
- MVPの進捗更新はHTMXポーリングに統一する。SSEは後続検討とする。
- Supabase AuthのOAuth開始・callback APIは認証基盤側の責務とし、本API定義には含めない。

## JSON Write API Caller Intent

JSON write APIs are kept for worker, E2E, admin scripts, and future integration. They are not the normal UI DOM update path. Until each route is fully moved behind RLS write clients or server RPC, every JSON write route must declare the intended caller and whether it may be exposed to a normal Supabase user.

For direct DB state mutation routes, nonmock callers must send `X-EB-Caller-Intent`. The currently accepted values are `e2e` and `admin`; `admin` also requires an authenticated admin role.

| API | Intended caller | Current boundary | Normal user exposure | Next P1-16 action |
|---|---|---|---|---|
| `POST /api/monthly-reports/jobs` | Normal integration / E2E / admin script | Service-owned direct insert. Auth user becomes owner in nonmock; active-limit and idempotency are enforced in the service layer, not via user-JWT write. | Allowed for future integration, not used by normal HTMX UI | Keep as service-owned create command unless product pressure justifies create-job RPC |
| `POST /api/monthly-reports/jobs/{job_id}/feedback` | Normal integration / E2E | RLS read preflight, then user-JWT Supabase write when available; mock/admin fallback direct | Allowed | Keep as first full-RLS write POC and add real Supabase/Postgres smoke |
| `POST /api/monthly-reports/jobs/{job_id}/sources` | E2E / admin script / future integration | RLS read preflight, then user-JWT Supabase source write when available; mock/admin fallback direct | Allowed for future integration, not used by normal HTMX UI | Keep owner/non-owner/idempotency smoke and decide whether to freeze here or move to RPC for Storage migration |
| `POST /api/monthly-reports/jobs/{job_id}/fetch-google-sources` | E2E / admin script / future integration | RLS read preflight, server-side Google token resolution, then user-JWT Supabase source write when available; mock/admin fallback direct | Transitional; normal UI uses HTML fragment route | Keep token handling server-side and leave only token refresh / workflow paths on direct DB |
| `POST /api/monthly-reports/jobs/{job_id}/artifacts` | E2E / admin script / future integration | RLS read preflight, then user-JWT Supabase artifact write for append-only artifact paths when available; mock/admin fallback direct | Transitional; do not expose as normal user editing boundary | Continue narrowing to direct DB only for worker/stateful paths and decide whether remaining artifact writes need RPC |
| `POST /api/monthly-reports/jobs/{job_id}/validations` | Worker / E2E / admin script | RLS read preflight, then user-JWT Supabase validation write when available; mock/admin fallback direct; idempotency remains service-owned/direct. Nonmock requires `X-EB-Caller-Intent: e2e|admin`. | Not exposed as normal user JSON API | Keep worker/admin intent explicit and decide whether validation persistence should stay mixed-boundary or move behind worker-only paths |
| `POST /api/monthly-reports/jobs/{job_id}/start` | E2E / admin script / legacy manual control | RLS read preflight, then direct state mutation. Nonmock requires `X-EB-Caller-Intent: e2e|admin`. | Not exposed as normal user JSON API; normal UI uses HTML actions | Move to worker-only/server-owned workflow boundary before production hardening |
| `POST /api/monthly-reports/jobs/{job_id}/complete-stage` | E2E / admin script / legacy manual control | RLS read preflight, then direct state mutation. Nonmock requires `X-EB-Caller-Intent: e2e|admin`. | Not exposed as normal user JSON API | Worker-only or admin-only route before production exposure |
| `POST /api/monthly-reports/jobs/{job_id}/fail` | Worker / admin recovery / E2E | RLS read preflight, then direct state mutation. Nonmock requires `X-EB-Caller-Intent: e2e|admin`. | Not exposed as normal user JSON API | Move worker failure persistence behind worker-only code path and keep admin recovery explicit |
| `POST /api/monthly-reports/jobs/{job_id}/manual-recovery/fail` | Admin recovery only | RLS read preflight, then direct fail transition with `manual_recovery_required` and PII-safe server-side audit log. Nonmock requires `X-EB-Caller-Intent: admin`. Only `running` jobs are accepted. | Not exposed as normal user JSON API | Keep as the explicit stuck-job recovery command until a fuller admin/worker maintenance surface exists |
| `POST /api/monthly-reports/jobs/{job_id}/cancel` | E2E / admin script | RLS read preflight, then direct cancel request. Nonmock requires `X-EB-Caller-Intent: e2e|admin`. | Not exposed as normal user JSON API; normal UI uses HTML action | Later move to RLS/RPC or server-owned cancel command |
| `POST /api/monthly-reports/jobs/{job_id}/run-mock` | E2E / local tuning / admin script | RLS read preflight, direct workflow execution. Nonmock requires `X-EB-Caller-Intent: e2e|admin`. | E2E/admin only | Keep disabled from normal user JSON flows; later move to worker-owned path |
| `POST /api/monthly-reports/jobs/{job_id}/run-openrouter` | E2E / local tuning / admin script | RLS read preflight, direct workflow execution with server-held OpenRouter key. Nonmock requires `X-EB-Caller-Intent: e2e|admin`. | E2E/admin only | Worker-owned path before broader production exposure |
| `POST /api/monthly-reports/jobs/{job_id}/rerun` | E2E / admin script | RLS read preflight, then direct job clone. Nonmock requires `X-EB-Caller-Intent: e2e|admin`. | Not exposed as normal user JSON API; normal UI uses HTML action | Move clone semantics and active-limit check behind RLS/RPC or service layer |
| `POST /api/monthly-reports/jobs/{job_id}/validate` | Future integration / E2E | Not part of the current primary implementation | Not exposed until implemented | Define caller intent before implementation |

### Direct DB / direct store を許容するカテゴリ

RLS 主境界へ寄せた後も、以下は server-owned として direct DB / direct store を残す。

| カテゴリ | 代表箇所 | 理由 | 通常ユーザー可視性 |
|---|---|---|---|
| idempotency record / response | `monthly_report_idempotency_keys`, idempotent response 記録 | 二重送信・再試行の横断制御を service-owned に保つため | 直接は見えない |
| audit_logs | approval / export / HTML source / distribution / workflow request/start の監査 | 監査イベントをクライアント可視境界から分離し、worker-owned request と service-owned workflow 実行の入口記録も server-side に寄せるため | 直接は見えない |
| llm_call_logs | source summary / worker generation の LLM call metadata | token / model / request hash 等の運用・再現性メタを server-owned telemetry として扱うため | GET API ではメタのみ可視、本文やプロンプト全文は返さない |
| worker/state mutation | `start` / `complete-stage` / `fail` / `cancel` / `run-*` / `rerun` | 状態遷移、lease、retry、OpenRouter key 保持を service-owned workflow に閉じるため | 通常UIの編集境界ではない |
| job creation | `POST /api/monthly-reports/jobs` | active-limit / owner 決定 / idempotency を service command として一元化するため | 将来連携用。通常 HTMX UI のDOM更新には使わない |

### 通常UIでなお direct store を併用する経路

- `POST /monthly-reports/jobs/{job_id}/fragments/source-summary`
  source 読み取りは RLS read、`source_summary_markdown` 保存は RLS write、`llm_call_logs` だけ direct telemetry。
- `POST /monthly-reports/jobs/{job_id}/fragments/google-sources` with `after_fetch_action=generate_openrouter`
  source 保存までは RLS write。`mock/admin` はそのまま service-owned workflow で即時生成するが、通常Supabaseユーザーは source 保存後に worker-owned workflow request を監査ログへ記録し、`EB_CLOUD_RUN_WORKER_JOB_*` が設定されている環境では Cloud Run Jobs `jobs.run` を server-side trigger しつつ、queued job のまま worker 処理待ちへ進める。
- `POST /monthly-reports/jobs/{job_id}/run`
  通常UIの実行入口。`run_mode=mock|openrouter` は `mock/admin` の補助導線として service-owned workflow を即時実行し、通常Supabaseユーザーの既定 `run_mode=stage` は worker-owned workflow request を記録し、Cloud Run worker trigger が設定済みなら `EB_WORKER_JOB_ID=<job_id>` override 付きで worker job を起動する。

## ID形式

| 対象 | DB主キー | 表示/API ID例 |
|---|---|---|
| monthly_report_jobs | UUID | `mrj_01HX...` |
| monthly_report_sources | UUID | `mrs_01HX...` |
| monthly_report_artifacts | UUID | `mra_01HX...` |
| monthly_report_validations | UUID | `mrv_01HX...` |
| llm_call_logs | UUID | `llm_01HX...` |

prefix付きIDはログ・問い合わせ・URLで対象種別を判別しやすくするために使う。DB内部の参照整合性はUUIDで扱う。

## JSON API

## Auth API

### POST `/api/auth/google-oauth/credentials`

認証済みユーザーに紐づくGoogle provider refresh tokenを暗号化保存する。Supabase AuthのOAuth callbackまたはサーバ側セッション処理でprovider refresh tokenを取得した直後に呼ぶ想定。refresh tokenはレスポンスに返さない。

```json
{
  "provider_refresh_token": "1//...",
  "scope": "openid email profile https://www.googleapis.com/auth/documents.readonly https://www.googleapis.com/auth/spreadsheets.readonly https://www.googleapis.com/auth/drive.readonly"
}
```

成功時:

```json
{
  "credential_id": "goc_...",
  "provider": "google",
  "scope": "openid ...",
  "encryption_key_version": "local-v1"
}
```

`EB_MONTHLY_REPORT_DATABASE_URL` または `EB_GOOGLE_TOKEN_ENCRYPTION_KEY` 未設定時は503。未認証時は401。平文refresh tokenはDB・レスポンス・ログへ出さない。

### POST `/api/auth/google-oauth/supabase-session`

Supabase Authセッション処理で得たGoogle provider refresh tokenを、FastAPI側の現在ユーザーに紐づけて暗号化保存するサーバ側ブリッジ。OAuth開始・callback自体はSupabase Auth側に置き、このAPIは「Supabase session上のuser id」とFastAPIが検証した現在ユーザーが一致する場合だけ保存する。

```json
{
  "supabase_user_id": "user@example.tomonokai-corp.com",
  "provider": "google",
  "provider_user_id": "google-sub-...",
  "email": "user@example.tomonokai-corp.com",
  "provider_refresh_token": "1//...",
  "scope": "openid email profile https://www.googleapis.com/auth/documents.readonly https://www.googleapis.com/auth/spreadsheets.readonly https://www.googleapis.com/auth/drive.readonly"
}
```

レスポンスは `/google-oauth/credentials` と同じ。`supabase_user_id` が現在ユーザーと一致しない場合は403。`provider` がGoogle以外の場合、refresh tokenやscopeが空の場合は422。`email` が現在ユーザーのメールと一致しない場合は403。refresh tokenはレスポンス、ログ、エラー本文へ出さない。

### POST `/api/monthly-reports/jobs`

ジョブを作成する。MVPローカルmockでは `owner_user_id` を暫定指定できる。非mock環境では、リクエスト値ではなく認証ユーザーIDから作成者を決める。

```json
{
  "target_month": "2026-04",
  "household_key": "demo_household_takafuji",
  "owner_user_id": "mock-user",
  "spreadsheet_id": "...",
  "doc_ids": ["..."],
  "template_key": "pattern_b",
  "notes": "任意メモ",
  "source_preset": "pattern_b_gws_sl",
  "prompt_scope_notes": "対象は平林様 Economics のみ。別姓＋様の段落は根拠から除外する。",
  "ideal_html_key": "tokura_2026-04_user_ideal",
  "structure_reference_key": "ideal_html",
  "artifact_type": "draft_markdown",
  "prompt_version": "monthly-report-v20260514.1",
  "template_hash": "sha256:...",
  "model_report": "anthropic/claude-sonnet-4.6",
  "model_light": "openai/gpt-4.1-mini",
  "resolved_model_report": "anthropic/claude-sonnet-4.6",
  "source_bundle_hash": "sha256:...",
  "app_version": "git-sha-or-image-digest"
}
```

成功時:

```json
{
  "job_id": "mrj_...",
  "status": "queued",
  "owner_user_id": "mock-user",
  "template_key": "pattern_b",
  "source_preset": "pattern_b_gws_sl",
  "prompt_scope_notes": "対象は平林様 Economics のみ。別姓＋様の段落は根拠から除外する。",
  "ideal_html_key": "tokura_2026-04_user_ideal",
  "structure_reference_key": "ideal_html",
  "artifact_type": "draft_markdown",
  "prompt_version": "monthly-report-v20260514.1",
  "template_hash": "sha256:...",
  "model_report": "anthropic/claude-sonnet-4.6",
  "model_light": "openai/gpt-4.1-mini",
  "resolved_model_report": "anthropic/claude-sonnet-4.6",
  "source_bundle_hash": "sha256:...",
  "app_version": "git-sha-or-image-digest"
}
```

### GET `/api/monthly-reports/jobs`

ジョブ一覧を返す。

クエリ:

- `target_month`
- `status`
- `mine`
- `has_errors`

### GET `/api/monthly-reports/jobs/{job_id}`

ジョブ詳細、ソース、成果物、検証サマリを返す。

### POST `/api/monthly-reports/jobs/{job_id}/start`

ジョブを `queued` から `running` へ進め、最初のstageを `fetch_sources` にする。MVPの明示制御APIで、後続の非同期worker実装では内部呼び出しへ寄せる。

### POST `/api/monthly-reports/jobs/{job_id}/complete-stage`

現在stageを完了し、次stageへ進める。最終stage `persist` 完了後は `succeeded` になる。不正遷移は409を返す。

### POST `/api/monthly-reports/jobs/{job_id}/fail`

ジョブを `failed` にし、失敗分類と概要を保存する。`error_type` / `error_message` は `monthly_report_jobs` の明示カラムへ保存し、監査ログにもイベントを残す。

```json
{
  "error_type": "provider_timeout",
  "error_message": "OpenRouter timed out"
}
```

### POST `/api/monthly-reports/jobs/{job_id}/run-mock`

開発・テスト用のprovider mock通電API。保存済みソースを束ね、`build_messages -> call_llm mock -> validate -> persist` を同期的に1回実行する。実OpenRouterは呼ばない。

```json
{
  "content": "# 4月度 月次レポート\n\n本文..."
}
```

成功時はジョブが `succeeded` になり、`draft_markdown` artifact と `non_empty_markdown` validation を保存する。空出力、テンプレート由来の必須見出し欠落、配布面禁止語、または `prompt_scope_notes` で明示された対象外生徒のdraft混入など決定的バリデーションエラーがある場合は、artifact保存前に `validation_failed` としてジョブを `failed` にする。

### POST `/api/monthly-reports/jobs/{job_id}/run-openrouter`

OpenRouter実providerで、保存済みソースを束ね、`build_messages -> call_llm -> validate -> persist` を同期的に1回実行する。MVP初期の手動通電・少量検証用であり、後続で非同期workerへ寄せる。

リクエストbodyなし。実行時設定:

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL_REPORT`。未指定時は `OPENROUTER_MODEL`、さらに未指定なら既定モデル
- `OPENROUTER_TIMEOUT`
- `OPENROUTER_MAX_TOKENS`

`OPENROUTER_API_KEY` 未設定時は503を返す。provider呼び出し失敗時はジョブを `failed` にし、`error_type = provider_call_failed` とする。

### POST `/api/monthly-reports/jobs/{job_id}/rerun`

同一ソーススナップショットから再生成する。

```json
{
  "model_report": "anthropic/claude-sonnet-4.6",
  "prompt_version": "monthly-report-v1",
  "template_version": "pattern-b-2026-05-13"
}
```

### POST `/api/monthly-reports/jobs/{job_id}/feedback`

フィードバックを保存する。

```json
{
  "category": "tone",
  "comment": "保護者向けにやや硬い",
  "final_markdown": "任意"
}
```

### POST `/api/monthly-reports/jobs/{job_id}/sources`

ソーススナップショットを保存する。Google API取得実装前のMVPでは、取得済み本文やhashをジョブに紐づける最小APIとして使う。

```json
{
  "source_type": "doc",
  "display_name": "面談メモ",
  "snapshot_text": "取得済み本文",
  "content_hash": "sha256:..."
}
```

成功時:

```json
{
  "source_id": "mrs_...",
  "job_id": "mrj_...",
  "source_type": "doc",
  "display_name": "面談メモ",
  "snapshot_text": "取得済み本文",
  "content_hash": "sha256:..."
}
```

### GET `/api/monthly-reports/jobs/{job_id}/sources`

ジョブに紐づくソーススナップショット一覧を返す。

### POST `/api/monthly-reports/jobs/{job_id}/fetch-google-sources`

Google Workspace REST APIからSheets / Docsを取得し、`monthly_report_sources` にソーススナップショットとして保存する。アプリコードは `gws` CLIを呼ばず、Docs API / Sheets APIをHTTPで呼び出す。

MVP初期のローカル開発では、サーバ側環境変数 `EB_GOOGLE_WORKSPACE_ACCESS_TOKEN` が設定されている場合はそれを使う。未設定の場合は、`google_oauth_credentials` に暗号化保存されたprovider refresh tokenを復号し、Google OAuth token endpointでaccess tokenを再取得して使う。本番ではaccess tokenやrefresh tokenをリクエストbodyやフロントに置かない。

```json
{
  "doc_ids": ["1abc..."],
  "sheet_ranges": [
    {
      "spreadsheet_id": "1sheet...",
      "range_name": "student",
      "display_name": "基本情報 student"
    },
    {
      "spreadsheet_id": "1sheet...",
      "range_name": "'lesson plan'",
      "display_name": "学習計画表 lesson plan"
    }
  ]
}
```

通常HTML UIでは、ユーザーに `range_name` を入力させない。Spreadsheet URL/IDだけを受け取り、既定では `student` と `lesson plan` の使用範囲全体を取得する。シート名が異なる場合は `GET /monthly-reports/jobs/{job_id}/fragments/sheet-selector` でシート名一覧を取得し、基本情報シートと学習計画表シートを選択する。

取得後の確認用に、通常HTML UIは `POST /monthly-reports/jobs/{job_id}/fragments/source-summary` を提供する。保存済みソースを `OPENROUTER_MODEL_LIGHT` で要約し、HTML fragmentで `取得内容サマリー`、`対象・期間・科目の確認`、`ズレ/不足の可能性` を返す。結果は `source_summary_markdown` artifactとして保存し、LLM呼び出しメタは `llm_call_logs.prompt_kind=source_summary` へ保存する。未取得時は422、OpenRouter APIキー未設定時は503、provider失敗時は502のHTML error fragmentを返す。

成功時:

```json
{
  "sources": [
    {
      "source_id": "mrs_...",
      "job_id": "mrj_...",
      "source_type": "google_doc",
      "display_name": "教師MTG",
      "snapshot_text": "取得本文...",
      "content_hash": "sha256:..."
    }
  ]
}
```

`EB_GOOGLE_WORKSPACE_ACCESS_TOKEN` も保存済みcredentialからのaccess token解決も使えない場合は503、Google API呼び出しまたはOAuth token refresh失敗時は502を返す。エラー本文にはaccess token、refresh token、client secret、Google APIレスポンス本文を含めない。

### POST `/api/monthly-reports/jobs/{job_id}/artifacts`

生成成果物を保存する。MVP初期は `draft_markdown` を主対象とし、後続で `draft_html`, `final_markdown`, `final_html`, `exported_html` を追加する。

```json
{
  "artifact_type": "draft_markdown",
  "content": "# 4月度 月次レポート",
  "content_hash": "sha256:..."
}
```

成功時:

```json
{
  "artifact_id": "mra_...",
  "job_id": "mrj_...",
  "artifact_type": "draft_markdown",
  "content": "# 4月度 月次レポート",
  "content_hash": "sha256:..."
}
```

### GET `/api/monthly-reports/jobs/{job_id}/artifacts`

ジョブに紐づく成果物一覧を返す。

### POST `/api/monthly-reports/jobs/{job_id}/validations`

決定的バリデーションの結果を保存する。

```json
{
  "rule_id": "required-heading",
  "severity": "error",
  "message": "学習の進捗セクションがありません",
  "path": "sections.learning_progress"
}
```

### GET `/api/monthly-reports/jobs/{job_id}/validations`

ジョブに紐づく検証結果一覧を返す。

### GET `/api/monthly-reports/jobs/{job_id}/llm-calls`

ジョブに紐づくLLM呼び出しログを返す。本文・プロンプト全文は返さず、チューニング比較に必要なhashとメタだけを返す。

```json
{
  "llm_calls": [
    {
      "llm_call_id": "llm_...",
      "job_id": "mrj_...",
      "prompt_kind": "report",
      "provider": "openrouter",
      "requested_model": "openrouter/auto",
      "resolved_model": "anthropic/claude-sonnet-4.6",
      "prompt_version": "monthly-report-v20260514.1",
      "request_hash": "sha256:...",
      "response_hash": "sha256:...",
      "latency_ms": 1234,
      "input_tokens": 111,
      "output_tokens": 222,
      "finish_reason": "stop",
      "error_type": null
    }
  ]
}
```

### POST `/api/monthly-reports/jobs/{job_id}/cancel`

ジョブのキャンセルを要求する。

成功時:

```json
{
  "job_id": "mrj_...",
  "status": "cancel_requested"
}
```

`queued` の場合は即時 `cancelled` にしてよい。`running` の場合は協調的キャンセルとし、実行中stageの終了後に `cancelled` へ遷移する。

### POST `/api/monthly-reports/jobs/{job_id}/validate`

編集後Markdownを再検証する。

```json
{
  "markdown": "# ..."
}
```

## HTML fragment API

通常画面の操作はこの層を優先する。エラー時もJSONを返さず、対象領域に差し込めるalert/status断片を返す。

| API | 用途 |
|---|---|
| `GET /monthly-reports` | レポート工房トップ |
| `GET /monthly-reports/jobs` | ジョブ一覧ページ |
| `GET /monthly-reports/jobs/new` | 新規ジョブ作成ページ |
| `POST /monthly-reports/jobs` | ジョブ作成後、ジョブカードまたは詳細への遷移指示を返す |
| `GET /monthly-reports/jobs/{job_id}` | ジョブ詳細ページ |
| `GET /monthly-reports/jobs/{job_id}/edit` | プレビュー・推敲ページ |
| `POST /monthly-reports/jobs/{job_id}/run` | 生成開始後の進捗パネルまたはエラー断片。通常 `run_mode=stage` は queued job を worker-owned workflow へ渡す依頼として扱い、`run_mode=mock` はモック生成を完了まで実行し、`run_mode=openrouter` はOpenRouter生成を実行する |
| `POST /monthly-reports/jobs/{job_id}/rerun` | 再生成ジョブ作成後の作成通知、新ジョブ詳細リンク、進捗断片 |
| `POST /monthly-reports/jobs/{job_id}/cancel` | キャンセル要求後の状態断片 |
| `GET /monthly-reports/jobs/{job_id}/fragments/status` | 進捗表示 |
| `GET /monthly-reports/jobs/{job_id}/fragments/sources` | ソース確認 |
| `POST /monthly-reports/jobs/{job_id}/fragments/sources` | 手動ソース保存後のUI |
| `POST /monthly-reports/jobs/{job_id}/fragments/google-sources` | Google Docs/Sheets取得後のソースUI。CSRF必須。成功時はsources断片、設定不足/取得失敗時はalert断片 |
| `GET /monthly-reports/jobs/{job_id}/fragments/preview` | プレビュー差し替え |
| `GET /monthly-reports/jobs/{job_id}/fragments/validation` | 検証結果 |
| `GET /monthly-reports/jobs/{job_id}/fragments/artifacts` | 成果物一覧 |
| `POST /monthly-reports/jobs/{job_id}/fragments/feedback` | フィードバック保存後のUI |
| `POST /monthly-reports/jobs/{job_id}/fragments/edited-markdown` | 編集後Markdown保存後のpreview/edit UI。`base_content_hash` が古い場合は409相当のHTML error fragment |
| `GET /monthly-reports/jobs/{job_id}/fragments/diff` | draft/finalの簡易テキスト差分 |
| `GET /monthly-reports/jobs/{job_id}/fragments/approval` | 承認状態、ブロック理由、承認フォーム |
| `POST /monthly-reports/jobs/{job_id}/fragments/approval` | 人間承認保存後の承認panel |
| `GET /monthly-reports/jobs/{job_id}/fragments/export` | HTMLエクスポート状態/成果物 |
| `POST /monthly-reports/jobs/{job_id}/fragments/export` | 承認済み配布artifactから `export_html` artifactを作成 |
| `GET /monthly-reports/jobs/{job_id}/fragments/html-source` | 最新 `export_html` のHTMLソース編集panel |
| `POST /monthly-reports/jobs/{job_id}/fragments/html-source` | 編集済みHTMLを新しい `export_html` artifactとして保存 |
| `GET /monthly-reports/jobs/{job_id}/fragments/distribution` | 手動送付用distribution package状態 |
| `POST /monthly-reports/jobs/{job_id}/fragments/distribution` | 承認済みHTML exportを `distribution_package` artifactとして固定 |
| `GET /monthly-reports/jobs/{job_id}/fragments/rerun-comparison` | 比較先ジョブIDを受け、prompt/model/template/source hash/app versionを横並び表示。同一世帯/同一ユーザーの比較候補も返す |
| `GET /monthly-reports/jobs/{job_id}/fragments/rerun-diff` | 比較先ジョブIDを受け、元/比較先ジョブの最新Markdown本文を行単位で比較 |
| `GET /monthly-reports/legacy-full-editor` | 既存全文エディタを同一オリジンで開く互換route |
| `GET /monthly-reports/jobs/{job_id}/legacy-full-editor` | 最新 `export_html` artifactを既存全文エディタのlocalStorageへ投入して開くbridge |

## エラー

| HTTP | ケース |
|---:|---|
| 401 | 未ログイン |
| 403 | ドメイン不一致、権限なし |
| 404 | ジョブなし、または閲覧権限なし |
| 409 | 状態遷移不正 |
| 422 | 入力不正 |
| 429 | 1ユーザー3件の同時実行制限超過 |
| 500 | サーバ内部エラー |
| 502 | LLMプロバイダ呼び出し失敗 |
| 504 | LLMまたは外部APIタイムアウト |

## ジョブレスポンス共通形

```json
{
  "job_id": "mrj_...",
  "status": "running",
  "target_month": "2026-04",
  "household_key": "demo",
  "current_stage": "call_llm",
  "completed_stages": ["fetch_sources", "bundle", "build_messages"],
  "prompt_version": "monthly-report-v1",
  "template_key": "pattern_b",
  "template_hash": "sha256:...",
  "model_report": "anthropic/claude-sonnet-4.6",
  "model_light": "openai/gpt-4.1-mini",
  "resolved_model_report": "anthropic/claude-sonnet-4.6",
  "source_bundle_hash": "sha256:...",
  "app_version": "git-sha-or-image-digest",
  "error_type": null,
  "error_message": null,
  "created_at": "2026-05-13T00:00:00+09:00",
  "updated_at": "2026-05-13T00:01:00+09:00"
}
```

## 未決事項

なし。`prompt_scope_notes` はレシピ由来または手入力で初期投入し、householdメタからの自動生成は後続とする。

## 実装追跡事項

- `/monthly-reports/*` のHTML page/action/fragment第一弾は本番ルータへ追加済み。ジョブ一覧・新規・作成・詳細・ソース確認/手動保存/Google取得・取得内容要約・生成開始・モック生成・OpenRouter生成・status/preview/validation/feedback、編集保存、再生成、承認、HTML export、HTML source、distribution package、rerun comparison、rerun diff、legacy full editor bridgeはHTMLを返す。
- 通常UIから `/api/monthly-reports/*` をDOM更新目的で直接使わない境界は文書化・focused test済み。JSON APIはworker/E2E/管理/将来連携用として維持する。
- JSONの `/api/monthly-reports/jobs/{job_id}/fetch-google-sources` はE2E/worker/管理/将来連携用。通常HTML UIは `POST /monthly-reports/jobs/{job_id}/fragments/google-sources` 経由でsources断片を差し替える。
- Cookie + CSRF第一弾はジョブ作成・生成開始・ソース保存・Google取得・フィードバック保存・編集保存・再生成・キャンセル・承認・HTML export・HTML source・distribution packageで実装済み。残りはserver-side session refresh/rotationとBearer token前提ヘルパーの棚卸し。
- POST系に冪等性キーまたはjob input hashを導入済み。job作成、生成開始、source保存、Google取得、artifact保存、validation保存、feedback保存、編集保存、再生成、承認、HTML export、HTML source、distribution packageは同一キー再送で重複作成しないことをfocused testで確認済み。
- 承認/export/html source/distributionなど入力フォームを含むpanelは定期pollingせず、`monthly-report-refresh` イベントで更新する。進捗statusは従来通りHTMX pollingで扱う。
- `running` のstatus fragmentは、ページを閉じても処理継続、自動更新、再読み込み後の状態復元を案内する。後段stageで長時間heartbeatがない場合は、後段stageを自動再claimしないworker運用に合わせてrunbook確認を促す。
- 2026-05-19に admin recovery の最小入口として `POST /api/monthly-reports/jobs/{job_id}/manual-recovery/fail` を追加した。stuck `running` job を `manual_recovery_required` で閉じる専用JSON routeで、通常ユーザーや `e2e` caller intent では使えない。

## 受け入れ条件

- MVP画面の全操作に対応するAPIまたはfragment APIがある。
- 同期生成APIに依存しない。
- エラー時にUIが適切なメッセージを出せる情報を返す。

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-13 | 初版作成 |
| 2026-05-14 | ソーススナップショット・生成成果物の保存/一覧APIを追加 |
| 2026-05-14 | 実装済みのstage進行/失敗/検証結果APIと再現性メタを反映 |
| 2026-05-14 | 月次レポートAPIの認証依存関係とローカルmock認証の扱いを反映 |
| 2026-05-14 | 静的POCレシピ合流のため、source_preset / prompt_scope_notes / ideal / artifact 関連のジョブ入力候補を追加 |
| 2026-05-14 | `prompt_scope_notes` を正式フィールド名として反映 |
| 2026-05-14 | `prompt_scope_notes` の初期投入方針をレシピ由来 + 手入力可能に決定 |
| 2026-05-14 | provider mock通電API `/jobs/{job_id}/run-mock` を追加 |
| 2026-05-14 | OpenRouter実provider通電API `/jobs/{job_id}/run-openrouter` を追加 |
| 2026-05-14 | LLM呼び出しログ取得API `/jobs/{job_id}/llm-calls` を追加 |
| 2026-05-14 | `multistudent_scope_exclusion` によるartifact保存前の `validation_failed` を反映 |
| 2026-05-14 | `required_headings` によるartifact保存前の `validation_failed` を反映 |
| 2026-05-14 | `forbidden_terms` によるartifact保存前の `validation_failed` を反映 |
| 2026-05-14 | Google Workspace REST APIからソースを取得する `/fetch-google-sources` を追加 |
| 2026-05-17 | 通常HTML UI用のsources fragment、手動ソース保存、Google Docs/Sheets取得HTML actionを追加 |
| 2026-05-17 | 通常HTML UIの `/run` actionにOpenRouter生成モードを追加 |
| 2026-05-17 | 編集保存、差分、承認、HTML export、HTML source、distribution、rerun comparison、rerun diff、比較候補、再生成ジョブリンク、legacy full editor bridge、running復帰案内のHTML fragment APIと冪等性/refresh方針を反映 |
| 2026-05-14 | 暗号化保存済みprovider refresh tokenからのGoogle access token解決経路を反映 |
| 2026-05-14 | Google provider refresh token保存API `/api/auth/google-oauth/credentials` を追加 |
| 2026-05-14 | Supabase session経由のGoogle provider refresh token保存ブリッジ `/api/auth/google-oauth/supabase-session` を追加 |
| 2026-05-14 | Supabase JWT secretによるBearer token検証とメールドメイン制限を反映 |
| 2026-05-15 | Supabase session保存ブリッジのprovider/email/scope検証とrefresh token秘匿を反映 |
| 2026-05-16 | 通常UIはHTMLページ/HTML断片、JSON APIはworker/E2E/管理/将来連携用とする境界、Cookie+CSRF、冪等性追跡を反映 |
| 2026-05-15 | 非mock環境のジョブ所有者決定と一般ユーザーのジョブアクセス制限を反映 |
| 2026-05-18 | JSON write APIのcaller intent、RLS/direct DB境界、通常ユーザー露出可否を表で固定 |
| 2026-05-19 | direct DB state mutation JSON routeに `X-EB-Caller-Intent` を導入し、`start` / `complete-stage` / `fail` / `cancel` / `run-*` / `rerun` を内部/管理/E2E 用として明示 |
| 2026-05-19 | stuck `running` job を `manual_recovery_required` で閉じる admin-only JSON route `/manual-recovery/fail` を追加 |
