# レポート工房 production promotion checklist

## 位置づけ

- 正本/補助資料の区分: staging 検証完了後の production 昇格 checklist / runbook
- 起点: [staging-deploy-runbook.md](staging-deploy-runbook.md), [development-plan.md](development-plan.md), [verification-log.md](verification-log.md)
- 関連文書: [security-operations.md](security-operations.md), [pre-e2e-setup.md](pre-e2e-setup.md)
- 最終更新: 2026-05-19

この文書は、2026-05-19 時点で staging core pipeline が green になった状態から、同一 image を production へ昇格させるための最小 checklist をまとめる。production 初回昇格では、未検証の新規 commit を混ぜず、staging で通った image / env 契約 / smoke 手順をそのまま持ち上げることを前提にする。

## 決定事項

- production へ新規 build を持ち込まず、staging で live E2E 成功済みの image を昇格候補にする。
- 2026-05-19 時点の昇格候補 image は `asia-northeast1-docker.pkg.dev/gen-lang-client-0360012476/monthly-report-workshop/monthly-report-workshop:01c993a-templatefix-20260519`。
- staging の確認済み service revision は `monthly-report-workshop-staging-00004-9vt`、worker smoke 最新 execution は `monthly-report-worker-staging-95nc8`、API live E2E 成功 job は `mrj_b2695817af474330a2eed6b43cc3be00`。
- production の smoke / 外形監視は `/health` を正とし、`/healthz` は Cloud Run 予約 URL 挙動のため使わない。
- browser `/auth/google` の実同意は staging でも client-side blocker が残っているため、production promotion の exit criteria からは外し、別途 blocker として管理する。

## Promotion Prerequisites

promotion 開始前に、次が全て揃っていることを確認する。

1. staging で `/health` 200、`/auth/google` 200、未認証 `/monthly-reports/jobs` 401、worker smoke success、seeded real Google OAuth refresh token による API live E2E success が確認済み。
2. production 用 Secret / OAuth client / Supabase project は staging と完全に分離されている。
3. production service と worker は staging と同じ image digest を使う。
4. rollback 先の直前 production revision 名と worker job 設定を記録してから作業する。
5. production 反映中は DB migration の有無を明示し、必要なら先に maintenance window を切る。

## Environment Separation Checklist

production では staging 値の使い回しをしない。

| 項目 | production で守ること |
|---|---|
| Supabase project | staging と別 project / 別 DB / 別 JWT secret |
| Secret Manager | `mrf-prod-*` のような production 専用 secret 名へ分離 |
| Google OAuth client | staging client と別 client ID / secret |
| Redirect URL | production origin / callback のみ登録し、staging URL を混ぜない |
| OpenRouter API key | production 専用 key と利用上限 |
| Token encryption key | staging と別 key / version |
| Cloud Run service account | production 専用 SA を推奨。共用時も secret accessor 対象を production secret に限定 |

最低限の production secret / env 例:

- Secrets: `EB_MONTHLY_REPORT_DATABASE_URL`, `SUPABASE_JWT_SECRET`, `GOOGLE_OAUTH_CLIENT_SECRET`, `EB_GOOGLE_TOKEN_ENCRYPTION_KEY`, `OPENROUTER_API_KEY`
- Non-secret env: `EB_ENV=production`, `EB_ALLOWED_EMAIL_DOMAIN=tomonokai-corp.com`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `GOOGLE_OAUTH_CLIENT_ID`, `OPENROUTER_MODEL_REPORT`, `OPENROUTER_MODEL_LIGHT`, `EB_MONTHLY_REPORT_PROMPT_VERSION`, `EB_APP_VERSION`

## Redirect / Auth Separation Checklist

production OAuth 反映前に、次を別環境として確認する。

1. Supabase production `Site URL` が production service origin を向いている。
2. Supabase production `Additional Redirect URLs` に production `/auth/callback` だけを入れる。
3. Google OAuth production client の Authorized redirect URI は production Supabase callback だけを入れる。
4. staging / production で同じ OAuth client を共有しない。
5. browser `/auth/google` の実同意は client-side blocker が解消するまで production の最終 gate にしない。

補足:

- production では API live E2E と worker smoke を優先し、browser consent は blocker 解消後の追加確認とする。
- `/auth/google` 自体の到達確認は `200` または期待した bridge page 表示までを smoke に含める。

## Same-Image Deploy Discipline

production では service と worker を別 build しない。

1. `gcloud artifacts docker images describe` などで昇格対象 image digest を取得する。
2. production service deploy にその digest を指定する。
3. production worker deploy にも同じ digest を指定する。
4. deploy 後、service revision と worker job 定義が同じ digest を指すことを確認する。
5. deploy 作業中に template / static asset / prompt file を差し替えない。

2026-05-19 の template packaging 漏れ再発防止として、production では「staging で通った image を再利用する」を崩さない。

## Promotion Procedure

1. rollback 用に現行 production revision 名、service URL、worker job 設定、secret version を記録する。
2. DB migration が必要な release なら、production DB へ先に適用し、RLS / schema 差分の確認結果を記録する。
3. production secret の version を更新する。staging secret を参照しない。
4. staging で成功済みの image digest を production service に deploy する。
5. 同じ image digest を production worker job に deploy する。
6. production `/health` smoke を実行する。
7. production 未認証 `/monthly-reports/jobs` 401 と `/auth/google` 到達を確認する。
8. queued job がない状態で production worker smoke を 1 回実行し、正常終了を確認する。
9. seeded token または運用で許可された方法で production API live E2E を 1 件だけ実行する。
10. Cloud Logging に本文 / source 本文 / token / secret が出ていないことを spot check する。
11. promotion 完了後、service revision / worker execution / E2E job id を記録する。

## Production Smoke Checks

最小 smoke:

```bash
SERVICE_URL="https://<production-service-url>"

curl -fsS "${SERVICE_URL}/health"
curl -I "${SERVICE_URL}/monthly-reports/jobs"
curl -I "${SERVICE_URL}/auth/google"
gcloud run jobs execute monthly-report-worker-production --region asia-northeast1 --wait
```

合格条件:

- `/health` が 200
- 未認証 `/monthly-reports/jobs` が 401 または期待した未ログイン応答
- `/auth/google` が 200 または期待した bridge page
- worker smoke が `status=no_job` または期待した success classification で終了

追加 smoke:

- seeded credential を使う production API live E2E 1件
- approval / export までは本番初回昇格の必須 gate にせず、core pipeline 成功後の follow-up smoke として扱う

## Rollback Notes

rollback は「直前 revision へ戻す」と「worker も同じ世代へ戻す」をセットで行う。

1. `gcloud run services update-traffic` または前 revision 再deploy で service を直前 revision へ戻す。
2. worker job も直前の image digest へ戻す。
3. 今回追加した production secret version が原因なら、前 version を参照するよう戻す。
4. migration が後方互換でない場合は、app rollback だけでは足りないので DB rollback 可否を先に判定する。
5. rollback 後も `/health`、未認証 `/monthly-reports/jobs`、worker smoke を再実行する。

## Blockers / Remaining Risks

- browser `/auth/google` 実同意は client-side blocker が未解消で、production 前の browser-based final sign-off をまだ取れていない。
- production Supabase / OAuth / Secret の実体値は未作成または未確認の可能性があり、environment separation の準備が昇格開始条件になる。
- seeded real Google OAuth refresh token を production でどう扱うかは運用判断が要る。手順を誤ると本番ユーザー credential と混ざる。
- approval / export / distribution package までの production 実機確認は未実施。

## 受け入れ条件

- staging 成功状態から production へ持ち上げる最小手順が一読で分かる。
- env / secret / redirect URL の分離ルールが明記されている。
- same-image deploy、smoke、rollback、OAuth blocker が含まれている。

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-19 | staging green 後の production promotion checklist を追加 |
