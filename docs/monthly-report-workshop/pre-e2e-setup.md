# Pre-E2E Setup Guide

## 位置づけ

- 正本/補助資料の区分: 実Supabase Auth + Google OAuth + Google Workspace read flowのライブE2E前チェックリスト
- 起点: [security-operations.md](security-operations.md), [api-definition.md](api-definition.md), [development-plan.md](development-plan.md)
- 関連文書: [.env.example](../../.env.example), [data-design.md](data-design.md), [test-plan.md](test-plan.md)
- 最終更新: 2026-05-17（MVPは本番のみ、stagingは本番ポータル合流時に用意する方針へ修正）

このガイドは、ローカルmockではなく実Supabase Auth、Google OAuth provider token、Google Workspace読み取り、月次レポートAPIをつないで確認する直前に使う。実シークレット値はここにも、Git管理ファイルにも、フロントエンドにも置かない。

## 決定事項

- MVPは本番のみで確認する。staging / production の2環境分離は、本番ポータルへ合流するタイミングで用意する。
- Cloud Run本番リージョンは `asia-northeast1`（東京）を使う。
- Supabaseプロジェクトを新規作成する場合、プロジェクトリージョンはCloud Runやデータ所在方針と矛盾しないリージョンを選ぶ。既存プロジェクトを使う場合は、リージョン差分を運用リスクとして確認する。
- 認証はSupabase Auth Google provider。**API側検証は ES256/RS256 を本流とし、`<SUPABASE_URL>/auth/v1/.well-known/jwks.json` から取得した公開鍵で検証**する（D-059）。HS256 + `SUPABASE_JWT_SECRET` は `alg` ヘッダが HS256 のときのフォールバックとテスト互換用に残す。
- ドメイン制限は Supabase 側ではなく **FastAPI 側の JWT email チェック（`EB_ALLOWED_EMAIL_DOMAIN`）**で担保する。Supabase Auth の signup は `enable_signup = true` で通し、許可しない email は FastAPI 層で 403（D-060）。
- Google Workspace APIは、ブラウザやリクエストbodyではなく、サーバ側で暗号化保存したGoogle provider refresh tokenからaccess tokenを取得して読む。

## 詳細

### 1. Supabase Auth

Supabase側で以下を設定する。

| 設定グループ | 設定 |
|---|---|
| Authentication provider | Google providerを有効化する |
| Google client | Google Cloudで作成したOAuth client ID / client secretを登録する |
| Site URL | `<APP_BASE_URL>`。例: `https://<cloud-run-service-url>` |
| Redirect URLs | `<APP_BASE_URL>/auth/callback`, `http://localhost:<PORT>/auth/callback` などE2Eで使うURLだけ |
| JWT | Supabase projectのJWT secretをバックエンド実行環境へ渡す |
| Domain policy | API側で `tomonokai-corp.com` を許可ドメインとして検証する |

E2E前に、対象ユーザーが `tomonokai-corp.com` のGoogleアカウントでログインできること、Supabase sessionのaccess tokenをFastAPIへBearer tokenとして渡せることを確認する。

本番ポータル合流時にstaging / productionを分ける場合は、それぞれのCloud Run URLまたは独自ドメインをSupabase Auth Redirect URLsへ登録し、callback URLを環境間で混ぜない。

#### ローカル Supabase で同等にする場合（`supabase/config.toml`）

ローカル開発でライブE2Eを通すときは、`supabase/config.toml` に下記を入れて `supabase stop && supabase start` で再起動する。`client_id` / `secret` は `.env` 経由で参照させる。

```toml
[auth]
enabled = true
site_url = "http://127.0.0.1:8000"
additional_redirect_urls = [
  "http://127.0.0.1:8000",
  "http://127.0.0.1:8000/auth/callback",
]
jwt_expiry = 3600
enable_signup = true  # D-060: 初回 Google ログインを signup 扱いで通す

[auth.external.google]
enabled = true
client_id = "env(GOOGLE_OAUTH_CLIENT_ID)"
secret = "env(GOOGLE_OAUTH_CLIENT_SECRET)"
redirect_uri = "http://127.0.0.1:56321/auth/v1/callback"
skip_nonce_check = true
```

確認コマンド:

- `curl -s http://127.0.0.1:56321/auth/v1/settings | jq '.disable_signup, .external.google'` → `false`, `true` を返す
- `curl -s http://127.0.0.1:56321/auth/v1/.well-known/jwks.json | jq '.keys[0].alg'` → `"ES256"` を返す（FastAPI 側 JWKS 検証経路の前提）

### 2. Google Cloud OAuth

Google Cloud側で以下を設定する。

| 設定グループ | 設定 |
|---|---|
| OAuth consent | Internal運用が可能ならWorkspace内部アプリとして設定する。External/testingの場合はテストユーザーを明示する |
| Authorized domains | Supabase Auth / Cloud Run / 独自ドメインの利用形態に合わせて登録する |
| OAuth client type | Web application |
| Authorized redirect URI | `https://<SUPABASE_PROJECT_REF>.supabase.co/auth/v1/callback` |
| Enabled APIs | Google Docs API, Google Sheets API, Google Drive API |
| Required scopes | `openid`, `email`, `profile`, `https://www.googleapis.com/auth/documents.readonly`, `https://www.googleapis.com/auth/spreadsheets.readonly`, `https://www.googleapis.com/auth/drive.readonly` |

Google provider refresh tokenを得るため、OAuth開始時は `access_type=offline` と `prompt=consent` を使う。すでに同意済みのユーザーではrefresh tokenが再発行されないことがあるため、ライブE2Eでは同意状態のリセットまたは新規テストユーザーも確認対象にする。

### 3. Backend Environment

バックエンド実行環境には以下を設定する。値はSecret Manager、Cloud Run Secret参照、または安全なローカル環境変数で渡し、Git管理ファイルに実値を書かない。

| 変数 | 用途 | ライブE2E |
|---|---|---|
| `EB_AUTH_MODE` | 認証モード。実E2Eでは `supabase` または未指定の既定値 | 必須 |
| `SUPABASE_JWT_SECRET` | Supabase JWT署名検証 | 必須 |
| `SUPABASE_JWT_AUDIENCE` | JWT audience。既定は `authenticated` | 原則設定 |
| `EB_ALLOWED_EMAIL_DOMAIN` | 許可メールドメイン。既定は `tomonokai-corp.com` | 原則設定 |
| `EB_MONTHLY_REPORT_DATABASE_URL` | 月次レポート用Postgres接続先 | 必須 |
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth token refresh | 必須 |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth token refresh | 必須 |
| `EB_GOOGLE_TOKEN_ENCRYPTION_KEY` | Google provider refresh token暗号化キー。Fernet key | 必須 |
| `EB_GOOGLE_TOKEN_ENCRYPTION_KEY_VERSION` | 暗号鍵バージョン | 必須 |
| `OPENROUTER_API_KEY` | LLM生成まで通す場合のOpenRouter APIキー | 生成E2Eでは必須 |
| `OPENROUTER_MODEL_REPORT` | 本文生成モデル | 生成E2Eでは必須 |
| `OPENROUTER_MODEL_LIGHT` | 軽量モデル | 推奨 |
| `OPENROUTER_TIMEOUT` / `OPENROUTER_MAX_TOKENS` | 呼び出し制御 | 任意 |
| `SUPABASE_URL` | `/auth/google` のE2Eブリッジで使うSupabase project URL。公開可能値 | ライブE2Eでは必須 |
| `SUPABASE_ANON_KEY` | `/auth/google` のE2Eブリッジで使うSupabase anon key。公開可能値 | ライブE2Eでは必須 |
| `EB_GOOGLE_OAUTH_SCOPES` | Supabase Google providerへ要求するGoogle OAuth scope | 原則設定 |

`EB_GOOGLE_WORKSPACE_ACCESS_TOKEN` はローカル疎通確認用の暫定経路であり、実Supabase Auth + Google OAuthのライブE2Eでは使わない。

### 4. Database / RLS

Supabase Postgresまたは同等のPostgres接続先で、月次レポート用migrationとRLS migrationを適用しておく。

- `monthly_report_jobs` など主要テーブルのRLSが有効であること。
- `google_oauth_credentials` はユーザー自身のcredentialだけを扱うこと。
- FastAPIのDB接続情報はサーバ側だけに置くこと。
- Supabase `service_role` key、JWT secret、DB URLをフロントエンドへ置かないこと。Supabase URL / anon keyをフロントで使う構成にする場合も、RLSとAPI側認可を前提に扱う。

### 5. E2E Flow

ライブE2Eでは、最低限以下の順で確認する。

1. GoogleログインでSupabase sessionを取得する。
2. Supabase session由来のprovider refresh tokenを `/api/auth/google-oauth/supabase-session` 経由で暗号化保存する。
3. 月次レポートジョブを作成する。
4. `/api/monthly-reports/jobs/{job_id}/fetch-google-sources` でDocs / Sheetsを読み、source snapshotを保存する。
5. OpenRouter設定がある場合だけ、生成APIまたはworker経路でdraft artifactまで通す。

### 5.1 E2Eブリッジ画面

バックエンドに `SUPABASE_URL` と `SUPABASE_ANON_KEY` を設定すると、`/auth/google` からSupabase Google providerログインを開始できる。callback先は `/auth/callback` で、Supabase sessionに含まれる `provider_refresh_token` を `/api/auth/google-oauth/supabase-session` へ送って暗号化保存する。

手動作業が必要な点:

- Supabase AuthのRedirect URLsに `<APP_BASE_URL>/auth/callback` を追加する。
- Google OAuth clientのAuthorized redirect URIに `https://<SUPABASE_PROJECT_REF>.supabase.co/auth/v1/callback` を追加する。
- 初回または再同意時に refresh token が返るよう、Google同意状態をリセットするか、未同意のテストユーザーを使う。
- E2E対象のDocs / Sheetsを、そのテストユーザーが閲覧できる状態にする。

期待結果:

- `/auth/callback` 画面に `Google refresh token stored` と `credential_id=...` が表示される。
- 画面・レスポンス・ログに `provider_refresh_token` の実値は表示されない。
- 続けて同じBearer tokenで月次レポートジョブを作成し、`/fetch-google-sources` が保存済みrefresh tokenからaccess tokenを解決できる。

### 5.2 レポート工房ライブE2E画面

`/auth/callback` でGoogle provider refresh token保存まで通った後、同じブラウザで `/monthly-report-workshop/e2e` を開く。この画面はSupabase sessionのBearer tokenを使い、以下を順番に実行する。

1. `POST /api/monthly-reports/jobs` でジョブを作成する。
2. `POST /api/monthly-reports/jobs/{job_id}/fetch-google-sources` でDocs / Sheetsをsource snapshotとして保存する。
3. `POST /api/monthly-reports/jobs/{job_id}/run-openrouter` でdraft生成、validation、artifact保存まで通す。
4. `GET /sources`, `/artifacts`, `/validations`, `/llm-calls` で結果を確認する。

この画面はライブE2E用の開発導線であり、実シークレットやGoogle provider tokenの実値は表示しない。

## Not Needed Yet

- ブラウザにGoogle access token / refresh tokenを保存する実装。
- フロントエンドからGoogle Workspace APIを直接読む実装。
- サービスアカウント鍵によるGoogle Workspace読み取り。
- Cloud Tasks、Pub/Sub、Cloud Run Jobsなどの非同期基盤。
- Supabase Storageへの成果物分離。
- `EB_GOOGLE_WORKSPACE_ACCESS_TOKEN` を使った本番運用。

## Must Not Be Put In Frontend

- `OPENROUTER_API_KEY`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `EB_GOOGLE_TOKEN_ENCRYPTION_KEY`
- `SUPABASE_JWT_SECRET`
- `EB_MONTHLY_REPORT_DATABASE_URL`
- Supabase `service_role` key
- Google provider refresh token / access token
- サービスアカウント鍵

## 未決事項

- Cloud Runの正式URLとSupabase Auth redirect URLの本番値。
- Supabaseプロジェクトを新規作成する場合の正式リージョン。
- ライブE2Eで使うテストユーザー、テストDocs / Sheets、保持期間到来前の削除手順。

## 受け入れ条件

- 実シークレット値を含まず、設定名と設定場所だけが分かる。
- Supabase Auth、Google OAuth consent/client/scopes、Google Workspace API、backend env、DB/RLSの準備項目が揃っている。
- フロントエンドへ置いてはいけない値が明示されている。

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-15 | 初版作成 |
| 2026-05-16 | `/monthly-report-workshop/e2e` のライブE2E画面を追加し、ジョブ作成からartifact確認までの手順を反映 |
| 2026-05-16 | ローカル Supabase 実機通電を反映。`supabase/config.toml` の `[auth.external.google]` + `enable_signup = true` + `additional_redirect_urls` 追記、JWKS（ES256）経由の JWT 検証への切替、ドメイン制限の API 側担保（D-059/D-060） |
| 2026-05-17 | MVPは本番のみへ戻し、staging / production の環境分離は本番ポータル合流タイミングで用意する方針へ修正 |
