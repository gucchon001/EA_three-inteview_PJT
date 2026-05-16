# API定義書

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツールのAPI定義
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- 関連文書: `functional-spec.md`, `screen-design.md`, `data-design.md`
- 最終更新: 2026-05-14

## 方針

- JSON APIは `/api/monthly-reports/*` に置く。
- HTML fragment APIは `/monthly-reports/*/fragments/*` に置く。
- LLM生成は同期 `generate` ではなく、ジョブ作成と状態取得に分ける。
- Supabase Authで認証済みのユーザーのみアクセス可能とする。
- FastAPI側はSupabase Authセッションを検証し、`tomonokai-corp.com` ドメイン制限を適用する。
- ローカル環境では `EB_AUTH_MODE=mock` のときだけ開発用モックユーザーを注入する。
- 月次レポートAPIは `get_current_user` 相当の依存関係を通す。非mock環境ではBearer tokenをSupabase JWT secretで検証し、`aud=authenticated` と `tomonokai-corp.com` ドメインを要求する。
- 非mock環境では、ジョブ作成時の `owner_user_id` はリクエストbodyではなく認証ユーザーIDから決める。ジョブ一覧・詳細・成果物・検証・LLM呼び出しログ・stage操作は、一般ユーザーには自分のジョブだけを返す。他ユーザーのジョブIDは404として扱う。admin roleは全ジョブ参照を許可する。
- DB主キーはUUIDとし、API・画面・ログではprefix付きIDを使う。
- MVPの進捗更新はHTMXポーリングに統一する。SSEは後続検討とする。
- Supabase AuthのOAuth開始・callback APIは認証基盤側の責務とし、本API定義には含めない。

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
      "range_name": "student!A1:Z200",
      "display_name": "学習計画表 student"
    }
  ]
}
```

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

| API | 用途 |
|---|---|
| `GET /monthly-reports/jobs/{job_id}/fragments/status` | 進捗表示 |
| `GET /monthly-reports/jobs/{job_id}/fragments/preview` | プレビュー差し替え |
| `GET /monthly-reports/jobs/{job_id}/fragments/validation` | 検証結果 |
| `POST /monthly-reports/jobs/{job_id}/fragments/feedback` | フィードバック保存後のUI |

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
| 2026-05-14 | 暗号化保存済みprovider refresh tokenからのGoogle access token解決経路を反映 |
| 2026-05-14 | Google provider refresh token保存API `/api/auth/google-oauth/credentials` を追加 |
| 2026-05-14 | Supabase session経由のGoogle provider refresh token保存ブリッジ `/api/auth/google-oauth/supabase-session` を追加 |
| 2026-05-14 | Supabase JWT secretによるBearer token検証とメールドメイン制限を反映 |
| 2026-05-15 | Supabase session保存ブリッジのprovider/email/scope検証とrefresh token秘匿を反映 |
| 2026-05-15 | 非mock環境のジョブ所有者決定と一般ユーザーのジョブアクセス制限を反映 |
