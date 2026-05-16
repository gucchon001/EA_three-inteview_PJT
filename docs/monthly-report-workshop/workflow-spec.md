# 業務フロー仕様書

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツールの業務フロー仕様
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- 関連文書: `requirements.md`, `functional-spec.md`, `api-definition.md`
- 最終更新: 2026-05-14

## As-Is

現状の月次レポート作成は、Google Workspace資料、NotebookLM、ローカルスクリプト、Cursor上の対話、静的HTML確認が分散している。

| レイヤー | 現状 |
|---|---|
| ソース取得 | `gws`, `scripts/fetch_monthly_gws_sources.py`, `gws_doc_json_to_plaintext.py` |
| 別系統 | NotebookLM / `nlm`, 世帯レジストリ |
| 草稿生成 | Cursor対話、`scripts/monthly_report_draft_openrouter.py` |
| 推敲・確認 | `serve_project.py`, 全文エディタ, 静的HTML/Vercel |
| Webアプリ | `src/eb_app` はモック中心で本番生成パイプライン未統合 |

## To-Be

ユーザーはブラウザ上で対象月・対象世帯・Google Sheets / Docsソースを指定し、取得結果を確認してから生成ジョブを開始する。サーバはソースをスナップショット保存し、LLMへ渡す入力を組み立て、生成結果を保存し、決定的バリデーションを行い、プレビューと推敲画面へ返す。

## 標準フロー

| 順 | 段階 | ユーザー操作 | システム処理 | 成果物 |
|---:|---|---|---|---|
| 1 | login | Googleログイン | ドメイン検証 | セッション |
| 2 | setup | 対象月・対象世帯・ソースURL入力 | 入力検証 | ジョブドラフト |
| 3 | fetch_sources | 取得開始 | Sheets / Docs / Drive API取得 | ソーススナップショット |
| 4 | review_sources | ソース一覧確認 | サイズ・種別・取得状態表示 | 確認済みソース |
| 5 | create_job | 生成ボタン | 同時実行数チェック、ジョブ作成 | `queued` ジョブ |
| 6 | bundle | なし | ソース連結、サイズ制限、hash計算 | source bundle |
| 7 | build_messages | なし | テンプレート・tone・データ契約を合成 | prompt messages |
| 8 | call_llm | なし | OpenRouter呼び出し | draft markdown |
| 9 | validate | なし | 規約検証 | errors / warnings |
| 10 | preview_edit | 草稿確認・推敲 | Markdown表示、編集保存 | 最終編集候補 |
| 11 | feedback | 問題タグ・メモ入力 | フィードバック保存 | 改善材料 |

## 例外フロー

| ケース | 振る舞い |
|---|---|
| OAuth失効 | 再ログインまたは再連携を促す |
| ソース取得失敗 | 失敗ソースを一覧に残し、再取得可能にする |
| 同時実行超過 | 429相当として「実行中ジョブが3件あります」を表示する |
| LLMタイムアウト | `failed` にし、stageとerror_typeを保存する |
| 検証エラー | 草稿は保存し、エラー一覧を表示する。自動repairはMVPでは実行しない |
| ユーザー離脱 | ジョブ一覧から再開できる |

MVPの長時間生成は、DB上のジョブ状態とHTMXポーリングで扱う。SSEやCloud Tasks等は後続検討とする。DB-backed workerは `queued` jobを原子的に `running` へclaimしてから実行する。Postgresでは `FOR UPDATE SKIP LOCKED` を使い、複数workerが同じjobを実行しないようにする。

## ジョブ状態

| 状態 | 意味 |
|---|---|
| `draft` | 入力途中 |
| `queued` | 生成待ち |
| `running` | パイプライン実行中 |
| `succeeded` | 生成・保存・検証完了 |
| `failed` | 実行失敗 |
| `cancel_requested` | キャンセル要求済み。実行中stageの終了後、次stageへ進ませない |
| `cancelled` | ユーザーまたは管理者が中止 |
| `rerun_requested` | 同一スナップショットから再生成依頼済み |

## 未決事項

なし。

## 受け入れ条件

- 標準フローの各段階が [functional-spec.md](functional-spec.md) と [api-definition.md](api-definition.md) に対応している。
- 失敗時にジョブ一覧から状態と原因を確認できる。
- 同一入力の再実行に必要な保存項目が [data-design.md](data-design.md) に存在する。

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-13 | 初版作成 |
| 2026-05-14 | DB-backed workerのqueued job claim方針を反映 |
