# 機能仕様書

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツールの機能仕様
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- 関連文書: `requirements.md`, `workflow-spec.md`, `screen-design.md`, `api-definition.md`
- 最終更新: 2026-05-17

## 横断方針

- 通常画面操作はJinja2 + HTMXのHTMLページ/HTML断片を返す。JSON APIはworker、E2E、管理、将来連携用に残す。
- エラー時も対象領域へ差し込めるHTML断片を返し、通常UIでJSONからDOMを組み立てない。
- 送付/エクスポート前には人間承認ゲートを必須にし、生成成功・検証OK・編集保存済み・承認済み・送付済みを別状態として扱う。

## 機能一覧

| ID | 機能 | MVP | 対応要件 |
|---|---|---|---|
| F-01 | ログイン・ドメイン制限 | 必須 | FR-1, FR-2 |
| F-02 | ソース指定 | 必須 | FR-3 |
| F-03 | Google API取得 | 必須 | FR-4 |
| F-04 | ソース確認 | 必須 | FR-5 |
| F-05 | ジョブ作成 | 必須 | FR-6, FR-7 |
| F-06 | 生成パイプライン | 必須 | FR-8, FR-9 |
| F-07 | 決定的バリデーション | 必須 | FR-10, FR-11 |
| F-08 | プレビュー・推敲 | 必須 | FR-13 |
| F-09 | フィードバック保存 | 必須 | FR-12 |
| F-10 | 再生成 | 後続優先 | FR-14 |
| F-11 | 管理者チューニング設定 | 後続優先 | FR-15 |
| F-12 | ジョブキャンセル | 必須 | FR-7 |
| F-13 | 送付前承認 | 必須 | FR-13 |
| F-14 | HTMLエクスポート | 必須 | FR-13 |
| F-15 | 手動送付用distribution package | 後続優先 | FR-13 |
| F-16 | 既存全文エディタ連携 | 後続優先 | FR-13 |

## F-01 ログイン・ドメイン制限

- Googleアカウントでログインする。
- メールドメインまたはIDトークンの `hd` が `tomonokai-corp.com` であることを確認する。
- 条件を満たさない場合は403画面を表示する。

## F-02 ソース指定

ユーザーは新規ジョブ作成画面で以下を入力する。

| 項目 | 必須 | 備考 |
|---|---:|---|
| 対象月 | 必須 | `YYYY-MM` |
| 対象世帯または内部識別子 | 必須 | MVPでは自由入力または既存registry参照 |
| Spreadsheet URL/ID | 必須 | 学習計画表など |
| Docs URL/ID | 任意 | 教師MTG、家庭面談など |
| テンプレート | 必須 | 初期値はPattern B |
| メモ | 任意 | 人手補足 |
| ソースプリセット | 任意 | 静的POCの `source_preset` 相当。例: `pattern_b_gws_sl` |
| スコープ補足 | 任意 | 複数生徒MTGで対象を限定する `prompt_scope_notes`。静的POCの `prompts.scope_reminder` 相当 |
| 構造参考 | 任意 | ideal HTMLまたは構造HTML。`structure_from_ideal` 相当 |
| 出力形式 | 必須 | `draft_markdown` または `draft_html`。初期MVPはMarkdown優先 |

## F-03 Google API取得

- サーバはユーザーOAuthトークンでSheets / Docs / Drive APIを呼び出す。
- 取得結果はソーススナップショットとして保存する。
- 取得に失敗したソースは、失敗理由とともに保存する。

## F-04 ソース確認

取得後、以下を表示する。

- ソース名
- 種別
- URLまたはdocument_id
- 取得日時
- サイズ
- hash
- トランケーション有無
- エラー有無

通常UIでは、保存済みソースに対して軽量LLMの取得内容サマリーを実行できる。要約は配布本文ではなく確認用artifactとして保存し、対象生徒・対象月・科目・資料種別・不足/ズレの可能性を本文生成前に確認するために使う。要約結果は `source_summary_markdown` として保存し、呼び出しメタは `llm_call_logs.prompt_kind=source_summary` に残す。

## F-05 ジョブ作成

- 生成ボタン押下時、ユーザーの実行中ジョブ数を確認する。
- 実行中が3件以上なら作成せず、429相当のメッセージを表示する。
- 作成できる場合は `queued` 状態で保存する。

## F-06 生成パイプライン

処理は以下の関数またはサービス境界に分ける。

1. `fetch_sources`
2. `bundle_sources`
3. `build_messages`
4. `call_llm`
5. `validate_draft`
6. `persist_artifacts`

各段階で `job_id`, `stage`, `started_at`, `finished_at`, `duration_ms`, `error_type` を記録する。

`build_messages` は [llm-design.md](llm-design.md) の塊順を正とし、静的POCの `build_prompts` と入力順・意味を揃える。特に複数生徒MTGでは、対象氏名・教科・別姓段落除外の補足を `prompt_scope_notes` として渡せること。

## F-07 決定的バリデーション

最低限の検証は以下。

- 必須見出しが存在する。第一弾ではテンプレートから抽出した `## 01...` 形式の見出し欠落を `required_headings` として検出する。
- 禁止語・禁止表現が含まれない。第一弾では `担当CA`, `教師 MTG`, `NotebookLM` を `forbidden_terms` として検出する。
- 星5行の原文一致が守られる。
- `DATA_CONTRACT_05_学習の進捗.md` で定義された表示規約に反しない。
- 生成Markdownが空でない。
- `prompt_scope_notes` で対象外として明示された生徒・教科が家庭向けdraftへ混入していない。第一弾では `対象外...様` の呼称混入を `multistudent_scope_exclusion` として検出する。
- Google Docs/Sheets本文に含まれる命令文や内部メモが、本文規約・対象範囲・送付禁止情報の扱いを上書きしていない。

MVPでは検証エラーを自動repair loopへ送らない。検証エラーはユーザーに表示し、人手修正・フィードバック・再生成判断の材料にする。将来、検証エラーと該当箇所のみを修正プロンプトへ渡すAPIを追加できる設計にする。

## F-08 プレビュー・推敲

- Markdown草稿をプレビュー表示する。
- 検証エラーと警告を同じ画面または隣接パネルに表示する。
- MVPではMarkdownエディタを優先し、WYSIWYGは後続でよい。
- 最終編集後Markdownを保存できる設計にする。
- 通常UIの第一弾では、ジョブ詳細に左プレビュー/右編集Markdownの2ペインを置く。
- プレビューは `final_markdown` を優先し、存在しない場合のみ `draft_markdown` を表示する。
- 編集Markdown欄は最新preview artifactでprefillし、入力時に未保存変更を表示する。
- 保存成功後は `final_markdown` artifactを作成し、preview fragmentを更新する。フォーム側に `base_content_hash` がある場合、最新preview artifact hashと不一致なら409相当のHTML error fragmentで保存を拒否し、同じIdempotency-Key再送は初回結果を優先する。
- 再生成UIは同一ソース/テンプレート/プロンプト/モデルメタを継承した新しいqueued jobを作成し、新ジョブ詳細リンク付きのHTML断片を返して比較UIへ接続する。
- 承認、export、HTML source、distributionなど入力フォームを含むpanelは定期pollingせず、編集保存・承認・export成功時の `monthly-report-refresh` イベントで更新する。進捗statusはHTMX pollingを維持する。
- 共通HTMX error bannerは `htmx:responseError` / `htmx:sendError` / `htmx:timeout` を拾い、画面下部に通信・処理失敗を表示する。
- `running` のstatus fragmentでは、ページを閉じても処理が継続すること、進捗panelが自動更新されること、再読み込み後も状態が復元されることを表示する。後段stageで長時間heartbeatがない場合は、後段stageを自動再claimしない運用に合わせてworker runbook確認を促す。

## F-09 フィードバック保存

ユーザーは以下を保存できる。

- 問題カテゴリ
- 自由記述
- 最終編集後Markdown
- 再生成したいかどうか

## F-13 送付前承認

- 生成成功、検証OK、編集保存済み、承認済み、送付/エクスポート済みを分けて表示する。
- 検証エラーまたは未承認の状態では、送付エクスポートを実行できない。
- 承認操作は監査ログに残す。
- 承認対象は最新の配布面artifact hashとする。`final_markdown` が存在する場合はそれを優先し、存在しない場合のみ最新 `draft_markdown` を対象にできる。
- 承認後に新しい `final_markdown` / `draft_markdown` / validation errorが追加された場合、既存承認は表示上「再承認が必要」へ戻す。
- 通常UIでは `GET/POST /monthly-reports/jobs/{job_id}/fragments/approval` のHTML断片で承認状態、ブロック理由、フォーム、成功/失敗を表示する。
- `POST /monthly-reports/jobs/{job_id}/fragments/approval` はCSRF、RLS read preflight、Idempotency-Key、対象hashの一致を必須にする。
- MVPの承認取り消しは管理者運用または再編集による自動失効に寄せ、一般ユーザー向けの明示的な取り消しボタンは後続とする。

### F-13 受け入れ条件

- `succeeded` ではない、validation errorがある、配布面artifactがない、対象hashが古い場合は承認できない。
- 承認成功後のfragmentには承認者、承認日時、対象artifact hash、承認コメントが表示される。
- 二重送信は同一Idempotency-Keyで同じ承認結果を返し、監査ログ/承認レコードを重複作成しない。

## F-14 HTMLエクスポート

- HTMLエクスポートは承認済みの配布面artifactから作成する。未承認、validation errorあり、承認対象hashと最新artifact hashが一致しない場合は作成できない。
- 通常UIでは `GET/POST /monthly-reports/jobs/{job_id}/fragments/export` のHTML断片でエクスポート可能性、最新export artifact、作成結果を表示する。
- export artifactには、本文HTML、元artifact hash、approval_id、template_hash、prompt_version、source_bundle_hash、app_versionを紐づける。
- HTMLは家庭向け配布面として独立表示できる最小構造にし、管理メモ、内部エラー、プロンプト、APIキー、OAuth token、service role情報を含めない。
- ダウンロード/プレビュー導線はHTML fragment内のリンクまたはボタンとして表示する。通常UIからJSONを取得してDOMを組み立てない。

### F-14 受け入れ条件

- 未承認ジョブのexport POSTはHTML error fragmentを返し、export artifactを作成しない。
- 承認済みジョブのexport POSTは `export_html` artifactを作成し、export fragmentにartifact hashと作成日時を表示する。
- 同一Idempotency-Keyの再送では同じexport artifactを返し、HTMLを重複作成しない。
- export fragmentとdetail pageに `/api/monthly-reports/*` をDOM更新目的で呼ぶ記述がない。

## F-10 再生成

- 同一ソーススナップショットを使い、prompt_versionまたはmodelだけを変えて再実行できる。
- APIと保存モデルはMVP内で用意する。
- 通常UI第一弾では、詳細画面の再生成フォームから新しいqueued jobを作成し、作成通知、status fragment、新ジョブ詳細リンクを返す。
- 管理者は再生成時に `prompt_version`, `model_report`, `model_light` をoverrideできる。一般ユーザーは元ジョブのメタを継承し、フォーム値を直接送られてもoverrideしない。
- 通常UI第一弾では、再生成元/再生成先の `prompt_version`, `template_key/hash`, `model_report`, `model_light`, `resolved_model_report`, `source_bundle_hash`, `app_version`, `prompt_scope_notes` を `rerun-comparison` fragmentで比較表示する。
- `rerun-comparison` fragmentでは、同一世帯/同一ユーザーの比較候補をdatalistとリンクで表示し、ジョブID手入力だけに依存しない。
- `rerun-diff` fragmentでは、再生成元/比較先ジョブの最新 `final_markdown` または `draft_markdown` 同士を行単位で比較する。
- 次段階では、比較結果の見た目調整とライブE2Eへ接続する。

## F-11 管理者チューニング設定

- 管理者は検証・比較用途に限り、モデル、テンプレート版、プロンプト版を指定できる。
- 一般ユーザーには固定プリセットのみ表示する。
- Auto Router等を利用した場合は、要求モデルと実使用モデルを分けて保存する。
- 通常UI第一弾では、新規ジョブ作成画面と再生成フォームでadminに限り `prompt_version` / `model_report` / `model_light` を指定できる。一般ユーザーには入力欄を表示せず、フォーム値を直接送られた場合も保存しない。

## F-15 手動送付用distribution package

- 実メール送信はMVPでは行わず、承認済みHTML exportを `distribution_package` artifactとして固定する。
- 通常UIでは `GET/POST /monthly-reports/jobs/{job_id}/fragments/distribution` のHTML断片で状態、ブロック理由、固定結果を表示する。
- 同一Idempotency-Keyの再送では同じdistribution packageを返し、重複artifactを作らない。

## F-16 既存全文エディタ連携

- `GET /monthly-reports/legacy-full-editor` で既存 `monthly_report_full_editor.html` を同一オリジンから開ける。
- `GET /monthly-reports/jobs/{job_id}/legacy-full-editor` は最新 `export_html` artifactを既存全文エディタのlocalStorageキーへ投入してから互換routeへ遷移するbridgeを返す。
- 既存エディタで編集した後の工房再取込は後続とする。

## F-12 ジョブキャンセル

- ユーザーは自分の `queued` / `running` ジョブをキャンセルできる。
- 管理者は任意のジョブをキャンセルできる。
- キャンセルは実行中HTTPリクエストの強制停止ではなく、`cancel_requested` に状態更新し、実行中stageの終了後に次stageへ進ませない協調的キャンセルとする。
- 完了済みの成果物やログは監査・調査のため保持する。

## 未決事項

世帯識別子はMVPでは自由入力または既存registry参照で開始し、ポータル統合時に正式マスタへ寄せる。差分表示はPhase 3で簡易テキスト差分から開始する。

なし。`prompt_scope_notes` は正式名称として決定済み。初期投入はレシピ由来 + 手入力可能とし、householdメタからの自動生成は後続に回す。

## 受け入れ条件

- MVP必須機能がAPIと画面に対応している。
- ジョブ状態と検証結果がユーザーに見える。
- 失敗したジョブを後から調査できる保存項目がある。

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-13 | 初版作成 |
| 2026-05-14 | FR対応の取り違えを修正し、F-11 管理者チューニング設定を追加 |
| 2026-05-14 | HANDOFF_STATIC_POC_TUNING.md を踏まえ、source_preset / prompt_scope_notes / 構造参考 / artifact のジョブ入力を追加 |
| 2026-05-14 | `prompt_scope_notes` を正式フィールド名として反映 |
| 2026-05-14 | `prompt_scope_notes` の初期投入方針をレシピ由来 + 手入力可能に決定 |
| 2026-05-14 | `multistudent_scope_exclusion` 第一弾を決定的バリデーションへ追加 |
| 2026-05-14 | `required_headings` 第一弾を決定的バリデーションへ追加 |
| 2026-05-14 | `forbidden_terms` 第一弾を決定的バリデーションへ追加 |
| 2026-05-17 | P3-03 admin tuning、P3-02/P3-03 rerun comparison/rerun diff、P3-11 legacy editor bridge、P3-13 refresh/error/conflict/running復帰案内、distribution packageを反映 |
