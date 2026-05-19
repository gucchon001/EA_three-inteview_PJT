# 画面設計書

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツールの画面設計
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- 関連文書: `docs/web-app/screen-design.md`, `DESIGN.md`, `functional-spec.md`, `api-definition.md`
- 最終更新: 2026-05-13

## 基本方針

- FastAPI + Jinja2 + HTMXで構築する。
- 通常画面操作はHTMLページ/HTML断片を返す。`/api/monthly-reports/*` のJSON APIはworker、E2E、管理スクリプト、将来連携用に残し、通常UIからDOM更新目的で直接叩かない。
- CSR専用SPAにはしない。
- MVPは月次レポート生成ツール単体で動かし、ポータルのグローバルナビ・サイドバーには依存しない。
- 将来の既存ポータル統合を見越し、ルータ・テンプレート・サービスを `monthly_reports` 境界で分ける。
- 進捗、検証結果、プレビュー差し替えはHTMX fragmentで行う。
- エラー時も対象領域へ差し込めるalert/status断片を返す。JSONを受けてフロントJSでDOMを組み立てる設計にはしない。
- 画面は業務ツールとして密度高く、静かでスキャンしやすい構成にする。
- 推敲・プレビュー画面は、現行 `docs/samples/monthly-reports/tools/monthly_report_full_editor.html` のHTML全文エディタをベースにする。
- 現行エディタの送付エクスポート、ファイル保存、ファイルから開く、HTMLソース直接編集はMVP内の後続必須機能として扱う。

## UIコンポーネント方針

レポート工房のUIは、Tailwind CSS + DaisyUIを主軸にする。DaisyUIはCSSクラス中心でJinja2 partialとHTMX fragmentに載せやすいため、MVPの標準コンポーネント層とする。Alpine.jsはモーダル、タブ、トーストなどHTMXだけでは扱いにくい局所状態に限定する。

FlowbiteはMVPでは標準依存にしない。DaisyUIで不足する高度なコンポーネントが出た場合に、対象画面・JS依存・アクセシビリティ・HTMXとの責務境界を確認してから個別採用を判断する。

### 採用するDaisyUIパターン

| 用途 | 推奨コンポーネント | 使用箇所 |
|---|---|---|
| ジョブ一覧・履歴 | `table`, `badge`, `progress`, `dropdown` | MR-S01、管理者向け履歴 |
| 新規ジョブ作成 | `form-control`, `input`, `select`, `textarea`, `btn`, `alert` | MR-S02 |
| ソース確認 | `collapse`, `badge`, `alert`, `table` | MR-S03、MR-F07〜F09 |
| 進捗表示 | `steps`, `progress`, `loading`, `alert` | MR-S04、MR-F01 |
| 生成結果プレビュー | 通常section + `prose` | MR-S04、MR-S05。本文はカードに閉じ込めすぎない |
| 編集・推敲 | `textarea`, `tabs`, `join`, `divider`, `btn` | MR-S05、P3-01/P3-02 |
| 検証結果 | `alert`, `badge`, `collapse` | MR-F03 |
| 承認ゲート | `modal`, `checkbox`, `steps`, `alert` | P3-12 |
| チューニング設定 | `table`, `stats`, `badge`, `select` | MR-S06 |
| フィードバック | `rating`, `textarea`, `alert` | MR-F04 |

### レイアウト制約

- 業務画面はtable/section中心にし、カードをページ全体の入れ子構造として多用しない。
- 個別ジョブ、検証項目、フィードバックなど「繰り返し単位」には `card` を使ってよい。ただし `card w-96` のような固定幅は避け、親grid/sectionに合わせる。
- 主要画面の上部は、見出し、主要CTA、状態badge、最終更新時刻を同じ視線上に置く。
- 長文プレビューは `prose max-w-none` 相当の読み物領域として扱い、編集フォーム・検証結果・承認ゲートとは視覚的に分ける。
- ボタンには状態を持たせる。生成中は `loading`、失敗時は `btn-error` または `alert-error`、注意は `alert-warning` を使う。
- HTMX actionの失敗レスポンスもDaisyUI `alert` 断片で返し、JSONをフロントJSで整形しない。

## MVP単体シェル

MVPの月次レポートビューは、現行 `monthly_report_full_editor.html` 相当の編集領域を主画面にし、左側に月次レポート専用サイドバーを置く。ポータルモックの `EB 指導管理` ヘッダーやサイドバーは表示しない。

### サイドバー項目

| グループ | 項目 |
|---|---|
| 作業 | レポートビュー、新規読み込み、ジョブ一覧、生成ステータス |
| チェック | 検証結果、ソース確認、簡易差分 |
| 出力・設定 | HTMLエクスポート、送付エクスポート、チューニング |

## URL一覧

| ID | 画面 | URL案 | MVP | 備考 |
|---|---|---|---|---|
| MR-S00 | 単体MVPトップ | `/monthly-reports` | 必須 | ポータル統合前のレポート工房入口 |
| MR-S01 | ジョブ一覧 | `/monthly-reports/jobs` | 必須 | 対象月、状態、作成者で絞り込み |
| MR-S02 | 新規ジョブ作成 | `/monthly-reports/jobs/new` | 必須 | メタ入力とソース指定 |
| MR-S03 | ソース確認 | `/monthly-reports/jobs/{job_id}/sources` | 必須 | 取得結果確認 |
| MR-S04 | ジョブ詳細 | `/monthly-reports/jobs/{job_id}` | 必須 | 状態、成果物、検証結果 |
| MR-S05 | プレビュー・推敲 | `/monthly-reports/jobs/{job_id}/edit` | 必須 | HTML/配布面優先・Markdown補助 |
| MR-S06 | チューニング設定 | `/monthly-reports/settings` | 後続 | 管理者のみ |
| MR-S07 | フィードバック一覧 | `/monthly-reports/feedback` | 後続 | 改善サイクル用 |

## MR-S00 単体MVPトップ

MVPではポータル統合前に、月次レポート生成ツール単体で業務フローを検証する。トップページはポータルのサイドバーに依存せず、以下を表示する。

### 表示要素

- プロダクト名: 月次レポート生成ツール / レポート工房
- 主要CTA: 新規生成、ジョブ一覧
- 生成フロー: ソース指定、取得確認、生成、検証・推敲
- 実行中ジョブ、検証エラー、平均生成時間などの概要
- 最近の生成ジョブ

### 操作

- 新規ジョブ作成へ遷移
- 既存ジョブ一覧へ遷移
- デモジョブまたは最近のジョブ詳細へ遷移

## MR-S01 ジョブ一覧

### 表示要素

- ページタイトル
- 新規作成ボタン
- フィルタ: 対象月、状態、自分のジョブ、エラーあり
- 一覧列: 対象月、世帯、状態、作成者、モデル、prompt_version、検証結果、作成日時、最終更新

### 操作

- 新規ジョブ作成へ遷移
- ジョブ詳細へ遷移
- 失敗ジョブの原因を展開表示

## MR-S02 新規ジョブ作成

### 入力

- 対象月
- 対象世帯
- Spreadsheet URL/ID
- Docs URL/ID（複数可）
- テンプレート
- メモ

### 操作

- ソース取得
- 下書き保存
- キャンセル

## MR-S03 ソース確認

### 表示

- ソース一覧
- 取得成功/失敗
- サイズ
- hash
- トランケーション
- 取得エラー

### 操作

- Google Docs/Sheets取得/再取得
- 生成開始
- ソース追加

## MR-S04 ジョブ詳細

### 表示

- ジョブ状態
- stage別進捗
- LLMメタ
- 成果物一覧
- 検証エラー・警告
- フィードバック入力

### HTMX

- `GET /monthly-reports/jobs/{job_id}/fragments/status`
- `GET /monthly-reports/jobs/{job_id}/fragments/validation`
- `GET /monthly-reports/jobs/{job_id}/fragments/artifacts`
- `POST /monthly-reports/jobs`
- `POST /monthly-reports/jobs/{job_id}/run`
- `POST /monthly-reports/jobs/{job_id}/rerun`
- `POST /monthly-reports/jobs/{job_id}/cancel`

## MR-S05 プレビュー・推敲

### レイアウト

| 領域 | 内容 |
|---|---|
| 上部 | ジョブ状態、検証結果サマリ、保存状態 |
| 中央 | 左に配布面プレビュー、右に承認/HTML編集/エクスポートへの進行ガイド |
| 補助領域 | `draft_markdown` / `final_markdown` を中間成果物として確認・保存・差分比較 |
| 下部 | HTMLソース直接編集、保存、送付エクスポート、フィードバック |
| サイドバー連動パネル | 検証結果、ソース確認、簡易差分、チューニングを本文下にアンカー表示 |

### 操作

- 配布面プレビューの確認
- 承認、HTMLソース編集、HTMLエクスポート、送付用固定への進行
- 生成Markdownの保存。保存後は `final_markdown` artifactとして扱い、承認対象は `final_markdown` を優先する
- `draft_markdown` / `final_markdown` の差分表示
- 生成ドラフトと保存済み本文の表示切替。MVP第一弾では `final_markdown` を優先表示し、なければ `draft_markdown` を表示する
- HTMLソース直接編集
- 簡易テキスト差分表示
- 検証再実行
- フィードバック保存
- ファイル保存・ファイルから開く
- 送付エクスポート
- standalone MVPモックでは、左サイドバーの検証結果・ソース確認・簡易差分・チューニングをバックエンド依存なしのアンカーパネルとして表示する。

### P3-01/P3-02 第一弾実装

2026-05-17時点では、ジョブ詳細内に「プレビュー / 編集」2ペインを追加済み。左は `GET /fragments/preview` のHTML断片、右は配布面を確定するための進行ガイドとし、Markdown textareaは「生成Markdown（中間成果物）」の補助領域へ降ろす。`draft_markdown` はLLM生成の安定した中間成果物として保持し、保存すると `POST /fragments/edited-markdown` により `final_markdown` artifactを保存する。通常運用ユーザーはMarkdown手編集を前提にせず、主に配布面プレビュー、承認、HTMLソース編集、HTMLエクスポート、送付用固定を辿る。再生成は既存 `POST /monthly-reports/jobs/{job_id}/rerun` で新しいqueued jobを作り、作成通知、status fragment、新ジョブ詳細リンクを返す。`rerun-comparison` fragmentでは比較先ジョブIDを指定し、prompt/model/template/source hash/app versionを横並びで確認する。同一世帯/同一ユーザーの比較候補はdatalistとリンクで表示し、手入力だけに依存しない。`rerun-diff` fragmentでは元/比較先ジョブの最新Markdown同士を行単位で比較する。HTMLソース編集パネルには既存 `monthly_report_full_editor.html` を開く互換リンクと、最新 `export_html` artifactを既存エディタのlocalStorageへ投入して開くbridge導線を置く。既存エディタで編集した後の工房再取込は後続。

## MR-S05A 承認・HTMLエクスポート

P3-06/P3-12の最小導線は、ジョブ詳細内の独立したHTML fragmentとして追加する。通常UIは `/monthly-reports/*` のJinja2 + HTMXを維持し、承認状態やエクスポート結果をJSONからDOM構築しない。

### 表示

| 領域 | 内容 |
|---|---|
| 承認ステップ | 生成成功、検証OK、編集保存済み、承認済み、エクスポート済みを `steps` で表示 |
| 送付前チェック | 対象月、世帯、最新artifact種別、最終編集hash、validation error/warning件数 |
| 承認フォーム | 確認チェックボックス、承認コメント、承認者、承認日時 |
| HTMLエクスポート | 最終編集後Markdown優先、なければdraft MarkdownをHTML化した成果物のダウンロード/プレビュー導線 |
| ブロック理由 | 未生成、検証errorあり、編集未保存、未承認、古い承認hashなど |

### 操作

- 承認状態の表示更新
- 送付前チェックの再読込
- 人間承認の保存
- 承認取り消しはMVPでは管理者のみ後続。一般ユーザーは新しい編集保存後に再承認する。
- HTMLエクスポート作成
- HTMLエクスポート成果物のプレビュー/ダウンロード

### HTMX

- `GET /monthly-reports/jobs/{job_id}/fragments/approval` は承認ステップ、ブロック理由、承認フォームを返す。
- `POST /monthly-reports/jobs/{job_id}/fragments/approval` はCSRF、RLS read preflight、Idempotency-Keyを通し、承認済みfragmentを返す。
- `GET /monthly-reports/jobs/{job_id}/fragments/export` はエクスポート可能性、最新export artifact、作成ボタンを返す。
- `POST /monthly-reports/jobs/{job_id}/fragments/export` は承認済みかつ承認対象hashが最新の場合だけHTML export artifactを作成し、export fragmentを返す。
- エラー時は対象panelに差し込めるDaisyUI `alert` 断片を返す。

### 受け入れ条件

- 未承認またはvalidation errorありのジョブでは、HTMLエクスポート作成ボタンがdisabledになり、POSTしても403/422相当のHTML error fragmentを返す。
- 承認は最新の `final_markdown` artifact hashを対象にする。`final_markdown` がない場合は最新 `draft_markdown` hashを対象にできるが、UIに「編集保存なし」と表示する。
- 承認後に新しい `final_markdown` または `draft_markdown` が保存された場合、承認ステップは「再承認が必要」と表示する。
- export artifactには `approved_artifact_hash`、`approval_id`、`template_hash`、`prompt_version`、`source_bundle_hash` を表示できる。
- 通常UIのHTMLには `/api/monthly-reports/*` をDOM更新目的で呼ぶ記述を含めない。

## MR-S06 チューニング設定

管理者のみアクセスできる。一般ユーザーには表示しない。

### 表示・操作

- report modelの固定プリセット選択
- light modelの固定プリセット選択
- `openrouter/auto` の比較利用
- `prompt_version` の選択
- テンプレート版の選択
- 設定変更履歴の確認
- 通常UI第一弾では、新規ジョブ作成画面内にadmin限定の「管理者チューニング」領域を置き、`prompt_version`、本文モデル、軽量モデルを指定する。一般ユーザーには同領域を表示しない。
- 詳細画面の再生成フォームにもadmin限定の「再生成チューニング」領域を置き、元ジョブのprompt/modelメタを初期値として表示する。一般ユーザーには表示しない。

## HTMX fragment一覧

2026-05-17時点の第一弾実装では、ジョブ一覧・新規・作成・詳細・ソース確認/手動保存/Google取得・取得内容要約・生成開始・モック生成・OpenRouter生成・status/preview/validation/feedback、編集保存、再生成、承認、HTMLエクスポート、HTMLソース編集、HTMLダウンロード、手動送付用distribution package、rerun comparison、rerun diff、既存全文エディタbridgeがHTMLページ/HTML断片で動く。キャンセル、差分UI、比較候補datalist、running復帰案内も最小導線まで入り、残りは送付先管理、ファイルから開く、既存エディタ編集後の工房再取込とする。

| ID | GET/POST | 用途 |
|---|---|---|
| MR-F01 | `GET /monthly-reports/jobs/{job_id}/fragments/status` | 進捗ポーリング |
| MR-F02 | `GET /monthly-reports/jobs/{job_id}/fragments/preview` | Markdown/HTMLプレビュー |
| MR-F03 | `GET /monthly-reports/jobs/{job_id}/fragments/validation` | 検証結果 |
| MR-F04 | `POST /monthly-reports/jobs/{job_id}/fragments/feedback` | フィードバック保存後の差し替え |
| MR-F05 | `POST /monthly-reports/jobs` | ジョブ作成後のジョブカード/遷移指示 |
| MR-F06 | `POST /monthly-reports/jobs/{job_id}/run` | 生成開始/モック生成/OpenRouter生成後の進捗パネル/エラー |
| MR-F07 | `GET /monthly-reports/jobs/{job_id}/fragments/sources` | ソース確認 |
| MR-F08 | `POST /monthly-reports/jobs/{job_id}/fragments/sources` | 手動ソース保存後の差し替え |
| MR-F09 | `POST /monthly-reports/jobs/{job_id}/fragments/google-sources` | Google Docs/Sheets取得後のソース差し替え |
| MR-F10 | `GET /monthly-reports/jobs/{job_id}/fragments/sheet-selector` | Spreadsheet IDからシート名を取得し、基本情報/学習計画表シート選択を表示 |
| MR-F11 | `POST /monthly-reports/jobs/{job_id}/fragments/source-summary` | 保存済みソースをlight modelで要約し、取得内容のズレ/不足確認を表示 |
| MR-F12 | `POST /monthly-reports/jobs/{job_id}/rerun` | 再生成ジョブの作成通知、新ジョブ詳細リンク、進捗 |
| MR-F13 | `POST /monthly-reports/jobs/{job_id}/cancel` | キャンセル要求後の状態 |
| MR-F14 | `GET /monthly-reports/jobs/{job_id}/fragments/approval` | 承認ステップ/送付前チェック |
| MR-F15 | `POST /monthly-reports/jobs/{job_id}/fragments/approval` | 人間承認保存後の承認panel |
| MR-F16 | `GET /monthly-reports/jobs/{job_id}/fragments/export` | HTMLエクスポート状態/成果物 |
| MR-F17 | `POST /monthly-reports/jobs/{job_id}/fragments/export` | HTMLエクスポート作成後のexport panel |
| MR-F18 | `POST /monthly-reports/jobs/{job_id}/fragments/edited-markdown` | 編集後Markdownを `final_markdown` artifactとして保存し、stale base hash時は409相当のHTML errorを返す |
| MR-F19 | `GET /monthly-reports/jobs/{job_id}/fragments/diff` | draft/finalの簡易テキスト差分 |
| MR-F20 | `GET /monthly-reports/jobs/{job_id}/fragments/html-source` | 最新 `export_html` のHTMLソース編集panel |
| MR-F21 | `POST /monthly-reports/jobs/{job_id}/fragments/html-source` | 編集済みHTMLを新しい `export_html` artifactとして保存 |
| MR-F22 | `GET /monthly-reports/jobs/{job_id}/fragments/distribution` | 手動送付用distribution package状態 |
| MR-F23 | `POST /monthly-reports/jobs/{job_id}/fragments/distribution` | 承認済みHTML exportを `distribution_package` artifactとして固定 |
| MR-F24 | `GET /monthly-reports/jobs/{job_id}/fragments/rerun-comparison` | 元ジョブと比較先ジョブのprompt/model/template/source hash/app versionを横並び表示。同一世帯/同一ユーザーの比較候補をdatalistで表示 |
| MR-F25 | `GET /monthly-reports/legacy-full-editor` | 既存全文エディタを同一オリジンで開く互換route |
| MR-F26 | `GET /monthly-reports/jobs/{job_id}/legacy-full-editor` | 最新 `export_html` を既存全文エディタのlocalStorageへ投入して開くbridge |
| MR-F27 | `GET /monthly-reports/jobs/{job_id}/fragments/rerun-diff` | 元ジョブと比較先ジョブの最新Markdown本文を行単位で比較 |

Google Sheets通常UIでは範囲指定を不要にし、既定で `student` と `lesson plan` の使用範囲全体を取得する。シート名が異なる場合は `sheet-selector` fragmentで取得したシート名から、基本情報シートと学習計画表シートを選択する。
文字起こし・Docs・Sheetsを保存した後は、`source-summary` fragmentで取得内容を軽くLLM要約し、対象生徒、期間、科目、取得漏れ、別生徒混入の可能性を本文生成前に確認できるようにする。

MVPではSSEを使わず、進捗状態はHTMXポーリングで扱う。承認、export、HTML source、distributionなど入力フォームを含むpanelは定期pollingせず、編集保存・承認・export成功時の `monthly-report-refresh` イベントで更新して入力途中の内容を消さない。

## 状態表示

| 状態 | UI表現 |
|---|---|
| `queued` | 待機中 |
| `running` | stage名と進捗を表示。ページを閉じても処理継続、自動更新、再読み込み後の状態復元を案内。後段stageで長時間heartbeatがない場合はworker runbook確認を促す |
| `succeeded` | プレビューと検証結果を表示 |
| `failed` | 失敗stage、再試行導線、エラー詳細を表示 |
| `cancel_requested` | キャンセル要求中として表示 |
| `cancelled` | 中止済み |

## 未決事項

なし。

## 受け入れ条件

- ユーザーが一覧から新規作成、ソース確認、生成、プレビュー、フィードバックまで辿れる。
- LLM生成中に画面が固まらず、状態がポーリング表示される。
- 検証エラーが草稿本文と同じコンテキストで確認できる。

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-13 | 初版作成 |
| 2026-05-17 | Tailwind CSS + DaisyUI主軸、Flowbite保留、業務画面はtable/section中心とするUIコンポーネント方針を追加 |
| 2026-05-17 | rerun comparison、rerun diff、比較候補datalist、再生成ジョブリンク、legacy full editor bridge、distribution package、`monthly-report-refresh` event更新、stale base hash conflict、running復帰案内をHTMX断片一覧と状態方針へ反映 |
