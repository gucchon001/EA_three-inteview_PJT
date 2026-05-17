# データ設計書

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツールの永続化設計
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- 関連文書: `requirements.md`, `api-definition.md`, `security-operations.md`
- 最終更新: 2026-05-15

## 方針

- ジョブ、ソーススナップショット、生成成果物、検証結果、LLMメタ、人手フィードバックを保存する。
- MVPからSupabase Postgresを永続化基盤として採用する。
- MVPでは本文・ソース本文・生成物をSupabase Postgresに保存し、Cloud Loggingには流さない。
- サイズが重くなった場合は、ソース本文・生成物をSupabase Storageへ逃がし、Postgresにはメタデータとstorage pathを保持する。
- Supabase Storageへ分離する場合は、bucket policy、object prefix、signed URLの有効期限、配布用エクスポートの閲覧期限、保持期間到来時のStorage削除バッチをPostgresメタデータと同時に設計する。
- 将来の指導管理ポータル統合時に、同じSupabaseプロジェクトまたは同じPostgres設計へ寄せやすいテーブル境界にする。
- FastAPI direct DB接続のMVPではAPI側の認可を主境界とするが、将来のSupabase/PostgREST/ポータル統合に備えてRLSを有効化し、一般ユーザーは自分のジョブ配下だけを読めるpolicyをmigrationに含める。

## テーブル候補

### `monthly_report_jobs`

| カラム | 型案 | 内容 |
|---|---|---|
| `id` | uuid | DB主キー |
| `public_id` | text | API/画面/ログ用prefix付きID。例: `mrj_...` |
| `created_by` | text | ユーザーID |
| `target_month` | text | `YYYY-MM` |
| `household_key` | text | 対象世帯識別子 |
| `status` | text | `queued` など |
| `current_stage` | text | 現在stage |
| `error_type` | text | 失敗分類。ジョブ失敗時は監査ログだけでなくジョブ本体へ明示保存する |
| `error_message` | text | 失敗概要。PIIや生ソースを含めず、UI表示・調査に使える範囲に留める |
| `prompt_version` | text | 使用プロンプト版 |
| `template_key` | text | テンプレート種別 |
| `template_hash` | text | 読み込んだテンプレートhash |
| `model_report` | text | 本文生成モデル |
| `model_light` | text | 軽量モデル |
| `resolved_model_report` | text | Auto Router等で実際に使われた本文生成モデル |
| `source_bundle_hash` | text | バンドルhash |
| `app_version` | text | Git SHA、release tag、image digest等 |
| `prompt_scope_notes` | text | レシピ由来または手入力の対象限定メモ。複数生徒MTGで対象生徒・教科を限定する |
| `created_at` | timestamptz | 作成日時 |
| `updated_at` | timestamptz | 更新日時 |

### `monthly_report_sources`

| カラム | 型案 | 内容 |
|---|---|---|
| `id` | uuid/text | ソースID |
| `public_id` | text | API/画面/ログ用prefix付きID。例: `mrs_...` |
| `job_id` | uuid | 親ジョブ |
| `source_type` | text | `sheet`, `doc`, `drive_file`, `upload` |
| `external_id` | text | spreadsheet_id/document_id |
| `url` | text | 参照URL |
| `display_name` | text | 表示名 |
| `snapshot_text` | text | プレーン化した本文 |
| `snapshot_json` | jsonb | API取得結果 |
| `storage_path` | text | Supabase Storageへ分離した場合のパス |
| `content_hash` | text | hash |
| `size_bytes` | int | サイズ |
| `truncated` | boolean | 切り詰め有無 |
| `fetch_status` | text | `succeeded`, `failed` |
| `error_type` | text | 失敗分類 |
| `fetched_at` | timestamptz | 取得日時 |

### `monthly_report_artifacts`

| カラム | 型案 | 内容 |
|---|---|---|
| `id` | uuid/text | 成果物ID |
| `public_id` | text | API/画面/ログ用prefix付きID。例: `mra_...` |
| `job_id` | uuid | 親ジョブ |
| `artifact_type` | text | `draft_markdown`, `draft_html`, `final_markdown`, `final_html`, `exported_html` |
| `content` | text | 本文 |
| `content_hash` | text | hash |
| `storage_path` | text | Supabase Storageへ分離した場合のパス |
| `created_at` | timestamptz | 作成日時 |

### `monthly_report_validations`

| カラム | 型案 | 内容 |
|---|---|---|
| `id` | uuid/text | 検証ID |
| `public_id` | text | API/画面/ログ用prefix付きID。例: `mrv_...` |
| `job_id` | uuid | 親ジョブ |
| `artifact_id` | uuid | 対象成果物 |
| `rule_id` | text | ルールID |
| `severity` | text | `error`, `warning`, `info` |
| `message` | text | 表示メッセージ |
| `path` | text | 対象箇所 |
| `created_at` | timestamptz | 作成日時 |

### `monthly_report_feedback`

| カラム | 型案 | 内容 |
|---|---|---|
| `id` | uuid/text | フィードバックID |
| `public_id` | text | API/画面/ログ用prefix付きID |
| `job_id` | uuid | 親ジョブ |
| `created_by` | text | 入力者 |
| `category` | text | 問題カテゴリ |
| `comment` | text | 自由記述 |
| `final_artifact_id` | uuid/text | 最終編集後成果物 |
| `created_at` | timestamptz | 作成日時 |

### `llm_call_logs`

実装済み。`run_monthly_report_job` がprovider成功/失敗時に自動記録し、本文・プロンプト全文は保存しない。

| カラム | 型案 | 内容 |
|---|---|---|
| `id` | uuid/text | 呼び出しID |
| `public_id` | text | API/画面/ログ用prefix付きID。例: `llm_...` |
| `job_id` | uuid | 親ジョブ |
| `prompt_kind` | text | `report`, `light`, `repair` |
| `provider` | text | `openrouter` |
| `requested_model` | text | リクエスト時に指定したモデルID。例: `openrouter/auto` |
| `resolved_model` | text | レスポンス上の実使用モデルID |
| `prompt_version` | text | prompt版 |
| `request_hash` | text | prompt本文のhash |
| `response_hash` | text | レスポンスhash |
| `latency_ms` | int | 所要時間 |
| `input_tokens` | int | 取得可能な場合 |
| `output_tokens` | int | 取得可能な場合 |
| `finish_reason` | text | 終了理由 |
| `error_type` | text | 失敗分類 |
| `created_at` | timestamptz | 作成日時 |

### `audit_logs`

| カラム | 型案 | 内容 |
|---|---|---|
| `id` | uuid/text | 監査ログID |
| `actor_id` | text | 実行者 |
| `action` | text | 操作 |
| `target_type` | text | 対象種別 |
| `target_id` | text | 対象ID |
| `metadata` | jsonb | PIIを含まない補足 |
| `created_at` | timestamptz | 作成日時 |

### `google_oauth_credentials`

Supabase Authのユーザーに紐づくGoogle API読取用credentialを保存する。

| カラム | 型案 | 内容 |
|---|---|---|
| `user_id` | uuid | Supabase Auth user id |
| `provider` | text | `google` |
| `encrypted_provider_refresh_token` | text | 暗号化したGoogle provider refresh token |
| `encryption_key_version` | text | 暗号鍵のバージョン |
| `scope` | text | 付与済みスコープ |
| `expires_at` | timestamptz | provider access tokenの期限。保存する場合のみ |
| `revoked_at` | timestamptz | 連携解除日時 |
| `created_at` | timestamptz | 作成日時 |
| `updated_at` | timestamptz | 更新日時 |

## RLS方針

`202605150001_monthly_report_rls_policies.sql` で主要テーブルのRLSを有効化する。MVPのFastAPIはDB接続情報でサーバ側から操作するため、アプリAPI側の所有者チェックを主境界にする。一方、将来Supabase Authの `authenticated` roleでPostgRESTやポータルから読む場合に備え、DB側にも最小の所有者policyを置く。

| テーブル | 方針 |
|---|---|
| `monthly_report_jobs` | `created_by = auth.uid()::text` の行だけselect/insert/update |
| `monthly_report_sources` | 親jobの `created_by = auth.uid()::text` の場合だけselect/insert |
| `monthly_report_artifacts` | 親jobの `created_by = auth.uid()::text` の場合だけselect/insert |
| `monthly_report_validations` | 親jobの `created_by = auth.uid()::text` の場合だけselect/insert |
| `monthly_report_feedback` | 親jobの所有者だけselect、insert時は `created_by = auth.uid()::text` も要求 |
| `llm_call_logs` | 親jobの所有者だけselect。本文・プロンプト全文は保存しない |
| `google_oauth_credentials` | `user_id = auth.uid()` のcredentialだけall |
| `audit_logs` | client accessなし。監査ログはサーバ側のみ |

## 保存対象

| 種類 | 保存 | 理由 |
|---|---|---|
| 入力メタ | 必須 | 再現・検索 |
| ソーススナップショット | 必須 | 同一入力再実行 |
| prompt_version | 必須 | チューニング比較 |
| template hash | 必須 | 規約変更影響の追跡 |
| モデルID | 必須 | 品質・コスト比較 |
| 生成Markdown | 必須 | 品質確認 |
| 検証結果 | 必須 | 回帰検証 |
| 最終編集後Markdown | 強く推奨 | 改善学習 |
| 生ログ | 保存しない | PII保護 |

## 保存先

| データ | MVP保存先 | 肥大化時 |
|---|---|---|
| ソース本文 | Supabase Postgres | Supabase Storageへ移動し、Postgresにはpathとhash |
| ソースJSON | Supabase Postgres `jsonb` | Supabase Storageへ移動し、Postgresにはpathとhash |
| 生成Markdown | Supabase Postgres | Supabase Storageへ移動し、Postgresにはpathとhash |
| 最終編集Markdown | Supabase Postgres | Supabase Storageへ移動し、Postgresにはpathとhash |
| HTMLエクスポート | Supabase Postgresまたは生成時作成 | 配布用はSupabase Storage候補 |

## 保持期間

| データ | 保持期間 | 備考 |
|---|---:|---|
| ジョブメタ | 3年 | 対象月、対象世帯、状態、版情報、作成者 |
| 生成Markdown | 3年 | 成果物として保存 |
| 最終編集Markdown | 3年 | 人手修正後の比較・改善に使用 |
| 生成HTML / 最終編集HTML | 3年 | 差分表示・送付エクスポートの元データ |
| ソーススナップショット | 1年 | 再生成・品質改善に必要。ただしPIIリスクが高いため成果物より短くする |
| LLMメタ | 3年 | model、latency、token等。本文は含めない |
| 検証結果 | 3年 | 品質傾向分析 |
| フィードバック | 3年 | チューニング材料 |
| Cloud Logging構造化ログ | 6か月 | 本文・生ソースは含めない |
| OAuthトークン | 利用中のみ | 失効、退職、連携解除時に削除 |

保持期間到来時は物理削除を基本とする。品質集計やモデル比較に必要なメタデータのみ、個人・世帯・ソースを特定できない形に匿名化して残せる。

保持期間削除は運用ジョブとして実装する。削除前の対象件数ドライラン、削除後の件数確認、監査ログ記録を必須にし、OAuthトークンは連携解除・退職・管理者削除時にも削除する。

## 未決事項

なし。

## 受け入れ条件

- 同一入力から再生成できる保存項目が揃っている。
- LLMチューニングの因果を後から説明できる。
- PIIをCloud Loggingへ出さずに調査できるメタ情報がある。

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-13 | 初版作成 |
| 2026-05-14 | ジョブ失敗詳細を `monthly_report_jobs.error_type` / `error_message` に明示保存する方針を反映 |
| 2026-05-14 | `monthly_report_jobs.prompt_scope_notes` を正式ジョブメタとして追加 |
| 2026-05-14 | `llm_call_logs` の実装状況を反映。本文・プロンプト全文ではなくhash/メタのみ保存 |
| 2026-05-15 | RLS有効化と所有者ベースpolicyのmigration方針を反映 |
