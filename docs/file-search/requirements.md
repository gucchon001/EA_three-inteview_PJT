# File Search 機能 要件定義

## 位置づけ

- 正本/補助資料の区分: File Search 機能の要件定義
- 起点: `docs/file-search/README.md`
- 関連文書: `api-definition.md`, `data-design.md`, `security-operations.md`
- 最終更新: 2026-05-14

## スコープ

### 対象

- Gemini File Search ストアの作成・運用
- ストア内ドキュメントの一覧・手動アップロード・削除をブラウザから操作する管理画面
- 月次レポート確定時の自動取り込みフック
- 監査ログの保存と参照

### 対象外（本フェーズ）

- 検索クエリの実行 UI（管理画面では、検索のテスト目的でのみ最小実装。生成側は OpenRouter で別途）
- 自然言語による複雑なドキュメント編集（PDF への加筆・分割など）
- 生徒個人情報 PII を含むデータの取り込み（PII は別経路、別ポリシーで扱う）
- ストア横断の重複検出・正規化

## ストア構成（4ストア）

| store_id | 用途 | 更新頻度 | 想定規模 | 主な consumer |
|---|---|---|---|---|
| `ib-syllabus` | IB 公式シラバス（DP / MYP / PYP の各教科ガイド・assessment criteria） | curriculum cycle 単位（数年に1回） | PDF 数十本、計 100-500MB | 月次レポート工房・面談準備 |
| `monthly-reports-archive` | 過去の月次レポート、ゴールデンサンプル | 月次（毎月追加） | テキスト〜中、時系列で増える | 月次レポート工房（few-shot）・トーン参照 |
| `scoring-rubrics` | 採点ルーブリック、mark scheme、assessment criteria | 年次 | 小 | 採点系ツール、月次レポート工房 |
| `internal-handbook` | 講師向け運用ガイド、面談スクリプト、内部 SOP | 不定期 | 小 | ポータル、講師向け検索 |

### 分割した理由

- 更新サイクル・寿命が大きく異なるストアは分けたほうが運用と権限管理が単純化する。
- consumer 側がスコープを絞ってクエリしたいケースが多い（例: 月次レポート生成時に handbook を引きたくない）。
- どれか1ストアを rebuild する場面が必ず来る（シラバス改訂など）ため、独立して扱える単位に切る。
- ストア横断検索が必要な場合は、クエリ側で複数ストアを束ねれば対応可能。分割のデメリットは小さい。

## display_name 規約

形式: `<sub-category>/<identifier>__v<version>.<ext>`

### ストアごとの具体例

| ストア | サブカテゴリ軸 | 例 |
|---|---|---|
| `ib-syllabus` | curriculum tier (`dp` / `myp` / `pyp`) | `dp/math-aa__v2021.pdf`, `myp/sciences__v2020.pdf`, `pyp/transdisciplinary__v2018.pdf` |
| `monthly-reports-archive` | 年月 (`YYYY-MM`) または `golden/YYYY-MM` | `2026-04/suzuki.md`, `golden/2025-12_suzuki__v3.md` |
| `scoring-rubrics` | curriculum tier | `dp/math-aa-paper1__v2021.md`, `dp/extended-essay__v2023.md` |
| `internal-handbook` | カテゴリ（`interview` / `onboarding` 等） | `interview/3者面談-進行台本__v2026-04.md` |

### ルール

- **第1階層 = サブカテゴリ**: ストア内で意味のある軸を1つだけ選ぶ。ネストは2階層以内に収める。
- **ファイル名は ASCII 主体**: handbook 系のみ日本語可。理由は後述（同名照合の安定性）。
- **バージョン suffix を必須化**: `__v<year>` または `__v<year-month>` を末尾に付ける。バージョン管理が不要なら省略可だが、推奨は必須。
- **同名 upload 時は delete → re-upload**: Gemini File Search の `display_name` は API 側では一意制約がないため、こちらで一意性を強制する。
- **メタテーブルが source of truth**: Supabase に `file_search_documents` テーブルを置き、(store_id, display_name) を unique key として扱う。Gemini API への呼び出しはこのメタテーブル経由でラップする。

### display_name の自動生成

| 経路 | 生成方法 |
|---|---|
| 手動アップロード | UI 側でストアごとのテンプレ（例: `monthly-reports-archive` ならアップロード時に年月入力を必須化）から組み立てる |
| 月次レポート auto-ingest | `<target_month>/<household_key>.md` を確定時に組み立てる |
| ゴールデン化トグル | `golden/<target_month>_<household_key>__v<n>.md`（n は既存ゴールデン数 + 1） |

## 機能要件

### F1. ストア一覧表示

- 管理画面のトップで 4ストアをカード表示する。
- カードに表示する情報: store_id、表示名、ドキュメント件数、合計サイズ（概算）、最終更新日時。
- カードクリックでストア詳細画面に遷移する。

### F2. ストア詳細・ドキュメント一覧

- 1ストア内のドキュメントをテーブルで一覧する。
- 列: display_name、size、created_at、updated_at、uploaded_by、操作（削除）
- ソート: updated_at desc 既定。display_name 昇順への切替を提供。
- 検索: display_name の部分一致フィルタを提供（クライアント側 or サーバ side、件数次第）。

### F3. 手動アップロード

- 対応形式: PDF, Markdown, plain text, HTML（Gemini File Search が受け付ける形式に従う）
- アップロード時に display_name を UI 側で組み立てる（ストアごとのフォーム）。
- 同名が既に存在する場合は、上書き確認モーダルを表示してから delete → re-upload する。
- アップロード結果を Supabase メタテーブルに記録する。
- アップロード進捗は HTMX で fragment 更新する（progress 表示）。

### F4. 削除

- ドキュメント単位での hard delete のみ提供する。
- 削除前に確認モーダルを必須化する（display_name を再タイプさせる方式は不要、確認チェックボックス + ボタンで十分）。
- 削除後、Gemini File Search 側と Supabase メタテーブルの双方から削除する。
- 失敗時は片側のみ消えた状態を残さないため、削除は **メタテーブル先行 → Gemini API → 成功時にメタテーブル commit** の2フェーズで行う。詳細は data-design.md。

### F5. 自動取り込み（auto-ingest）

- 月次レポート工房から内部 API で呼ばれる。
- トリガー: 月次レポートの「確定/公開」アクション、および「ゴールデン化」トグル。
- バックエンドから内部呼び出しのため、UI フォームは持たない。
- 取り込み履歴は監査ログに ingest 種別で記録する。

### F6. 取り込み履歴

- ストア詳細画面の下部に、最近の auto-ingest と手動 upload/delete をタイムライン表示する。
- 件数は 直近 50 件、それ以前は別画面の監査ログから辿る。

### F7. 監査ログ

- 全ての upload / delete / auto-ingest を Supabase の `file_search_audit_log` テーブルに保存する。
- 記録項目: timestamp、actor (user_id + email)、action (`upload` / `delete` / `auto_ingest`)、store_id、display_name、source（`manual_upload` / `auto_ingest_monthly_finalize` / `auto_ingest_monthly_golden`）、結果（`success` / `failure`）、failure_reason。
- 監査ログ自体の閲覧は管理者ロールのみ。

## 非機能要件

| 項目 | 要件 |
|---|---|
| 認証 | Supabase Auth、講師/管理者ロールのみ画面アクセス可。詳細は `security-operations.md` |
| 認可 | 全 API でロールチェック。auto-ingest 内部 API はサービストークンで認証 |
| 監査 | 全変更操作を Supabase に記録（hard delete でも履歴は残る） |
| ファイルサイズ上限 | 1ファイル 50MB を上限とする（Gemini File Search の制約に合わせる。確認次第更新） |
| ストア合計サイズ目安 | 1ストア 1GB を上限の目安とする。超過時は分割または古いものの退避を検討 |
| アップロード応答 | 50MB のファイルで 30 秒以内に応答を返す |
| 削除応答 | 同期で 5 秒以内に完了 |
| Secret 管理 | Secret Manager 経由で `GEMINI_API_KEY` `OPENROUTER_API_KEY` を保持。BOM 混入禁止 |
| ログ | Cloud Logging には API レイヤのアクセスログのみ。本文は Supabase 側に閉じる |
| デプロイ | 月次レポート工房と同じ Cloud Run サービス内に同居する（別サービスにはしない） |

## 制約・前提

- Gemini File Search は **Google Gen AI API の機能**であり、OpenRouter 経由では使えない。検索は Gemini ネイティブ、生成は OpenRouter で別経路にする。
- Gemini File Search の `display_name` には API 側の一意制約がない。同名 upload を許せば中身が並んで保存され、検索ノイズの原因になる。Supabase メタテーブルで一意性を強制する。
- Secret Manager に登録する API キーに BOM (U+FEFF) が混入すると Gemini SDK が `ByteString` エラーを返す（過去事例あり）。登録時は `--data-file` か `printf` 経由で BOM を入れない。詳細は `security-operations.md`。
- PII（生徒個人情報・成績の生データ）は File Search ストアには入れない。月次レポートは「レポート本文として整形済み」のものだけが対象。生データは Supabase に閉じる。

## 主要決定事項

| # | 決定 | 根拠・備考 |
|---:|---|---|
| D1 | 4ストアに分割する（`ib-syllabus` / `monthly-reports-archive` / `scoring-rubrics` / `internal-handbook`） | 更新サイクルと寿命が異なる。consumer のスコープも分かれる |
| D2 | 管理 UI はブラウザベース（CLI 直接運用はしない） | 中身の可視化・誰でも操作可能・運用ミス防止 |
| D3 | 講師/管理者ロールのみアクセス可 | PII 影響と運用ガード |
| D4 | hard delete のみ。ゴミ箱機能は持たない | 運用シンプル化。誤削除は監査ログから再アップロードで復旧 |
| D5 | 監査ログを Supabase に保存する | 「誰が消した？」「いつ入った？」を必ず追えるようにする |
| D6 | display_name の一意性は Supabase メタテーブルで強制する | Gemini API 側に一意制約がないため |
| D7 | 検索は Gemini、生成は OpenRouter | File Search は Gemini ネイティブ機能、OpenRouter 経由では使えない |
| D8 | 月次レポート工房と同じ Cloud Run サービスに同居 | デプロイ・認証・Secret 管理を共通化 |

## 未決事項

| # | 内容 | 期限の目安 |
|---:|---|---|
| O1 | ストア合計サイズ 1GB を超えたときの退避先（Supabase Storage / GCS / 別ストア分割） | Phase 2 中盤 |
| O2 | ファイルサイズ上限の正確な値（Gemini 公式値の確認） | Phase 1 着手前 |
| O3 | `internal-handbook` の初期投入対象（面談スクリプト・新人 SOP 等の現物リスト） | Phase 3 開始時 |
| O4 | auto-ingest 失敗時のリトライポリシー（即時1回 / 翌日バッチ / 通知のみ） | Phase 2 設計時 |
| O5 | 監査ログの保持期間（永続 / 1年 / 3年） | Phase 1 着手前 |

## 成功基準

- 月次レポート工房から `ib-syllabus` と `monthly-reports-archive` の2ストアを参照して、シラバス根拠を引いた本文と過去トーンに揃ったレポートが生成される。
- 講師・管理者がブラウザのみで、新規シラバスの差し替え・過去レポートの追加・削除を完結できる。CLI を触る必要がない。
- 誰がいつ何を入れたか・消したかを、監査ログ画面で 1分以内に追える。
- 月次レポート確定操作と同時に `monthly-reports-archive` への取り込みが完了し、講師の手動操作は不要。
