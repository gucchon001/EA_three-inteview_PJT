# 画面設計書

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツールの画面設計
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- 関連文書: `docs/web-app/screen-design.md`, `DESIGN.md`, `functional-spec.md`, `api-definition.md`
- 最終更新: 2026-05-13

## 基本方針

- FastAPI + Jinja2 + HTMXで構築する。
- CSR専用SPAにはしない。
- MVPは月次レポート生成ツール単体で動かし、ポータルのグローバルナビ・サイドバーには依存しない。
- 将来の既存ポータル統合を見越し、ルータ・テンプレート・サービスを `monthly_reports` 境界で分ける。
- 進捗、検証結果、プレビュー差し替えはHTMX fragmentで行う。
- 画面は業務ツールとして密度高く、静かでスキャンしやすい構成にする。
- 推敲・プレビュー画面は、現行 `docs/samples/monthly-reports/tools/monthly_report_full_editor.html` のHTML全文エディタをベースにする。
- 現行エディタの送付エクスポート、ファイル保存、ファイルから開く、HTMLソース直接編集はMVP内の後続必須機能として扱う。

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
| MR-S05 | プレビュー・推敲 | `/monthly-reports/jobs/{job_id}/edit` | 必須 | Markdown優先 |
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

- 再取得
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

## MR-S05 プレビュー・推敲

### レイアウト

| 領域 | 内容 |
|---|---|
| 上部 | ジョブ状態、検証結果サマリ、保存状態 |
| 編集枠直上 | 1行のコンパクト編集ツールバー |
| 中央 | 現行エディタ由来のiframe編集領域 |
| 下部 | HTMLソース直接編集、保存、送付エクスポート、フィードバック |
| サイドバー連動パネル | 検証結果、ソース確認、簡易差分、チューニングを本文下にアンカー表示 |

### 操作

- サーバ側自動保存
- HTMLソース直接編集
- 簡易テキスト差分表示
- 検証再実行
- フィードバック保存
- ファイル保存・ファイルから開く
- 送付エクスポート
- standalone MVPモックでは、左サイドバーの検証結果・ソース確認・簡易差分・チューニングをバックエンド依存なしのアンカーパネルとして表示する。

## MR-S06 チューニング設定

管理者のみアクセスできる。一般ユーザーには表示しない。

### 表示・操作

- report modelの固定プリセット選択
- light modelの固定プリセット選択
- `openrouter/auto` の比較利用
- `prompt_version` の選択
- テンプレート版の選択
- 設定変更履歴の確認

## HTMX fragment一覧

| ID | GET/POST | 用途 |
|---|---|---|
| MR-F01 | `GET /monthly-reports/jobs/{job_id}/fragments/status` | 進捗ポーリング |
| MR-F02 | `GET /monthly-reports/jobs/{job_id}/fragments/preview` | Markdown/HTMLプレビュー |
| MR-F03 | `GET /monthly-reports/jobs/{job_id}/fragments/validation` | 検証結果 |
| MR-F04 | `POST /monthly-reports/jobs/{job_id}/fragments/feedback` | フィードバック保存後の差し替え |

MVPではSSEを使わず、HTMXポーリングに統一する。

## 状態表示

| 状態 | UI表現 |
|---|---|
| `queued` | 待機中 |
| `running` | stage名と進捗を表示 |
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
