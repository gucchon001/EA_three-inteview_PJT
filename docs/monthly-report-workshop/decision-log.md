# 課題・決定ログ

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツールの決定事項・未決事項ログ
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- 関連文書: `README.md`, `requirements.md`, `development-plan.md`, `AUTOMATION_NORTH_STAR.md`
- 最終更新: 2026-05-19（D-073・Cloud Run worker trigger反映）

## 決定事項

| ID | 日付 | 決定 | 根拠 |
|---|---|---|---|
| D-001 | 2026-05-13 | プロダクト呼称は「月次レポート作成ツール」、別名「レポート工房」 | 移行計画書 |
| D-002 | 2026-05-13 | FastAPI + Jinja2 + HTMXを採用する | 移行計画書 |
| D-003 | 2026-05-13 | 本番ホスティングはCloud Run | 移行計画書 |
| D-004 | 2026-05-13 | MVPの認証はGoogleアカウント、`tomonokai-corp.com` 限定 | 移行計画書 |
| D-005 | 2026-05-13 | Sheets / DocsはユーザーOAuthでサーバ取得する | 移行計画書 |
| D-006 | 2026-05-13 | 当面のLLMプロバイダはOpenRouter中心 | 移行計画書 |
| D-007 | 2026-05-13 | 本文生成モデルと軽量モデルを分ける | 移行計画書 |
| D-008 | 2026-05-13 | 1ユーザー最大3生成ジョブ | 移行計画書 |
| D-009 | 2026-05-13 | 旧決定: MVPは本番のみ。ステージングはMVPでは切らない。2026-05-18のD-067で廃止 | 移行計画書・2026-05-17再確認・2026-05-18方針更新 |
| D-010 | 2026-05-13 | MVPはチューニング重視。ログ・スナップショット・生成物保存を必須とする | 移行計画書 |
| D-011 | 2026-05-13 | 推敲・プレビュー画面は現行 `monthly_report_full_editor.html` のHTML全文エディタをベースにする | ユーザー合意 |
| D-012 | 2026-05-13 | 現行エディタ由来の送付エクスポート、ファイル保存、HTMLソース編集などは後続扱いでもMVP内の必須機能とする | ユーザー合意 |
| D-013 | 2026-05-13 | ソーススナップショットの保持期間は1年とする | ユーザー合意 |
| D-014 | 2026-05-13 | ジョブメタ、生成Markdown、最終編集Markdown、検証結果、フィードバックは3年保持を初期方針とする | 作業仮説・ユーザー合意済み保持方針セット |
| D-015 | 2026-05-13 | Cloud Loggingの構造化ログは6か月保持を初期方針とし、本文や生ソースは出力しない | 作業仮説・ユーザー合意済み保持方針セット |
| D-016 | 2026-05-13 | MVPの永続化基盤はSupabase Postgresとする | ユーザー合意 |
| D-017 | 2026-05-13 | Cloud Run初期値はtimeout 900秒、1 vCPU、1GiB、concurrency 10、min instances 0、max instances 3とする | ユーザー合意 |
| D-041 | 2026-05-14 | クラウド本番リージョンは `asia-northeast1`（東京）を基本とする | ユーザー合意 |
| D-042 | 2026-05-14 | 「ブラウザ上で自動生成」を北極星とし、静的 POC と Cloud Run 工房を規約・レシプリで乖離させない方針の正本を `AUTOMATION_NORTH_STAR.md` とし Cursor ルール `monthly-report-north-star.mdc` とスキルを整合させる | 運用ぶれ対策・ユーザー依頼 |
| D-043 | 2026-05-14 | ジョブ失敗時の `error_type` / `error_message` は `monthly_report_jobs` の明示カラムに保存し、監査ログはイベント履歴として併用する | ユーザー合意 |
| D-044 | 2026-05-14 | ローカルMVPでは `owner_user_id` を暫定リクエスト値として扱い、Supabase Auth接続後は認証ユーザーIDへ差し替える | ユーザー合意 |
| D-045 | 2026-05-14 | 再生成APIと保存モデルはMVP内で用意し、再生成UIはPhase 3「MVP体験完成」で比較・チューニング導線と合わせて実装する | レビュー反映 |
| D-046 | 2026-05-14 | 静的 POC 側チューニング実装・複数生徒 MTG／Economics レシピ等の **他エージェントへの引き継ぎ正本は `HANDOFF_STATIC_POC_TUNING.md`** とする（合流チェックリスト・U-025 含む） | ユーザー依頼・複数チャット並行運用 |
| D-047 | 2026-05-14 | 静的レシピ `prompts.scope_reminder` 相当のジョブ/APIフィールド名は `prompt_scope_notes` とする | ユーザー合意 |
| D-048 | 2026-05-14 | `prompt_scope_notes` の初期投入はレシピ由来 + 手入力可能とし、householdメタからの自動生成は後続に回す | ユーザー合意 |
| D-049 | 2026-05-14 | 非同期workerの初期境界はDB-backed claim方式とし、Postgresでは `FOR UPDATE SKIP LOCKED` で `queued` jobを原子的に `running` へ進める。Cloud Tasks等の外部キューは後続検討とする | 実装方針 |
| D-050 | 2026-05-16 | レポート工房の通常画面操作はJinja2 + HTMXのHTMLページ/HTML断片を返す。`/api/monthly-reports/*` のJSON APIはworker、E2E、管理スクリプト、将来連携用に残し、通常UIからDOM更新目的で直接叩かない | 方針レビュー反映 |
| D-051 | 2026-05-16 | SSR/HTMX本番UIの認証は `HTTPOnly`, `Secure`, `SameSite=Lax` Cookie + CSRF対策を正とする。Bearer token検証はE2E、内部JSON API、移行中の互換経路として扱う | 方針レビュー反映 |
| D-052 | 2026-05-16 | Supabase RLSを主境界として効かせる方針に寄せる。通常ユーザーリクエストはユーザーJWT付きSupabase Clientを第一候補とし、service role/direct DBはworker、管理、migration、保持期間削除など限定用途に閉じる | 方針レビュー反映 |
| D-053 | 2026-05-16 | Cloud Run worker本番化前に、lease timeout、heartbeat/updated_at、stuck job再claim、再試行上限、手動再実行、協調的キャンセル、冪等性を設計・テストする | 方針レビュー反映 |
| D-054 | 2026-05-16 | POST系API/HTML actionはIdempotency-Keyまたはjob input hashにより、二重送信・リロード・worker再試行に耐える設計にする | 方針レビュー反映 |
| D-055 | 2026-05-16 | Supabase Storageへ成果物を移す場合は、bucket policy、object prefix、signed URL期限、配布用エクスポート閲覧期限、Storage削除バッチをPostgresメタデータと同時に設計する | 方針レビュー反映 |
| D-056 | 2026-05-16 | 保持期間削除は運用ジョブとして実装し、ドライラン件数確認、削除後件数確認、監査ログ、OAuth credential削除runbookを含める | 方針レビュー反映 |
| D-057 | 2026-05-16 | Google Docs/Sheets由来の本文は信頼済み命令として扱わず、プロンプトインジェクション対策・対象外生徒混入・内部メモ露出・送付禁止語を検証対象にする | 方針レビュー反映 |
| D-058 | 2026-05-16 | 家庭向け送付・エクスポート前に人間承認ゲートを置き、生成成功・検証OK・編集保存済み・承認済み・送付済みを分けて扱う | 方針レビュー反映 |
| D-059 | 2026-05-16 | Supabase 発行 access token の検証は **JWKS 経由の ES256/RS256 を本流**とし、`alg` ヘッダで分岐する。HS256 + 対称 `SUPABASE_JWT_SECRET` 経路はテスト互換と内部用途のために残す。ローカル Supabase / Supabase Cloud いずれも新 signing keys（asymmetric）で JWT を発行するため、`<SUPABASE_URL>/auth/v1/.well-known/jwks.json` の公開鍵で検証する | ライブE2E通電時の実機切り分け（ES256 token が HS256-only 検証で 401 になっていた） |
| D-060 | 2026-05-16 | ローカル Supabase（`supabase/config.toml`）では `[auth.external.google]`（`client_id`/`secret` は env(...) 参照）と `additional_redirect_urls` に `http://127.0.0.1:8000/auth/callback` を設定し、初回 Google ログインが signup 扱いで通るよう `enable_signup = true` にする。ドメイン制限は FastAPI 側 JWT email チェック（`EB_ALLOWED_EMAIL_DOMAIN`）で担保する。Cloud Supabase（本番）に移行する場合も同じ「provider 有効化 + email domain ガードは API 側」の構造を引き継ぐ | ライブE2E通電時の `422: Signups not allowed for this instance` を解消した実機判断 |
| D-062 | 2026-05-17 | 旧決定: staging / production の2環境分離はMVPでは行わず、本番ポータルへ合流するタイミングで用意する。2026-05-18のD-067で廃止 | ユーザー再確認・2026-05-18方針更新 |
| D-067 | 2026-05-18 | MVPから staging / production の2環境を用意する方針に更新したが、今回プロジェクトの完了判定からproduction昇格はD-068で除外した。Cloud Run service、Supabase project/DB、OAuth redirect URI、Secret、E2Eデータは環境ごとに分離する | ユーザー方針更新・D-068で完了条件を再固定 |
| D-068 | 2026-05-18 | 今回プロジェクトの完了条件は、指導管理ポータル統合ではなく、レポート工房MVPがstaging環境で動作し、HTTP smoke、worker smoke、RLS、Google OAuth、OpenRouter、HTML UI smoke、ライブE2Eの結果が検証ログに残ることとする。production昇格と指導管理ポータル統合は後続スコープ | ユーザー方針更新 |
| D-063 | 2026-05-17 | レポート工房のUIコンポーネントはTailwind CSS + DaisyUIを標準にする。Alpine.jsは局所状態に限定し、FlowbiteはMVP標準依存にしない。業務画面はtable/section中心、カードは繰り返し単位に限定する | UI方針レビュー |
| D-064 | 2026-05-17 | 管理者向けprompt/model tuningは、新規ジョブ作成と再生成フォームのadmin限定overrideから開始する。一般ユーザーには表示せず、直接投稿値も破棄する | P3-03実装反映 |
| D-065 | 2026-05-17 | 承認/export/html source/distributionなど入力フォームを含むpanelは定期pollingせず、`monthly-report-refresh` イベントで更新する。進捗statusはHTMX pollingを維持する | P3-13実装反映 |
| D-066 | 2026-05-17 | 既存全文エディタ連携は、同一オリジン互換routeと `export_html` artifactのlocalStorage bridgeを第一弾とし、既存エディタ編集後の工房再取込は後続に回す | P3-11実装反映 |
| D-069 | 2026-05-19 | 承認/export/HTML source edit/distribution package に加え、通常UIから到達できる workflow request / direct workflow start の監査ログも server-side direct store に記録する。通常Supabaseユーザーの artifact append-only write は user-JWT Supabase client 経由の RLS write store を使い、監査ログは通常ユーザーのクライアント可視境界に置かない | P3-12実装反映・P1-16 direct workflow audit 整合・RLS主境界と監査境界の分離 |
| D-070 | 2026-05-19 | 通常JSON API の validation 保存は、owner確認のRLS read preflight後、user-JWT Supabase client による `monthly_report_validations` insert を第一候補とする。idempotent response 記録は service-owned/direct store に残し、mock/admin/worker 互換は direct fallback を維持する | P1-16 validation write slice 実装反映 |
| D-071 | 2026-05-19 | `llm_call_logs` は通常ユーザーの編集データではなく server-owned telemetry として扱い、source-summary や worker generation からの記録は direct store に残す。RLS主境界へ寄せる対象は append-only user content を優先し、idempotency / audit / worker state mutation / llm_call_logs は直ちにRLS writeへ移さない | P1-16 direct store棚卸し・source-summary focused test反映 |
| D-072 | 2026-05-19 | 通常Supabaseユーザーの HTML `run_mode=stage` と `after_fetch_action=generate_openrouter` は、即時の service-owned workflow 実行ではなく worker-owned workflow request として扱う。`mock/admin` の `run_mode=mock|openrouter` は補助導線として service-owned 即時実行を維持し、通常ユーザー側は queued job のまま worker 待ちメッセージと監査ログで状態を表現する | P1-16 Bトラック実装・通常UIを mock 非依存へ寄せる |
| D-073 | 2026-05-19 | 通常UIの worker-owned workflow request は、Cloud Run service から Cloud Run Jobs REST API `projects.locations.jobs.run` を呼んで自動起動する。execution ごとに `EB_WORKER_JOB_ID=<job_id>` を override し、worker は対象 job だけを claim する。設定がない環境では queue request だけを受け、設定済み環境では trigger 成功/失敗を server-side audit と HTTP error で扱う | P1-16 Bトラック実装・targeted worker trigger 追加 |
| D-018 | 2026-05-13 | 長時間生成はMVPではDBジョブ + HTMXポーリングで扱い、Cloud Tasks等は後続検討とする | ユーザー合意 |
| D-019 | 2026-05-13 | GoogleログインはSupabase AuthのGoogle providerを使う | ユーザー合意 |
| D-020 | 2026-05-13 | Google API読取に必要なprovider token / provider refresh tokenはサーバ側で安全に保存・更新する | Supabase公式方針を踏まえた設計 |
| D-021 | 2026-05-13 | OAuthスコープは `openid`, `email`, `profile`, `spreadsheets.readonly`, `documents.readonly`, `drive.readonly` を初期値とし、書き込みスコープは持たない | ユーザー合意 |
| D-022 | 2026-05-13 | ローカル環境ではGoogle/Supabase Authの実ログインを使わず、開発用モック認証を使う | ユーザー合意 |
| D-023 | 2026-05-13 | レポート本文生成の既定は固定モデルとし、OpenRouter Auto Router `openrouter/auto` は管理者向けチューニング・比較用オプションとして許可する | OpenRouter公式仕様を踏まえた設計 |
| D-024 | 2026-05-13 | Auto Router利用時はレスポンスの実使用 `model` を必ずジョブに保存する | OpenRouter公式仕様を踏まえた設計 |
| D-025 | 2026-05-13 | `prompt_version` は `monthly-report-vYYYYMMDD.N` 形式で採番する | ユーザー合意 |
| D-026 | 2026-05-13 | MVPでは自動repair loopを実装しない。検証エラーを修正プロンプトへ渡せる設計余地のみ残す | ユーザー合意 |
| D-027 | 2026-05-13 | HTMLエクスポートはPhase 3「MVP体験完成」で必須実装する | ユーザー合意 |
| D-028 | 2026-05-13 | MVPではソース本文・生成物をSupabase Postgresに保存し、サイズが重くなったらSupabase Storageへ逃がす | ユーザー合意 |
| D-029 | 2026-05-13 | Google provider refresh tokenはアプリ側でFernetまたはAES-GCM暗号化し、暗号鍵はCloud Run Secretに置き、Supabaseには暗号文のみ保存する | ユーザー合意 |
| D-030 | 2026-05-13 | DB主キーはUUID、画面/API/ログ表示はprefix付きIDを使う | ユーザー合意 |
| D-031 | 2026-05-13 | MVPの進捗更新はHTMXポーリングに統一し、SSEは後続検討とする | ユーザー合意 |
| D-032 | 2026-05-13 | ジョブキャンセルはMVPに含め、`cancel_requested` / `cancelled` による協調的キャンセルで実装する | ユーザー合意 |
| D-033 | 2026-05-13 | Supabase AuthのOAuth開始・callbackは認証基盤側に分離し、月次レポートAPI定義には含めない | ユーザー合意 |
| D-034 | 2026-05-13 | 差分表示はPhase 3で簡易テキスト差分から開始し、DOM差分は後続検討とする | ユーザー合意 |
| D-035 | 2026-05-13 | MVPの自動テストはPhase 1でpytest + provider mockを必須、Phase 3でPlaywrightを必須ゲートとして導入する | ユーザー合意 |
| D-036 | 2026-05-13 | CIはGitHub Actionsを想定し、Phase 1はpytest、Phase 3でPlaywrightを追加する | ユーザー合意 |
| D-037 | 2026-05-13 | 実案件フィクスチャは氏名・メール・URL・IDを置換し、数値は必要最小限を丸める最低限の匿名化で開始する | ユーザー合意 |
| D-038 | 2026-05-13 | ローカルモックユーザーは互換用に `mock-admin@tomonokai-corp.com` と `mock-user@tomonokai-corp.com` を残す | ユーザー合意 |
| D-061 | 2026-05-17 | ローカル通常UIの既定mockメールは `y-haraguchi@tomonokai-corp.com` とし、保存済みGoogle OAuth credential利用時は `EB_MOCK_USER_ID` にSupabase Auth user UUIDを設定する | 実機検証でmock emailをUUID列へ渡して500になったため |
| D-039 | 2026-05-13 | 管理者向けチューニング設定は管理者ロールのみ公開し、一般ユーザーには固定プリセットのみ表示する | ユーザー合意 |
| D-040 | 2026-05-13 | 保持期間到来時は物理削除を基本とし、集計に必要なメタのみ匿名化して残せる | ユーザー合意 |

## 未決事項

| ID | 状態 | 論点 | 影響文書 |
|---|---|---|---|
| U-001 | 解決 | ソーススナップショットは1年、ジョブメタ・成果物・検証・フィードバックは3年、構造化ログは6か月保持 | `requirements.md`, `data-design.md`, `security-operations.md` |
| U-002 | 解決 | MVPからSupabase Postgresを採用する | `data-design.md`, `development-plan.md` |
| U-003 | 解決 | Cloud Run初期値はtimeout 900秒、1 vCPU、1GiB、concurrency 10、min instances 0、max instances 3。長時間生成はDBジョブ + HTMXポーリング | `security-operations.md` |
| U-004 | 解決 | Supabase Auth Google providerを使い、Google API読取用provider tokenを暗号化保存。スコープはログイン基本 + Sheets/Docs/Drive readonly | `security-operations.md` |
| U-005 | 解決 | 初期モデルは固定モデルを既定とし、`openrouter/auto` は管理者向け比較オプションとして扱う。実使用modelを保存する | `llm-design.md` |
| U-006 | 解決 | `prompt_version` は `monthly-report-vYYYYMMDD.N` 形式。Git SHAやtemplate hashは別途保存する | `llm-design.md`, `development-plan.md` |
| U-007 | 解決 | MVPでは自動repair loopは実装しない。将来の手動/自動repair API余地だけ残す | `functional-spec.md`, `llm-design.md` |
| U-008 | 解決 | 推敲画面は現行HTML全文エディタをベースにする。差分表示の詳細のみ後続設計 | `screen-design.md` |
| U-009 | 解決 | HTMLエクスポートはPhase 3「MVP体験完成」で必須実装する | `workflow-spec.md`, `development-plan.md` |
| U-010 | 解決 | ソース本文・生成物はMVPではSupabase Postgresに保存し、肥大化時にSupabase Storageへ分離する | `data-design.md`, `security-operations.md` |
| U-011 | 解決 | provider refresh tokenはアプリ側でFernetまたはAES-GCM暗号化し、鍵はCloud Run Secret、DBには暗号文のみ保存する | `data-design.md`, `security-operations.md` |
| U-012 | 解決 | DB主キーはUUID、画面/API/ログ表示は `mrj_...` などのprefix付きIDを使う | `api-definition.md`, `data-design.md` |
| U-013 | 解決 | MVPはHTMXポーリングに統一し、SSEは後続検討とする | `api-definition.md`, `screen-design.md`, `workflow-spec.md` |
| U-014 | 解決 | ジョブキャンセルはMVPに含める。実行中リクエストの強制停止ではなく、次stageに進ませない協調的キャンセル | `workflow-spec.md`, `functional-spec.md`, `api-definition.md` |
| U-015 | 解決 | OAuth開始・callbackは認証基盤側へ分離し、月次レポートAPIは認証済みユーザー前提にする | `api-definition.md`, `security-operations.md` |
| U-016 | 解決 | 差分表示はPhase 3で簡易テキスト差分から開始。生成物と最終編集後HTML/Markdownを保存し、DOM差分は後続検討 | `screen-design.md`, `data-design.md`, `development-plan.md` |
| U-017 | 解決 | Phase 1はpytest + provider mock必須。Phase 3でPlaywrightを必ず導入し、エディタ体験完成の品質ゲートにする | `test-plan.md`, `development-plan.md` |
| U-018 | 解決 | CIはGitHub Actions想定。Phase 1はpytest、Phase 3でPlaywrightを追加 | `test-plan.md`, `development-plan.md` |
| U-019 | 解決 | 実案件フィクスチャは最低限の匿名化で開始。氏名・メール・URL・IDを置換し、数値は必要最小限を丸める | `test-plan.md`, `security-operations.md` |
| U-020 | 解決 | モック認証ユーザーは既定 `y-haraguchi@tomonokai-corp.com`、互換用 `mock-admin@tomonokai-corp.com` / `mock-user@tomonokai-corp.com`。Google OAuth credential利用時は `EB_MOCK_USER_ID` でUUIDを分ける | `security-operations.md`, `test-plan.md` |
| U-021 | 解決 | チューニング設定は管理者のみ。一般ユーザーは固定プリセットのみ | `screen-design.md`, `llm-design.md`, `security-operations.md` |
| U-022 | 解決 | 保持期間到来時は物理削除を基本にし、集計メタのみ匿名化して残せる | `data-design.md`, `security-operations.md` |
| U-023 | 解決 | ローカルMVPの `owner_user_id` は暫定値。Supabase Auth後は認証ユーザーIDへ差し替える | `api-definition.md`, `security-operations.md` |
| U-024 | 解決 | 再生成はAPI/保存モデルをMVP内、UIをPhase 3で実装する | `functional-spec.md`, `api-definition.md`, `development-plan.md` |
| U-025 | 解決 | 工房側 `build_messages` と `scripts/monthly_report_draft_openrouter.py` の **`build_prompts` は共通Pythonモジュール化を第一候補として実装する**。静的レシピの `prompts.scope_reminder` 相当のジョブ/APIフィールド名は `prompt_scope_notes` とする。初期投入はレシピ由来 + 手入力可能、householdメタからの自動生成は後続 | [`HANDOFF_STATIC_POC_TUNING.md`](HANDOFF_STATIC_POC_TUNING.md), [`llm-design.md`](llm-design.md), [`api-definition.md`](api-definition.md), [`functional-spec.md`](functional-spec.md) |
| U-026 | 解決 | UI/Auth/RLS/worker/冪等性/Storage/保持削除/監視/プロンプトインジェクション/人間承認の横断方針を正本へ反映する | `agents.md`, `.cursor/rules/monthly-report-north-star.mdc`, `api-definition.md`, `security-operations.md`, `development-plan.md` |

## 参考扱いの文書

| 文書 | 扱い |
|---|---|
| `docs/project/レポート自動化システム_要件定義.md` | 参考。移行計画書と矛盾する場合は移行計画書を優先 |

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-13 | 初版作成 |
| 2026-05-14 | D-041〜D-045、U-023〜U-024を追加し、リージョン、失敗詳細保存、ローカルowner_user_id、再生成API/UI方針を反映 |
| 2026-05-14 | D-046、U-025 を追加。[`HANDOFF_STATIC_POC_TUNING.md`](HANDOFF_STATIC_POC_TUNING.md) を静的 POC チューニングの他エージェント向け合流入り口とする |
| 2026-05-14 | U-025に第一候補として共通Pythonモジュール化を追記し、`prompt_scope_notes` を候補フィールドとして整理 |
| 2026-05-14 | D-047を追加し、`prompt_scope_notes` を正式フィールド名として決定。U-025を一部解決へ更新 |
| 2026-05-14 | D-048を追加し、`prompt_scope_notes` の初期投入方針を決定。U-025を解決へ更新 |
| 2026-05-14 | D-049を追加し、DB-backed worker claim境界を決定事項として反映 |
| 2026-05-16 | D-050〜D-058、U-026を追加し、HTML断片UI、Cookie+CSRF、RLS主境界、worker lease、冪等性、Storage、保持削除、監視、LLM入力安全、人間承認ゲートを反映 |
| 2026-05-16 | D-059（Supabase JWT は ES256/RS256 JWKS 検証を本流とし HS256 はテスト互換用に残す）、D-060（ローカル Supabase config.toml の Google provider 有効化と enable_signup=true、ドメイン制限は API 側）を追加 |
| 2026-05-17 | D-009を再確認し、MVPは本番のみへ戻した。D-062は本番ポータル合流時のstaging / production分離方針として整理 |
| 2026-05-17 | D-063を追加し、Tailwind CSS + DaisyUI主軸、Flowbite保留、業務画面table/section中心のUIコンポーネント方針を記録 |
| 2026-05-18 | D-067を追加し、D-009/D-062を廃止扱いに変更。staging / productionの環境分離を設計対象に戻したうえで、production昇格の完了条件はD-068で再整理 |
| 2026-05-18 | D-068を追加し、今回プロジェクトの完了条件をレポート工房MVPのstaging環境動作確認へ固定。production昇格と指導管理ポータル統合は後続スコープへ分離 |
| 2026-05-19 | D-069を追加し、P3-12の監査ログに加えて通常UIから到達できる direct workflow start の監査も direct store とし、通常ユーザーartifact writeは RLS write store とする境界を明文化。あわせて P3-12 完了、P1-16 direct workflow audit、P3-14 の self-contained Playwright 連続UI確認完了を `development-plan.md` と整合 |
| 2026-05-19 | D-070を追加し、通常JSON API の validation 保存を user-JWT Supabase client 優先の RLS write store へ寄せ、idempotency 記録のみ direct store に残す混成境界を明文化。`api-definition.md` / `development-plan.md` と整合 |
| 2026-05-19 | D-071を追加し、`llm_call_logs` を server-owned telemetry として分類。`source-summary` HTML action では artifact は RLS write、LLM call記録は direct store のまま維持する境界を focused test と `api-definition.md` / `development-plan.md` に反映 |
