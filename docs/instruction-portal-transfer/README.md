# 指導管理ポータル 別プロジェクト移管計画

## 位置づけ

- 正本/補助資料の区分: 指導管理ポータルを本リポジトリから別プロジェクトへ切り出すための移管計画
- 起点: `docs/requirements/v0.3.md`, `docs/web-app/screen-design.md`, `docs/sheets-migration/parser-spec.md`
- 関連文書: `docs/pjc/eb_juku_instruction_monitoring_charter.md`, `docs/wbs/eb_juku_instruction_monitoring_wbs.md`, `docs/monthly-report-workshop/development-plan.md`
- 最終更新: 2026-05-17

## 決定事項

1. **レポート工房と指導管理ポータルは別プロジェクトとして管理する。**
   - レポート工房は、月次レポート生成・検証・編集・保存・エクスポートのMVPを先に単体リリースする。
   - 指導管理ポータルは、教師・生徒・指導枠・指導実績・面談/MTG・学習計画表運用を扱う別プロジェクトとして切り出す。

2. **統合順序は段階移行とする。**
   - Step 1: レポート工房MVPを単体リリース
   - Step 2: 指導管理ポータルを構築
   - Step 3: レポート工房を指導管理ポータルへ組み込み
   - Step 4: 指導枠ごとにデータソースを一元管理
   - Step 5: 学習計画表のスプレッドシート運用を指導ポータルへ組み込み
   - Step 6: 学習計画表作成MVPを別プロジェクトから組み込み
   - Step 7: studentシート（基本情報）をポータルDBへ移管し、Sheets運用を廃止

3. **データソース責務を分ける。**

| 領域 | 正とするソース | 移管後の扱い |
|---|---|---|
| 生徒・契約・コース等の基本情報 | FileMaker / 既存基幹情報 | 指導ポータルDBへ同期・移行 |
| 指導実績・実施時間・指導報告書 | マイページ（指導報告書）BigQuery | 指導ポータルDBへ同期。列定義・キーはBigQuery MCPで確認 |
| 面談/教師MTG/学習面談ステータス | 指導モニタリング管理表 | 移行期にSheetsから取り込み、将来はポータル入力へ寄せる |
| 学習計画表 | 現行Google Sheets → 将来ポータルDB | 学習計画表作成MVPの組み込み後にDB正本化 |
| レポート生成結果 | レポート工房 | 統合後は指導ポータル内の指導枠/生徒に紐付ける |

4. **本リポジトリには、移管完了までのポインタと連携契約だけを残す。**
   - 指導管理ポータルの詳細要件・画面・移行仕様は新プロジェクトへ移す。
   - レポート工房側には、ポータル統合時の外部契約だけを残す。

## 移管対象

### 新プロジェクトへ移す文書

| 現在の場所 | 移管後の役割 |
|---|---|
| `docs/requirements/v0.3.md` | 指導管理ポータル要件定義 |
| `docs/web-app/screen-design.md` | 指導管理ポータル画面設計 |
| `docs/web-app/mock-ui-boundary.md` | ポータルモック境界 |
| `docs/sheets-migration/` | 指導モニタリング管理表の移行仕様・fixtures |
| `docs/pjc/eb_juku_instruction_monitoring_charter.md` | 指導ポータルPJC |
| `docs/wbs/eb_juku_instruction_monitoring_wbs.md` | 指導ポータルWBS |
| `docs/phase0/PO_REVIEW_PACKAGE.md` | 指導ポータルPhase 0レビュー論点 |
| `.cursor/skills/eb-juku-portal-ui/` | 指導ポータルUI運用スキル |

### 新プロジェクトへコピーまたは再利用する候補

| 現在の場所 | 判断 |
|---|---|
| `DESIGN.md` | 指導ポータル用にコピーし、レポート工房との差分が出たら移管先で更新 |
| `src/eb_app/templates/mock/` | モック実装を移管先のFastAPI/Jinja構成へコピー候補 |
| `src/eb_app/fixtures/portal_frame.py` | ポータルナビの初期実装候補 |
| `src/eb_app/fixtures/mock_screens.py` | 画面一覧とモックURLの同期用にコピー候補 |
| `tests/test_mock_ui.py` | モック境界の回帰テストとしてコピー候補 |

### 本リポジトリに残すもの

| 場所 | 残す理由 |
|---|---|
| `docs/monthly-report-workshop/` | レポート工房MVPの正本 |
| `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md` | レポート工房の起点 |
| `docs/samples/monthly-reports/` | レポート工房のテンプレート・サンプル |
| `src/eb_app/monthly_reports/` | レポート工房MVP実装 |

## 新プロジェクト案

| 項目 | 案 |
|---|---|
| 仮称 | `EB_instruction_portal` または `ea-instruction-portal` |
| 技術 | FastAPI + Jinja2 + HTMX + Tailwind/DaisyUI + Supabase Postgres |
| デプロイ | Cloud Run |
| 認証 | Supabase Auth。教師は招待メール方式 |
| データ境界 | 指導ポータルが教師・生徒・指導枠・実績・学習計画表を所有。レポート工房は生成ジョブ機能として後段統合 |

## 移管フェーズ

### Phase T0: 境界固定

目的: 切り出す範囲を決め、レポート工房側のMVP進行を止めない。

完了条件:
- 本計画が正本化されている
- `docs/requirements/v0.3.md` に指導ポータルとレポート工房の境界が明記されている
- レポート工房側のPhase 4が「指導ポータル構築後に組み込み」として整理されている

### Phase T1: 移管先リポジトリ準備

目的: 指導ポータル専用の正本と開発環境を作る。

タスク:
- 新リポジトリを作成する
- `AGENTS.md` を指導ポータル用に作成する
- `docs/README.md` と `docs/DOCUMENTATION_LIFECYCLE.md` を移管先へ作成する
- FastAPI/Jinja/HTMX/Supabaseの最小スケルトンを用意する

完了条件:
- 移管先でlint/test/build相当の最小品質ゲートが通る
- 移管先のdocs入口から要件・画面・移行仕様へ辿れる

### Phase T2: 文書移管

目的: 指導ポータル仕様の正本を移管先へ移す。

タスク:
- `requirements/v0.3.md`, `web-app/`, `sheets-migration/`, `pjc/`, `wbs/`, `phase0/PO_REVIEW_PACKAGE.md` を移管
- 本リポ側は同内容を二重管理せず、移管先URLまたは移管済みメモへ置換する
- 本リポの `docs/README.md` と `DOCUMENTATION_LIFECYCLE.md` を「指導ポータルは別プロジェクト」を示す形へ再整理する

完了条件:
- 指導ポータル仕様の更新先が移管先に一本化される
- 本リポに残るポータル文書は、移管先へのリンクまたは統合契約だけになる

### Phase T3: データ移行設計の深化

目的: BigQuery / FileMaker / Sheets / 学習計画表の取り込み契約を実装可能にする。

タスク:
- BigQuery MCPでマイページ（指導報告書）のdataset/table/schema/key候補を確認する
- FileMaker/基幹情報の取得方式を確認する
- 指導モニタリング管理表のparser-specを移管先のDB schemaへ合わせる
- 学習計画表作成MVPとの接続契約を決める

完了条件:
- `students`, `teachers`, `assignments`, `lesson_reports`, `meetings`, `lesson_plans`, `import_errors` の初期ERDがある
- 充足率の算出式と出典がテスト可能な形で固定される

### Phase T4: モック/画面実装移管

目的: 現在のポータルモックを移管先で生かす。

タスク:
- `templates/mock`, `portal_frame.py`, `mock_screens.py`, `tests/test_mock_ui.py` を移管または再実装する
- `docs/web-app/screen-design.md` とモックURLの同期を移管先で維持する
- 指導枠詳細にデータソース表示と乖離アラートのUIを追加する

完了条件:
- 移管先でダッシュボード、教師一覧、生徒一覧、指導枠詳細、取込エラー一覧のモックが表示できる
- モック境界テストが通る

### Phase T5: レポート工房統合契約

目的: レポート工房をポータルへ組み込む前に、契約を先に固定する。

タスク:
- 指導ポータルからレポート生成ジョブを作るAPI/HTML actionの契約を定義する
- 指導枠、対象月、データソースbundle、生成artifact、承認状態のID対応を固定する
- レポート工房側はポータルDBを直接所有せず、統合用の入力契約を受ける形に寄せる

完了条件:
- 指導ポータル側から「この指導枠・対象月で生成」を呼べる設計がある
- レポート工房単体MVPのデータモデルと矛盾しない

## カットオフ条件

| 条件 | 内容 |
|---|---|
| 文書カットオフ | 指導ポータル要件・画面・移行仕様の正本が移管先へ移り、本リポでは編集しない |
| 実装カットオフ | ポータル固有の画面/DB/API実装は移管先で行う |
| データカットオフ | BigQuery/FileMaker/Sheets移行実装は移管先で行う |
| 統合再開条件 | レポート工房MVPが単体リリースされ、指導ポータル側の指導枠/データソース管理がMVP化している |

## 未決事項

| ID | 未決事項 | 確認方法 |
|---|---|---|
| U-01 | 移管先リポジトリ名・配置 | ユーザー決定 |
| U-02 | BigQueryのdataset/table/schema/key | BigQuery MCPで確認 |
| U-03 | FileMaker/基幹情報の取得方式 | 既存連携方法または担当者確認 |
| U-04 | 学習計画表作成MVPの範囲 | 別プロジェクト計画で定義 |
| U-05 | 本リポからポータル文書を削除するタイミング | 移管先作成後に決定 |

## 受け入れ条件

- 指導ポータルを別プロジェクトとして説明できる
- 移管対象・残置対象・コピー候補が明確である
- BigQuery/FileMaker/Sheets/学習計画表/レポート工房の責務が分かれている
- 本リポ側のレポート工房MVP開発を止めずに進められる
- 移管後にどの文書を更新すべきか迷わない

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-17 | 初版作成。レポート工房と指導管理ポータルの切り分け、移管対象、カットオフ条件、統合順序を定義 |
