# 開発計画書

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツールの開発計画
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- 関連文書: `requirements.md`, `functional-spec.md`, `test-plan.md`, `decision-log.md`, `AUTOMATION_NORTH_STAR.md`
- 最終更新: 2026-05-19

## 現在位置

レポート工房は、静的POCの知見をFastAPI + Jinja2 + HTMXの通常UIへ寄せる段階に入っている。開発計画本文は「現在状態、次優先、フェーズ、未完了タスク」を読むための正本とし、詳細な日次ログは [development-history.md](development-history.md)、検証コマンド履歴は [verification-log.md](verification-log.md) に分離する。

現在の要点:

- 今回プロジェクトの完了条件は **レポート工房MVPがstaging環境で動くこと** とする。指導管理ポータル統合、およびproduction昇格は今回の完了条件ではなく後続フェーズに分ける。
- MVPでは staging を必須環境として用意する。migration、RLS、Google OAuth、OpenRouter、HTML UI smoke、Cloud Run Jobs worker smoke、ライブE2Eはstagingで確認する。production環境はstaging完了後の昇格先として設計対象に残すが、今回プロジェクトの完了判定には含めない。
- Phase 0は完了。プロンプト断片、`prompt_version`、静的レシピ連携、ジョブ表現の基礎は固定済み。
- Phase 1は骨格実装済み。Supabase Auth + Google OAuth + Google Docs/Sheets取得 + OpenRouter生成 + artifact/validation/llm_call_logs保存のライブE2E成功サンプルがある。2026-05-18には実Google Docs 1件 + Sheets 2件 + 実OpenRouterで `status=succeeded` のAPIライブE2Eを再確認済み。
- Phase 2は進行中。冪等性、worker lease/retry、RLS read store、PII/logging safety、保持削除、operational guardrailを段階的に固定している。
- Phase 3は進行中。編集後Markdown保存、再生成、承認、HTML export、distribution package、既存全文エディタ連携、自己完結Playwright smoke、起動中ローカルUI smoke、実Google/source summary smokeまで第一弾が通っている。
- Phase 4は今回プロジェクトのスコープ外。指導管理ポータルへ合流する時点では、MVPで用意したstaging成果をポータル基盤へ接続し、production昇格手順・権限・監視を統合する。

直近の詳細な実装メモと2026-05-17の細かい達成ログは [development-history.md#詳細な現在位置ログ移動前の現在位置](development-history.md#詳細な現在位置ログ移動前の現在位置) を参照する。

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
- ✅ 達成: ライブE2Eを実Google Docs/Sheets + 実OpenRouterで成功（緑）させ、決定的バリデーションを通過するジョブを保存。本データでのチューニング比較土台を作成。2026-05-18の成功サンプルは job `mrj_d3e6e1e884ba4cb4b44c2c9d2044250b`
- 優先: worker常駐実行接続、lease/stuck再claim/retry/冪等性、3件制限の実環境再現、LLM失敗時の再試行/再生成導線をE2Eで閉じる
- 優先: Storage移行policy、保持期間削除ジョブ、監視・費用上限アラート、プロンプトインジェクション検証、人間承認ゲートを設計・テストへ入れる
- 仕上げ: 編集後Markdown保存、再生成API/UI、モデル版比較、HTMLエクスポート/保存/送付の最小導線、Playwright最小シナリオで体験を通す

### 今後の開発計画（2026-05-19更新）

直近の開発は、ライブE2Eで確認済みの「OAuth取得・Google source保存・OpenRouter生成・artifact/validation/llm_call_logs保存」を土台に、通常UIと運用境界を固める。新しいモデル/語彙チューニングは、サンプルを増やしてからP2-11でまとめて扱う。

| 順位 | タスク | 理由 | 完了条件 |
|---|---|---|---|
| 1 | P1-11/P3-14 UI/UX整理 継続 | 現在の詳細画面はMVP検証ワークベンチで、通常ユーザーにはまだ複雑 | 一覧/新規作成/詳細をDaisyUIで統一し、データソース登録→取得内容確認→生成→編集/承認の導線が手動UIレビューで迷わない。2026-05-18にURL投入→Google取得→OpenRouter生成→プレビュー/検証OOB反映の通常UI縦切りを追加済み |
| 2 | P3-01/P3-02 編集保存・再生成UI 継続 | MVP体験として生成後の推敲、保存、再生成比較が必要 | 保存後の次アクション導線、実Google取得済みジョブ同士の比較、再生成比較の見た目調整が通る |
| 3 | P1-16 RLS client化 継続 | 通常ユーザー操作をRLS主境界へ寄せ切る | source / artifact / feedback / validation / final Markdown までは user-JWT write化済み。残りの direct DB / direct store 用途が worker/admin/migration/retention/idempotency/audit/telemetry に固定され、通常ユーザー経路に generic direct write が残らない |
| 4 | P2-10 worker本番化 継続 | Cloud Run運用でstuck jobを残さない | Cloud Run Jobsのcommand/env例、期待JSON summary、manual recovery非0終了、HTTP smokeとの役割分担、admin-only `manual-recovery/fail`、monitoring helper script は固定済み。残りは Cloud Monitoring alert policy の実反映、通知先設定、必要なら管理操作入口の追加 |
| 5 | P2-14 / P2-12 運用 | MVP本番で費用・保持・削除を人手だけにしない | monitoring helper script、ログベースmetric、保持削除 entry 契約は揃った。残りは alert policy apply、日次token/cost集計、保持削除の実DB dry-run/delete確認、OAuth credential削除の管理操作入口 |
| 6 | browser `/auth/google` 追加確認 | staging core gate は閉じたが、ブラウザ実同意だけ client-side blocker で残っている | clean profile または blocker 解消後に `/auth/google -> /auth/callback` を再確認し、client-side issue と app issue を完全に切り分けて検証ログへ残す |
| 7 | production昇格準備 | staging成功状態を同一imageでproductionへ持ち上げられるようにする | [production-promotion-checklist.md](production-promotion-checklist.md) を正本に、same-image deploy、secret/OAuth分離、smoke、rollback を固定し、運用者が実行できる状態にする |

並行で進めやすいタスク:

- P2-11: `Gemini メモ` / `Google Meetメモ` 系を含む入力由来メタ語彙のチューニング。ただし、成功サンプルを複数蓄積してから forbidden / safe replacement / warning に分類する。
- P2-13: GitHub Actions第二弾として、secret不要のmigration/static schema/RLS guardrail workflowを追加済み。Cloud Run serviceのHTTP smokeはmanual dispatchのみで、実Secretがある環境で実行する。2026-05-19にstaging service smoke（`/health` 200、`/monthly-reports/jobs` 401、`/auth/google` 200）とCloud Run Jobs worker smokeを手動確認済み。`/healthz` はCloud Run予約URL挙動によりGoogle Frontend HTML 404になるため、staging/prod smokeでは使わない。
- Phase 4: 指導管理ポータル構築後にレポート工房を組み込む。これは今回プロジェクトの完了条件ではなく、staging MVP完了後の後続統合枠とする。指導枠ごとのデータソース一元管理、学習計画表、BigQuery指導報告書、FileMaker/基幹情報との接続は指導ポータル側の正本に従う。
- P2-14: MVP初期の監視runbookに加え、ログベースmetric名・label・filter、alert threshold、日次token/cost summary contract、budget guardrail停止手順を固定済み。2026-05-19のstaging worker smoke成功を基準サンプルに、HTTP smokeはservice疎通、worker smokeはJSON summaryと終了コード、manual recovery/stuck jobはCloud Monitoring alertからrunbookへ遷移する責務分担を明文化した。さらに `scripts/staging/monthly_report_staging_monitoring.ps1` を追加し、`monthly_report_worker_failed_count` metric と `monthly-report-staging-worker-manual-recovery` / `monthly-report-staging-worker-failed-spike` / `monthly-report-staging-worker-fetch-sources-stale` の policy JSON 生成と apply 入口まで揃えた。残りはCloud Monitoring alert policy実反映、日次集計job/SQL、quota dashboard、新規OpenRouter実行停止feature flagまたは管理操作入口。
- P3-10: `tests/test_monthly_report_playwright_smoke.py` を入口にする。自己完結smokeはsource保存からdistribution/rerun comparison/rerun diffまで通過済み。ライブGoogle取得/source summary smokeとAPIライブE2Eもローカルで通過済み。2026-05-19にstagingのservice/job smokeに加え、seeded real Google OAuth refresh tokenを使うstaging API live E2Eも成功した。通常CIではskipを既定にし、残るブラウザ `/auth/google` 実同意確認は client-side blocker が外れた時点で追加確認する。
- Staging deploy: [staging-deploy-runbook.md](staging-deploy-runbook.md) を入口にする。Project ID は `gen-lang-client-0360012476`、region は `asia-northeast1`。2026-05-19時点で image `asia-northeast1-docker.pkg.dev/gen-lang-client-0360012476/monthly-report-workshop/monthly-report-workshop:01c993a-templatefix-20260519` をbuild/pushし、service revision `monthly-report-workshop-staging-00004-9vt` とworker jobへdeploy済み。service smokeは `/health` 200、未認証 `/monthly-reports/jobs` 401、`/auth/google` 200、worker smoke execution `monthly-report-worker-staging-fpfks` 成功。さらに staging API live E2E job `mrj_b2695817af474330a2eed6b43cc3be00` が `status=succeeded`、Google source 3件、`draft_markdown` artifact 1件、validation 2件、llm_call 1件で完了した。`/healthz` はCloud RunではGoogle Frontend HTML 404になるため、ローカル互換endpointとしてのみ扱う。

### 開発期間の見通し

現時点では、ローカルMVPの中核パイプラインは通っている。残りは「通常ユーザーが迷わないUI/UX」「RLS write化と運用境界」「staging環境での実証」の3束に分かれる。下記は1人の実装者が継続して進める前提の目安で、レビュー・手動確認・外部環境作成待ちを含む。

| 到達点 | 目安 | 含むもの | 主な外部依存 |
|---|---:|---|---|
| ローカルMVPを手動UIレビューしやすい状態 | 2〜4開発日 | P1-11/P3-14の画面整理、P3-01/P3-02の保存後導線、再生成比較の見た目、P3-12承認導線の整理 | なし。ローカルDBと既存E2Eデータで進行可能 |
| staging投入前のコード準備 | 完了 | P1-16の次write slice、P2-09のatomic化補強、P2-12/P2-14の運用入口整理は継続。Cloud Run service/jobのbuild・deploy・基本smoke、template packaging fix、monitoring helper script 追加まで完了 | なし |
| stagingでのMVP実証 | core live E2E完了 | migration適用、Cloud Run service smoke、Cloud Run Jobs worker smoke、Google OAuth入口、HTML UI未認証境界、seeded real Google OAuth refresh token による staging API live E2E は確認済み | ブラウザ `/auth/google` 実同意確認と Cloud Monitoring policy 実反映 |
| レポート工房MVP完了 | ほぼ到達 | stagingでHTTP smoke、worker smoke、RLS、OpenRouter、HTML UI smoke、seeded real Google OAuth refresh token を使うライブE2E、最小監視/runbookの script 入口までは記録済み。残りは Cloud Monitoring policy の実反映と通知着弾確認、通常UIの仕上げ、browser `/auth/google` 実同意確認を追加項目として扱う | Cloud Monitoring 実反映、通常UI仕上げ、ブラウザ OAuth 追加確認 |
| production昇格 | 後続 2〜4開発日 | production promotion checklist、Secret/OAuth分離、最小監視、rollback/runbook、production smoke | 今回プロジェクトの完了条件外。production Cloud Run/Supabase/Secret、運用者承認 |
| 指導管理ポータル統合 | 後続別枠 2〜4週間以上 | Phase 4。ポータル側の認証/指導枠/データソース管理/履歴統合へ組み込む | 今回プロジェクトの完了条件外。ポータル本体の要件・DB・権限設計 |

最短で「MVPとして試せる」状態を増やすなら、次の順に進める。

1. P1-11/P3-14: UI/UXを通常業務導線へ整理する。
2. P3-01/P3-02/P3-12: 編集保存、再生成比較、承認/exportの次アクションを1本の流れにする。
3. P1-16: feedback以外のappend-only writeをRLS write化する。
4. browser `/auth/google`: core staging gate とは切り分けて、client-side blocker 解消後の追加確認を行う。

### 手動ブラウザレビュー開始ライン

手動ブラウザレビューは、目的を分ければ **今から開始してよい**。

1. **今すぐ始めてよい**
   - 一覧/新規作成/詳細/ソース登録/生成開始/preview/validation/編集保存/承認/export の通常導線レビュー
   - staging URL 上の未認証境界、ジョブ詳細、既存導線の見た目と操作感の確認
2. **残件反映後にやる**
   - browser `/auth/google` の実同意確認
   - Cloud Monitoring alert の実通知確認
   - retention の実削除確認

つまり、UI/導線のレビューはもう始めてよく、運用通知とブラウザOAuthの最終レビューは残件処理後に回す。

外部環境がない状態で「済」に近づけられる主なタスクは、P1-11/P3-14、P3-01/P3-02、P1-16、P2-09、P3-12。外部環境が必要で「済」判定まで進められない主なタスクは、P2-05、P2-06、P2-10、P2-13、P2-14、browser `/auth/google` 追加確認。

## マイルストーン

| フェーズ | 状況 | 成果物 | 完了条件 |
|---|---|---|---|
| Phase 0: 整備 | 済 | プロンプト断片正本化、prompt_version、ジョブ表現スタブ | スクリプトとアプリが同じプロンプト断片を参照できる |
| Phase 1: MVP | 骨格実装済み・ライブE2E成功・通常UI/RLS第一弾済み | Supabase Postgres、OAuth取得、ジョブ保存、モックLLM、Markdown生成、検証、フィードバック、HTML断片UI、Cookie+CSRF、RLS主境界 | 実案件でチューニング記録を残しながら生成できる。残りは通常UIの編集/再生成/承認へ寄せる |
| Phase 2: 品質 | 進行中 | 決定的バリデーション拡充、pytest、provider mock、GitHub Actions、エラーハンドリング、冪等性、worker lease、保持削除、監視 | CIでモック生成パイプラインが通り、二重送信・stuck job・PII/secret・プロンプトインジェクション・保持削除を検証できる |
| Phase 3: MVP体験完成 | 進行中 | 編集後Markdown保存、再生成、再生成メタ比較、複数タブ競合防止、running復帰表示、HTMLエクスポート、ファイル保存、送付エクスポート、既存全文エディタbridge、人間承認ゲート、Playwright | 現行全文エディタの必須操作をサーバ保存前提で内包し、承認後の送付/エクスポートまでPlaywrightで確認できる。stagingのHTTP smoke / worker smoke / seeded real Google OAuth refresh token による live E2E は通過済みで、残る browser `/auth/google` 実同意確認は client-side blocker 解消後の追加確認とする |
| Phase 4: 統合 | 後続スコープ外 | 指導管理ポータルへの組み込み、ジョブ履歴一本化、指導枠ごとのデータソース一元管理、production昇格 | 今回プロジェクトの完了条件ではない。staging MVP完了後に別計画として扱う |

## 一部完了タスクの済条件

この表は、各タスクの状態を `一部完了` から `済` へ上げるための判定条件を固定する。細かい実装履歴は各タスク行と [verification-log.md](verification-log.md) を正とし、この表では「何ができれば済か」だけを見る。

| ID | 済へ上げる条件 |
|---|---|
| P1-02 | mock認証の利用範囲がlocal/test限定として文書化され、Cookie/CSRF/RLSありの通常UIテストとBearer互換APIテストの両方で、mock/admin/userの権限差分がfocused testで固定される |
| P1-03 | staging Supabaseへ全migrationを適用し、Supabase Auth role + RLSでowner閲覧/非owner拒否/管理用途の境界を実DB E2Eで確認し、production適用手順をrunbook化する |
| P1-06 | Docs/Sheets/手入力/source summaryのsnapshot保存、content_hash/source_bundle_hash、重複防止、RLS可視性、PII-safe logging、再実行時の同一source再利用がfocused + ライブE2Eで確認される |
| P1-07 | 3件制限、queued/running/succeeded/failed/cancelled、claim/lease/retry/cancel、Cloud Run Jobs実行、stagingでのstuck recovery smokeが通り、通常UIから状態復帰を確認できる |
| P1-08 | OpenRouter report/lightの通常経路、timeout/retryable/non-retryable分類、token/cost記録、model fallback、Secret非露出がmock + 実API smokeで固定される |
| P1-09 | `draft_markdown` / `final_markdown` の保存、hash、版管理、RLS可視性、編集競合、再生成比較、承認対象hashの一貫性がfocused + Playwrightで確認される |
| P1-10 | 必須見出し、禁止語、対象外生徒、数値/日付、内部メモ露出、source evidence境界、warning/error/infoの扱いが決まり、承認ゲートと連動する |
| P1-11 | ジョブ一覧・新規作成・詳細・プレビューがDaisyUI標準で統一され、検索/フィルタ/ページング、次アクション表示、空/失敗/権限なし状態、Playwright連続E2Eが通る |
| P1-12 | feedback作成/一覧/監査/RLS write、再生成への反映、重複送信防止、一般ユーザーと管理者の見え方がfocused testで固定される |
| P1-14 | 通常UIで必要な画面操作がすべてHTML page/action/fragmentで完結し、失敗時専用error fragment、running/cancel復帰、JSON API非依存がPlaywrightで確認される |
| P1-15 | server-side session refresh/rotation、logout、Cookie失効、CSRF再発行、Bearer UI経路の棚卸し完了、staging HTTPS Cookie動作確認が済む |
| P1-16 | feedback以外のappend-only writeもuser-JWT Supabase client経由へ移し、通常ユーザー操作のread/writeがRLS主境界で通り、direct DB用途がworker/admin/migration/retentionに限定される |
| P2-01 | 匿名化ゴールデンフィクスチャを複数科目/複数家庭/失敗ケースまで揃え、prompt build、validation、source summary、snapshot再現テストへ接続する |
| P2-03 | validation rule setのseverity、表示文、承認ブロック条件、repair/手動修正の扱いが固定され、代表fixtureで期待結果が安定する |
| P2-04 | 各stageの `error_type` / retryable / user_action_required / manual_recovery_required が列挙され、API/HTML/worker/logの表示が同じ分類を使う |
| P2-05 | Cloud Run実ログでPII/secret/source本文が出ないことを確認し、失敗系ログもallowlist構造化ログだけになる |
| P2-06 | GitHub ActionsでPR/pushのfocused suite、manual staging smoke、失敗時artifact/log閲覧手順が固定され、必須branch protectionへ接続できる |
| P2-07 | 匿名化手順、再匿名化チェック、元データ参照禁止、fixture更新レビュー手順が文書化され、CIでfixture内PII検査が走る |
| P2-08 | 複数生徒/複数家庭/別姓/同姓/兄弟姉妹の混入防止fixtureが揃い、source summaryとdraft生成の両方で対象外情報が配布面へ出ない |
| P2-09 | Cloud Run複数インスタンスでもidempotency recordがatomicに効き、approval/export/distribution/worker成果物がhash upsertまたは一意制約で二重作成されない |
| P2-10 | staging Cloud Run Jobs worker smokeは2026-05-19に成功済み。成功/no_job/failed/manual_recovery_requiredの終了コードと監視alert/runbook接続を検証ログに残す |
| P2-11 | ライブ成功/失敗サンプルを複数蓄積し、禁止語・置換・warningの辞書と承認ブロック条件を更新、回帰fixtureに追加する |
| P2-12 | staging/実DBでdry-run件数確認→delete→削除後確認→監査ログ確認を実施し、OAuth credential削除とStorage object削除の管理入口/runbookを用意する |
| P2-13 | stagingへのmigration適用、Cloud Run service HTTP smoke、Cloud Run Jobs worker smoke、production promotion checklistがCI/runbook/verification-logでつながる。Cloud Run service/job smokeは2026-05-19に手動確認済み |
| P2-14 | Cloud Monitoring alert policy、日次token/cost集計job、quota dashboard、budget guardrailの停止feature flagまたは管理操作入口がstagingで確認される |
| P3-01 | 保存後の次アクション、承認/exportへの導線、runningからの復帰表示、final/draft切替、古い保存拒否が通常UI Playwrightで通る |
| P3-02 | 再生成後の新ジョブ遷移、比較候補選択、差分表示、実Google取得済みジョブ同士の比較、active job拒否がPlaywright/ライブE2Eで確認される |
| P3-03 | 管理者設定画面でprompt/model既定値を管理でき、一般ユーザー非表示、監査ログ、再生成比較への反映が確認される |
| P3-04 | iframe内直接編集、書式ツールバー、プレビュー更新、保存/差分/承認への反映がPlaywrightで確認される |
| P3-05 | HTML編集プレビュー、HTML差分、保存競合、download/distribution連携、承認hash再確認がfocused + Playwrightで通る |
| P3-06 | 既存静的プレビュー相当のHTML体裁、download、distribution package、承認済みhashとの一致、未承認/validation errorブロックが確認される |
| P3-07 | ローカル保存名、ファイルから開く、PDF/ZIPなどMVP配布形式、失敗時表示が通常UIで確認される |
| P3-08 | 送付先管理、送付履歴、差戻し、外部送信を行わない手動送付監査フロー、将来メール送信境界が固定される |
| P3-09 | draft/final/html export/別ジョブ再生成の差分が同一UIで見られ、Playwrightで比較操作が通る |
| P3-10 | 自己完結Playwright、起動中ローカルsmoke、実Google/source summary、実OpenRouter APIライブE2E、staging service/worker smoke、staging live E2Eをすべて検証ログに残す |
| P3-11 | 既存サンプルmanifestとの対応、legacy editorでの編集結果再取込、静的プレビューとの差分吸収が確認される |
| P3-12 | 承認監査ログ、再承認条件、送付/export/distributionとの状態遷移、管理者/一般ユーザー権限差分がfocused + Playwrightで通る |
| P3-13 | running復帰表示、HTMXエラー通知、timeout/sendError/responseError、複数タブ保存競合をPlaywrightで確認し、見た目もDaisyUIで統一する |
| P3-14 | ジョブ一覧、新規作成、detail page本体、approval/export/source登録がDaisyUI table/form/steps/modal中心に統一され、手動UIレビューで「何を確認すればよいか」が明確になる |

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
| P1-11 | 一部完了 | ジョブ一覧・詳細・プレビュー画面。通常UIの一覧/詳細/preview fragmentを実装し、一覧に次の操作、source/artifact件数、最新artifact、validation errorを表示。詳細画面に現在位置サマリー、次操作、承認/export状態、ショートカット導線を追加し、プレビューは表示中artifact種別を明示。編集保存フォームは最新preview artifactでprefillする。2026-05-18に一覧の検索/状態フィルタ、Google Docs/Sheets URL投入からOpenRouter生成まで進める「取得してレポート生成」導線、ジョブ作成/ソース取得/要約/生成/検証の状態と日時が見える実行状況ログ、ソース本文の折りたたみ表示を追加済み。同日に通常UIから実Google Docs/Sheets + 実OpenRouterで `status=succeeded`、ソース3件、レポートビュー反映、validation表示まで確認。残りはページ全体のDaisyUI統一、ページング、staging URLでの連続E2E |
| P1-12 | 一部完了 | フィードバック保存 |
| P1-13 | 済 | 肥大化時にSupabase Storageへ移すための `storage_path` カラムを初期スキーマに含める |
| P1-14 | 一部完了 | 通常UI用の `/monthly-reports/*` HTML page/action/fragmentルータを本番側へ追加し、ジョブ作成・ソース確認/手動保存/Google取得・取得内容要約・生成開始・モック生成完了・OpenRouter生成・進捗・プレビュー・検証・フィードバック・編集保存・再生成・キャンセル・承認・HTMLエクスポート・エラーをHTML断片で返す。Google取得actionはソース一覧だけでなく、`mock/admin` では任意でOpenRouter即時生成まで実行し、通常Supabaseユーザーでは worker-owned workflow request として queued job を worker 待ちへ進める。残りは失敗時専用エラー断片の整理、ページ全体のDaisyUI統一、キャンセル中running jobのpolling復帰表示 |
| P1-15 | 一部完了 | HTTPOnly/Secure/SameSite Cookie + CSRFを本番UI認証境界として実装し、Bearer token前提の経路をE2E/内部JSON API/移行互換へ限定する。HTML action用CSRF cookie + hidden token検証をジョブ作成・生成開始・ソース保存・Google取得・フィードバック保存へ追加済み。さらに `eb_auth_session` HTTPOnly CookieからSupabase JWTを検証する移行ブリッジを追加済み。残りはserver-side session refresh/rotation、Cookie失効/ログアウト、Bearer UI棚卸し |
| P1-16 | 一部完了 | Supabase RLSを主境界にするため、ユーザーJWT付きSupabase Client生成を導入し、service role/direct DBの用途をworker・管理・migration・保持削除へ限定する。第一弾として検証済みaccess tokenを `CurrentUser` に保持し、ユーザーJWT付きSupabase anon client生成ヘルパーとRLS実効Postgresテストを追加済み。第二弾として通常ユーザーのJSON読み取りAPI（jobs/detail/sources/artifacts/validations/llm-calls）と通常UI一覧をRLS read store優先へ移行済み。第三弾として通常HTML UIのGET detail/status/preview/sources/validation fragment読み取りをRLS read store優先へ移行済み。第四弾として編集後Markdown保存/再生成、第五弾としてsource保存/Google source取得/feedback保存/生成開始のHTML write action、第六弾として通常JSON write APIへRLS read preflight認可を追加済み。第七弾としてfeedback保存を最初のfull RLS write POCにし、通常Supabaseユーザーはuser-JWT Supabase client経由で `monthly_report_feedback` へinsert、mock/adminはdirect fallbackを維持する。第八弾として artifact append-only write の一部を user-JWT Supabase client へ拡張し、通常Supabaseユーザーの `approval` / `export_html` / `distribution_package` と HTMLソース編集、および `POST /api/monthly-reports/jobs/{job_id}/artifacts` を RLS write store 経由で保存できるようにした。第九弾として通常HTML UIの `final_markdown` 保存と `source_summary_markdown` 保存も RLS write store 経由へ移行し、source summaryのソース読み取りもRLS read store優先にした。第十弾として通常HTML UI / 通常JSON API の手動source保存と Google source取得も RLS write store 経由へ移行した。第十一弾として direct DB state mutation JSON route (`start` / `complete-stage` / `fail` / `cancel` / `run-*` / `rerun`) に `X-EB-Caller-Intent` guard を追加し、内部/管理/E2E 用として明示した。第十二弾として通常JSON API の validation 保存も user-JWT Supabase client 経由の RLS write store へ移し、idempotent response 記録だけ direct store に残す形へ分離した。第十三弾として `source-summary` HTML action の artifact/RLS write と `llm_call_logs` / idempotency / audit / workflow state mutation の direct 境界を棚卸しし、`llm_call_logs` は server-owned telemetry として残す前提を test と設計文書へ反映した。第十四弾として通常UIから到達できる service-owned workflow 実行（`/run`, `after_fetch_action=generate_openrouter`）を helper と server-side audit log で明示し、focused test で direct workflow 境界を固定した。第十五弾として通常Supabaseユーザーにはこの direct workflow 実行を開放せず、`mock/admin` 補助導線に限定する backend guard と detail UI の disable/説明文を追加した。第十六弾として通常Supabaseユーザーの既定 `run_mode=stage` と `after_fetch_action=generate_openrouter` を worker-owned workflow request へ切り替え、queued job のまま worker 待ちに進める監査ログ・status文言・operation log を追加した。第十七弾として Cloud Run Jobs `jobs.run` を server-side trigger する executor と、`EB_WORKER_JOB_ID` override を使う targeted worker 起動を追加し、通常UIからの queued request がそのまま該当 job の worker 実行へつながる経路を実装した。残りは trigger 設定の staging/prod 反映、失敗時 monitoring/runbook、worker/管理/migration/保持削除境界の固定。並行化する場合は、A: user-content write/RLS、B: direct workflow 実行の縮退、C: direct telemetry/idempotency/audit 文書化と focused test、の3トラックに分割して進める |
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
| P2-09 | 一部完了 | POST系API/HTML actionにIdempotency-Keyまたはjob input hashを導入し、二重送信・リロード・worker再試行時の挙動を固定する。job作成、`run-mock`、`run-openrouter`、source保存、Google source取得、artifact保存、validation保存、feedback保存、編集後Markdown保存、source summary、approval保存、HTML export作成、distribution package固定の冪等性を実装し、Google取得の同一キー再送では外部APIを再実行しないfocused testも追加済み。approval/export/distributionは同一プロセス内の同一key同時実行をlockし、Postgres永続化用 `monthly_report_idempotency_keys` migration/storeとHTML hidden keyも追加済み。残りはCloud Run複数インスタンスでのapproval/export/distribution完全atomic化、worker再試行時の成果物単位hash upsert |
| P2-10 | 一部完了 | Cloud Run worker本番化に向け、lease timeout、heartbeat/updated_at、stuck job再claim、retry上限、手動再実行、協調的キャンセルを実装・テストする。worker実行結果サマリ、provider実行前キャンセル境界、worker attempt/max attempt、lease timeout後のstale `running/fetch_sources` reclaim、retryable failureのqueued復帰、worker heartbeat/touch primitive、lease指定時のprovider call中best-effort heartbeat、Cloud Run worker entry/runbookを実装し、実DB Postgres focused testも通過済み。後段stageは自動再claimしない方針をfocused testで固定し、stale後段jobはPII-safeな `manual_recovery_required` summaryと非0終了で検知する。手動回復runbookは、検知、安全確認、retry/requeue/cancel判断、監査、保持削除との相互作用、エスカレーションまで `security-operations.md` に具体化済み。2026-05-18にCloud Run Jobsの作成/更新/実行コマンド例、必要env/secret、期待JSON summary、`no_job`/`failed`/`manual_recovery_required` の判定、GitHub Actions manual HTTP smokeとの役割分担を追記済み。2026-05-19にworker jobをimage `asia-northeast1-docker.pkg.dev/gen-lang-client-0360012476/monthly-report-workshop/monthly-report-workshop:01c993a-templatefix-20260519` へ再deployし、smoke execution `monthly-report-worker-staging-fpfks` が成功。追加で、stuck `running` job を `manual_recovery_required` で閉じる admin-only JSON route `POST /api/monthly-reports/jobs/{job_id}/manual-recovery/fail` を実装し、PII-safe audit log を残す最小の管理操作入口を用意した。残りは Cloud Monitoring の worker failed / manual recovery / stale job alert policy 作成、通知先設定、runbookへの運用導線固定、必要なら管理操作入口の拡張 |
| P2-11 | 一部完了 | Google Docs/Sheets由来のプロンプトインジェクション、内部メモ露出、送付禁止語、対象外生徒混入の検証を拡充する。明示的なプロンプトインジェクション文言、内部/管理メモ露出、`Gemini メモ` / `Google Meetメモ` / Google生成メモ系配布面メタ語彙のsanitizationをfocused testで固定済み。残りはE2Eサンプルを増やした語彙variant追加と承認ゲート連動 |
| P2-12 | 一部完了 | 保持期間削除ジョブを設計・実装し、ドライラン件数確認、削除後確認、監査ログ、OAuth credential削除runbookを含める。第一弾として `src/eb_app/monthly_reports/retention.py` にDB非依存のplanner/executor、Postgres用repository、dry-run/delete監査ログmetadataを追加し、unit testで外部Secretなしに対象件数・削除順・PIIを含まない監査metadataを固定済み。追加で `src/eb_app/monthly_reports/retention_entry.py` にCloud Run Jobs向けentryを追加し、既定dry-run、JSON summary、DB URL不足/失敗時非0、PII-safe出力をsecret不要unit testで固定済み。2026-05-18に `--delete` は `--confirm-total-eligible-count` 必須へ強化し、削除直前dry-runの総対象件数と一致しない場合は非破壊で終了する契約をfocused testで固定済み。残りは実DBでの削除後確認、OAuth credential削除の管理操作入口、Storage移行後のobject削除連動 |
| P2-13 | 済 | GitHub Actionsにmigration/static schema/RLS guardrailを追加済み。既定のPR/pushでは実Secret・Supabase Docker不要で静的SQLチェックとfocused pytestを実行する。Cloud Run serviceのHTTP smokeは `workflow_dispatch` + `run_cloud_run_smoke=true` の手動実行に限定し、repository secret `CLOUD_RUN_SMOKE_URL` と任意の `CLOUD_RUN_SMOKE_BEARER_TOKEN` を使う。Cloud Run Jobs worker smokeはActionsではなく運用者の手動実行として扱い、PII-safe summaryと終了コードを検証ログに残す。2026-05-19に `/health` 200、未認証 `/monthly-reports/jobs` 401、`/auth/google` 200のstaging service smoke、worker smoke execution `monthly-report-worker-staging-fpfks`、seeded real Google OAuth refresh token による staging API live E2E success を確認し、[production-promotion-checklist.md](production-promotion-checklist.md) を追加済み。`/healthz` はCloud Run予約URL挙動でGoogle Frontend HTML 404になるため、staging/prod smoke対象外。ブラウザ `/auth/google` 実同意確認は app 未達成項目ではなく、client-side blocker 解消後の追加確認として別管理に切り分ける |
| P2-14 | 一部完了 | Cloud Run 5xx/timeout/latency/memory、worker failed/stuck/retry、OpenRouter token/cost/error、Google API quota/OAuth refresh失敗、429/CSRF/403 spike、budget guardrailのMVP監視runbookを `security-operations.md` に追加済み。2026-05-18に第二弾として `src/eb_app/monthly_reports/observability.py` へsecret-freeなログベースmetric定義と日次token/cost summary contractを追加し、metric名・label・filter、alert threshold、budget guardrail停止手順を文書で固定した。2026-05-19時点で staging の worker smoke execution `monthly-report-worker-staging-fpfks` を監視配線前の正常系基準として残し、`manual_recovery_required` と stale fetch_sources を alert policy で検知して `security-operations.md` / `staging-deploy-runbook.md` の runbook へ遷移する前提を固定した。残りはCloud Monitoring alert policy実作成、日次集計job/SQL、quota dashboard、新規OpenRouter実行停止feature flagまたは管理操作入口 |

## Phase 3 タスク

| ID | 状態 | タスク |
|---|---|---|
| P3-01 | 一部完了 | 編集後Markdown保存。通常UI詳細画面にHTMX保存フォームとbackend routeを追加し、`final_markdown` artifact保存とpreview fragment更新をfocused testで固定済み。`draft_markdown` / `final_markdown` は引き続き再現性・差分・承認基準のための中間成果物として保持する。一方で、通常運用ユーザーにMarkdown直編集を要求しない方針へ切り替え、詳細画面では配布面プレビューを主領域、Markdown保存は補助領域へ降ろした。保存競合と複数タブの古い保存拒否はfocused/Playwrightで固定済み。running中はページを閉じても処理継続/自動更新/再読み込み復元の案内を出し、後段stageで長時間heartbeatがない場合はworker runbook確認を促す。残りは保存後の次アクション導線、running復帰表示のPlaywright確認、HTML主編集面との接続整理 |
| P3-02 | 一部完了 | 再生成API/UI。通常UI詳細画面にHTMX再生成フォームとbackend routeを追加し、新しいqueued jobの作成通知と新ジョブ詳細リンクを専用panelへ返す。admin再生成override時も新しいqueued jobを作成する。さらに `rerun-comparison` fragmentで元/比較先ジョブの再現性メタを横並び表示し、同一世帯/同一ユーザーの比較候補をdatalistで選べる。`rerun-diff` fragmentでは元/比較先ジョブの最新Markdown同士を行単位で比較し、自己完結Playwrightにも接続済み。backend側でもactive job再生成拒否、同一世帯比較制約、Markdown専用diff、同一Idempotency-Key二重送信ロックをfocused testで固定済み。残りは比較結果の見た目調整と実Google取得を含むライブE2E |
| P3-03 | 一部完了 | 管理者向けprompt/model override。新規ジョブ作成UIと再生成フォームにadmin限定の `prompt_version` / `model_report` / `model_light` 入力欄を追加し、一般ユーザーには非表示かつフォーム投稿値も破棄するfocused testを追加。比較fragmentで変更メタを確認可能。残りはadmin設定画面 |
| P3-04 | 一部完了 | 現行HTML全文エディタ由来のiframe編集領域と1行ツールバー。第一弾としてHTMLソース編集fragmentにsandbox iframeプレビューと簡易ツールバーを追加し、export済みHTMLを同じ画面で確認できる。主編集対象はMarkdownではなくHTML/配布面側に寄せる。残りはiframe内直接編集、書式ツールバー、プレビュー更新の操作性改善 |
| P3-05 | 一部完了 | HTMLソース直接編集。`GET /monthly-reports/jobs/{job_id}/fragments/html-source` で最新 `export_html` artifactをtextarea表示し、未export時はHTML断片でブロック理由を返す。`POST /fragments/html-source` はCSRF、RLS read preflight、Idempotency-Key、非空本文、最新export hash一致を要求し、編集済みHTMLを新しい `export_html` artifactとして保存する。Markdownは生成安定化用の中間成果物として残しつつ、最終的な人手修正導線はHTML側へ集約する。残りはHTMLプレビューとの並列表示、差分、ファイル保存/送付導線との接続 |
| P3-06 | 一部完了 | HTMLエクスポート。`GET /monthly-reports/jobs/{job_id}/fragments/export` とdetail panel、`POST /fragments/export` を追加済み。現行承認がある場合のみ最新配布artifactから `export_html` artifactを作成し、未承認、validation errorあり、承認対象hash不一致ではHTML error fragmentを返す。Idempotency-Keyで二重作成を防ぐ。残りは既存静的プレビュー相当のHTML体裁、ファイル保存/送付エクスポートとの接続 |
| P3-07 | 一部完了 | ファイル保存・ファイルから開く。第一弾として最新 `export_html` artifactをHTML attachmentとして保存する `/download/export-html` を追加し、通常UIの送付/配布panelからリンクできる。残りはファイルから開く、ローカル保存名のUI調整、PDF/ZIPなど配布形式 |
| P3-08 | 一部完了 | 送付エクスポート。第一弾として承認済みHTML exportを `distribution_package` artifactとして固定するHTMX fragment/actionを追加。実メール送信は行わず、手動送付用の監査可能な成果物を残す。残りは送付先管理、メール/外部送信、送付履歴、差戻し |
| P3-09 | 一部完了 | 生成物と最終編集後HTML/Markdownの簡易テキスト差分表示。依存なしの行単位Markdown diff helper、`GET /monthly-reports/jobs/{job_id}/fragments/diff`、detail画面の差分panelを追加し、`unchanged` / `added` / `removed` の構造化行とHTML escaped済みplain text payload、draft/final不足時のHTML表示をfocused testで固定済み。残りはHTML exportとの差分、再生成job間比較、Playwright連続E2E |
| P3-10 | 済 | Playwrightによるエディタ体験・保存・差分・送付エクスポートE2E。第一弾として `tests/test_monthly_report_playwright_smoke.py` を追加し、ローカル実サーバのdetail画面で押せる/押せない制御、required、Google source表示、sheet-selectorを確認できる。第二弾としてsecret不要の自己完結ローカルPlaywrightで、detail page → 手動ソース保存 → mock生成 → final Markdown保存 → 承認 → HTML exportまで通過済み。第三弾として送付用 `distribution_package` 固定と `rerun-comparison` 比較フォーム送信まで拡張。第四弾としてリロード後のstatus/final preview/承認/export/distribution復元を確認。第五弾として `rerun-diff` の本文差分フォーム送信まで確認。第六弾として実Google/source summaryの通常UIライブsmokeと、実Google Docs/Sheets + 実OpenRouterのAPIライブE2Eを2026-05-18に確認済み。第七弾として通常UIの「取得してレポート生成」から実Google Docs/Sheets取得、OpenRouter生成、プレビュー反映、operation log/validation復元表示まで確認済み。2026-05-19にstaging service smoke、worker smoke、seeded real Google OAuth refresh token による staging API live E2Eが完了し、done条件に含めていた検証ログ記録も揃った。ブラウザ `/auth/google` 実同意確認は client-side blocker 解消後の追加確認として別管理に切り分ける |
| P3-11 | 一部完了 | 既存静的プレビュー経路との接続。`docs/samples/monthly-reports/tools/monthly_report_full_editor.html` を `/monthly-reports/legacy-full-editor` から同一オリジンで提供し、HTMLソース編集パネルから開ける互換リンクを追加。さらに `/monthly-reports/jobs/{job_id}/legacy-full-editor` で最新 `export_html` artifactを既存全文エディタのlocalStorageへ投入して開けるbridgeを追加。残りは既存サンプルmanifestとの対応付け、静的プレビューとの差分吸収、編集後の工房再取込 |
| P3-12 | 済 | 生成成功、検証OK、編集保存済み、承認済み、送付/エクスポート済みを分ける人間承認ゲートを実装する。`GET /monthly-reports/jobs/{job_id}/fragments/approval` とdetail panel、`POST /fragments/approval` を追加済み。最新 `final_markdown` 優先の承認対象artifact hash、validation/生成状態のブロック理由、承認保存、配布artifact更新後の再承認必須表示をHTML断片で返す。2026-05-18に detail 画面へ `承認 -> HTMLエクスポート -> 送付用固定` の一本道ガイドと、各fragmentの「次の操作」案内を追加済み。2026-05-19に approval / export / HTML source edit / distribution package の server-side 監査ログを追加し、artifact write はRLS write store・audit は direct store で分離した。さらに管理者/一般ユーザーのチューニング欄表示差分を self-contained Playwright で固定し、承認/export/distribution の状態遷移は focused + Playwright で通過済み |
| P3-13 | 一部完了 | 複数タブ編集、保存競合、HTMX polling失敗、長時間生成中のリロード復帰をUI仕様・Playwrightで確認する。第一弾として編集Markdown保存の `base_content_hash` が提示されており、かつ最新preview artifact hashと一致しない場合は409で拒否し、同じIdempotency-Key再送は初回結果を返すfocused testを追加。承認/export/html source/distributionは定期pollingではなく `monthly-report-refresh` イベント更新にして入力中の再描画消失を避ける。さらに `htmx:responseError` / `sendError` / `timeout` を共通エラーバナーで表示し、自己完結Playwrightでリロード後の操作状態復元、複数タブの古い保存拒否、running中の復帰案内、stale後段stageのworker runbook案内まで確認済み。残りはエラー通知の見た目調整 |
| P3-14 | 一部完了 | Tailwind CSS + DaisyUIのUIコンポーネント標準化。第一弾としてalert/status/validation/feedback/sources/preview fragmentsをDaisyUI `alert` / `badge` / `table` / `prose` 中心へ整理済み。2026-05-19に detail 画面の workflow board / summary / quick nav / operation log / sources / preview / validation / approval / advanced compare / distribution の連続 UI 確認を self-contained Playwright で追加し、主要パネルの空状態・再読込復元・HTML fragment 更新が崩れないことを確認した。さらに同日に `jobs.html` / `new.html` / `fragments/approval.html` を detail ページ寄りの骨格へ寄せ、一覧の役割説明、作成画面の進行ガイド、承認状態の要約を追加し、`detail.html` の生成操作・ソース登録・フィードバック周辺も共通ボタン/フォームクラスへ寄せた。2026-05-20時点で、Markdown編集を主領域に置く暫定ワークベンチから、配布面プレビューとHTML側導線を主とし、Markdownを補助領域へ下げる方向へ方針転換した。残りは detail page本体と approval/export 周辺の見た目統一、HTML主編集面の操作性改善 |

## 現時点の検証

詳細な検証コマンド履歴は [verification-log.md](verification-log.md) を正とする。開発計画本文では、次の判断に必要な代表値だけを残す。

| 区分 | 最新の代表結果 | 意味 |
|---|---|---|
| 広いmock focused suite | 2026-05-17時点で **179 passed, 1 skipped** | RLS read store移行、Phase 2 CI対象suite、プロンプトインジェクション/内部メモ露出validationを含むmock focusedが通過 |
| RLS / schema 実DB focused | 2026-05-17時点で **8 passed** | 実DB RLS評価とRLS migration静的確認が通過 |
| 通常UI / API / worker focused | 2026-05-18時点で **18 passed** のRLS/feedback focused、P3/P2統合は直近 **135 passed, 1 skipped** まで確認 | worker stale reclaim境界、承認/HTML export GET fragment、API・HTML UI・worker focusedが通過。再生成リンク、比較候補、rerun diff、running復帰表示、再生成actionのbackend guard、feedback full RLS write POCも確認済み |
| Observability focused | 2026-05-18時点で `tests/test_monthly_report_cloud_logging.py` **7 passed** | P2-14のログallowlist、ログベースmetric定義、日次token/cost summary contractがPII/secret fieldを含まないことを確認 |
| Playwright smoke | 2026-05-18時点で自己完結smoke、起動中ローカルUI smoke、実Google/source summary smokeが通過。2026-05-19にstaging service smoke（`/health` 200、未認証jobs 401、`/auth/google` 200）とworker smokeが通過 | browser `/auth/google` 実同意の client-side blocker 解消後に追加確認 |
| ライブE2E | 2026-05-18時点で実Google Docs/Sheets + 実OpenRouter + validation succeededの保存サンプルあり | job `mrj_d3e6e1e884ba4cb4b44c2c9d2044250b` を成功サンプルとして記録。本文・ソース本文・Secret値は記録しない |

今回の文書整理ではコード・テストは変更しない。Markdown差分の整合確認として `git diff --check` を実行する。

## 依存関係

- Supabaseスキーマ案は初期migrationとして作成済み。Postgres storeも追加済み。次はRLS、実Supabase Auth検証、実ジョブ永続化の拡張が必要。
- 月次レポートAPIは認証依存関係を通す。ローカルMVPでは `owner_user_id` 暫定値を許可し、Supabase Auth接続時は認証ユーザーIDへ差し替える。2026-05-16以降の本番UI方針はCookie+CSRF、内部/E2E/移行期JSON APIはBearer token互換とする。
- 通常UIはHTML page/action/fragmentを優先する。既存JSON APIはworker/E2E/管理/将来連携用として残すが、UIのDOM更新はHTML断片で行う。
- RLSは主境界へ寄せる。ユーザーJWT付きSupabase Client経路の導入前は、direct DB/API側認可が暫定境界であることを明示し、本番UI完成条件にしない。
- P1-16は通常ユーザーJSON読み取りAPI、通常UI一覧、HTML detail/status/preview/sources/validation fragment読み取り、主要HTML write actionのRLS read preflight認可に加え、feedback / artifact / final_markdown / source_summary / source / Google source取得 / validation 保存まで user-JWT Supabase client 経由の write を順次拡張済み。残りは `llm_call_logs` を含む direct DB呼び出しの棚卸しと、worker・管理・migration・保持削除への境界固定。
- prompt_version管理が決まらないと、チューニング比較が曖昧になる。
- U-025は解決済み。静的POCの `prompts.scope_reminder` は工房ジョブ/APIでは `prompt_scope_notes` とする。初期投入はレシピ由来 + 手入力可能、householdメタからの自動生成は後続に回す。
- ジョブ状態モデル、モックAPI、DB永続化、3件制限、`prompt_scope_notes` 保存、provider mock通電、実OpenRouter少量通電、LLM呼び出しメタ保存、DB-backed workerのclaim境界は骨格実装済み。次は常駐worker/Cloud Run実行方式と、実案件ソースでのチューニング比較UIが必要。
- OpenRouter呼び出し抽象は実装済み。キー情報エンドポイントと `chat/completions` の工房本体通電は確認済み。
- 実Supabase Auth + Google OAuth + Google Workspace read flowのライブE2E前設定は [pre-e2e-setup.md](pre-e2e-setup.md) を参照する。
- Auth & OAuth Agentの初手として、`/auth/google` と `/auth/callback` のE2Eブリッジを追加済み。`SUPABASE_URL` / `SUPABASE_ANON_KEY` だけをブラウザへ渡し、Supabase sessionの `provider_refresh_token` は `/api/auth/google-oauth/supabase-session` へ送って暗号化保存する。
- `/monthly-report-workshop/e2e` はライブE2E用の開発導線として使う。`/auth/callback` でcredential保存後、同じSupabase sessionで `create job -> fetch-google-sources -> run-openrouter -> result確認` を実行する。
- 実装体制として、Phase 1以降は実装オーナー＋Backend/Auth/LLM/Validation/UI/QAの役割分担を固定し、同一ファイルの同時編集を避ける運用で進める。
- 次の開発優先順は「P1-11/P3-14 UI/UX整理」「P3-01/P3-02 編集保存・再生成UI継続」「P2-10 worker本番化継続」「P1-16 RLS client化継続」「P2-14/P2-12 運用」「browser `/auth/google` 追加確認」の順で固定。

## 環境変数ガイド

手動設定が必要な環境変数は `.env` を正とし、値はログ・ドキュメント・完了報告に出さない。ローカルPostgres/Supabase込みのfocused testでは、少なくとも `EB_MONTHLY_REPORT_DATABASE_URL` をプロセス環境へ読み込む。

| 用途 | 必須キー | 備考 |
|---|---|---|
| Postgres store/API focused test | `EB_MONTHLY_REPORT_DATABASE_URL` | 未設定時は `tests/test_monthly_report_postgres_store.py` / `tests/test_monthly_report_api_postgres.py` がskipされる |
| ローカルmock認証 | `EB_AUTH_MODE=mock` | UI/API focused testは原則mockで実行する |
| Supabase Auth/JWKS E2E | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET` | `SUPABASE_JWT_SECRET` はHS256互換テスト用、ES256/RS256はJWKS経由 |
| OpenRouter実通電 | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL_REPORT` | 通常のpytestでは実APIを叩かず、provider mockを使う |
| 通常HTML UIのGoogle取得 | `EB_GOOGLE_WORKSPACE_ACCESS_TOKEN` または `EB_MONTHLY_REPORT_DATABASE_URL`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `EB_GOOGLE_TOKEN_ENCRYPTION_KEY` | 前者は暫定ローカル経路。後者は保存済みGoogle OAuth refresh tokenからaccess tokenを再取得する本来経路 |
| P3-10 PlaywrightライブGoogle取得 | `MONTHLY_REPORT_PLAYWRIGHT_SMOKE=1`, `MONTHLY_REPORT_LIVE_GOOGLE_E2E=1`, `MONTHLY_REPORT_JOB_ID`, `MONTHLY_REPORT_GOOGLE_DOC_IDS` または `MONTHLY_REPORT_SHEET_URL` | 既定skip。source summaryまで確認する場合だけ `MONTHLY_REPORT_LIVE_SOURCE_SUMMARY=1` とOpenRouter設定済みサーバを使う |
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

詳細な改訂履歴は [development-history.md#改訂履歴](development-history.md#改訂履歴) へ分離した。以後、この文書には計画の読解に必要な大きな構造変更だけを残す。

| 日付 | 内容 |
|---|---|
| 2026-05-17 | 読みやすさ改善のため、詳細な現在位置ログを `development-history.md`、検証コマンド履歴を `verification-log.md` へ分離。`development-plan.md` は現在状態、次優先、フェーズ、未完了タスク中心へ整理 |
