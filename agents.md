# agents.md — 月次レポート作成ツール 開発ドキュメント生成チーム

このファイルは、`docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md` を起点に、月次レポート作成ツール（別名: レポート工房）の開発ドキュメントを作成・更新するためのエージェント分担表です。

目的は、要件定義書・仕様書・画面設計書・API定義書・開発計画書などを、チャット内の暗黙知ではなく、リポジトリ上の正本として揃えることです。

**月次レポート自動生成のゴール・アーキ方針（静的 POC とレポート工房の接続）**は、`docs/monthly-report-workshop/AUTOMATION_NORTH_STAR.md` を正とする（Cursor では `.cursor/rules/monthly-report-north-star.mdc` も参照）。

---

## 1. 最優先で守ること

1. **正本候補**
   - 戦略・アーキ（北極星）: `docs/monthly-report-workshop/AUTOMATION_NORTH_STAR.md`
   - 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
   - 月次レポート規約: `docs/samples/monthly-reports/monthly_pattern_b_content.template.md`
   - データ契約: `docs/samples/monthly-reports/DATA_CONTRACT_05_学習の進捗.md` ほか既存データ契約
   - 既存ポータル要件: `docs/requirements/v0.3.md`
   - 既存画面設計: `docs/web-app/screen-design.md`
   - UIトークン: `DESIGN.md`

2. **古い文書の扱い**
   - `docs/project/レポート自動化システム_要件定義.md` は参考資料として扱う。
   - 最新の決定事項と矛盾する場合は、移行計画書を優先する。
   - 特に以下は移行計画書の決定を正とする。
     - FastAPI + Jinja2 + HTMX
     - Cloud Run
     - Google アカウント認証、`tomonokai-corp.com` 限定
     - Google Sheets / Docs はユーザーOAuthでサーバ取得
     - OpenRouter中心
     - 1ユーザー最大3生成ジョブ
     - MVPは本番のみ
     - MVPの主目的はチューニング、ログ・スナップショット・生成物保存を必須

3. **MVPの境界**
   - 「エディタのみ」ではない。
   - スコープは、データソース取込・LLM生成・規約検証・推敲（プレビュー／エディタ）を一体で扱う。
   - 既存の静的HTML/Vercel配信は当面維持してよいが、レポート工房本体は Cloud Run 上の FastAPI とする。

4. **セキュリティ**
   - サービスアカウント鍵や OpenRouter API キーをフロントへ置かない。
   - PIIをログへ生出力しない。
   - ソーススナップショット・生成物・検証結果は保存するが、権限・保持期間・削除ポリシーを必ず設計対象に含める。

---

## 2. 作成する開発ドキュメント

推奨配置は `docs/monthly-report-workshop/`。既存の `docs/project/` に置く場合も、下記のファイル名と役割は維持する。

| 文書 | 推奨ファイル | 目的 |
|---|---|---|
| ドキュメント索引 | `README.md` | 正本・関連資料・更新順序を示す入口 |
| 要件定義書 | `requirements.md` | 業務要件、機能要件、非機能要件、制約、成功基準 |
| 業務フロー仕様書 | `workflow-spec.md` | 現行業務、To-Be、ジョブ生成から推敲までの流れ |
| 機能仕様書 | `functional-spec.md` | 画面・API・ジョブ・検証・再生成などの振る舞い |
| 画面設計書 | `screen-design.md` | ページ、HTMX断片、状態、権限別表示、エラー表示 |
| API定義書 | `api-definition.md` | REST/fragment API、リクエスト/レスポンス、エラー、認可 |
| データ設計書 | `data-design.md` | RDB候補、ジョブ、ソーススナップショット、成果物、監査ログ |
| LLM設計書 | `llm-design.md` | プロンプト版管理、モデル選択、OpenRouter呼び出し、検証・リペア |
| セキュリティ・運用設計書 | `security-operations.md` | 認証、権限、PII、Secrets、Cloud Run、ログ、保持・削除 |
| テスト計画書 | `test-plan.md` | 単体、結合、ゴールデンフィクスチャ、モックLLM、手動確認 |
| 開発計画書 | `development-plan.md` | フェーズ、WBS、依存関係、未決事項、受け入れ条件 |
| 課題・決定ログ | `decision-log.md` | 未決事項、決定事項、変更履歴、PO確認事項 |

---

## 3. エージェント構成

### 3.1 Documentation Lead

**責務**

- 全文書の構成、粒度、正本関係を管理する。
- 文書間の重複を抑え、参照リンクを張る。
- 移行計画書の決定事項を各文書へ展開する。

**主な成果物**

- `README.md`
- `decision-log.md`
- 各文書の冒頭に置く「正本・参照元・更新ルール」

**確認観点**

- どの文書を読めば何が分かるかが明確か。
- 古い要件と新しい決定事項が混ざっていないか。
- 未決事項が本文に紛れず、決定ログへ分離されているか。

### 3.2 Requirements Agent

**責務**

- 移行計画書を要件定義へ変換する。
- MVP、将来統合、スコープ外を明確に分ける。
- 成功基準と非機能要件を測定可能にする。

**主な成果物**

- `requirements.md`

**必ず含める要件**

- Googleアカウントログイン、`tomonokai-corp.com` 限定
- ユーザーOAuthによる Sheets / Docs / Drive API 取得
- ジョブ・ソーススナップショット・生成成果物・検証結果の保存
- 1ユーザー最大3生成ジョブ
- OpenRouter中心、本文用モデルと軽量モデルの分離
- Cloud Run本番のみ
- チューニング期間のモデル・プロンプト・テンプレート比較

### 3.3 Workflow / Functional Spec Agent

**責務**

- 業務フローと機能仕様を定義する。
- fetch → bundle → build_messages → call_llm → validate → preview/edit の流れを仕様化する。
- ジョブ状態、再生成、検証失敗時の扱いを決める。

**主な成果物**

- `workflow-spec.md`
- `functional-spec.md`

**確認観点**

- 同一入力から再実行できるか。
- LLMが数十秒から数分かかる前提で非同期ジョブになっているか。
- 検証失敗を人手へ戻すか、repair loopへ送るかが明確か。

### 3.4 UI / Screen Design Agent

**責務**

- Jinja2 + HTMX前提の画面設計を作る。
- 既存ポータルの `docs/web-app/screen-design.md` と `DESIGN.md` に合わせる。
- 「操作ひとつでドラフト生成から推敲まで辿れる」画面導線にする。

**主な成果物**

- `screen-design.md`

**想定画面**

- ログイン
- レポートジョブ一覧
- 新規ジョブ作成
- ソース確認
- ジョブ進捗
- 生成結果プレビュー
- 推敲エディタ
- 検証結果
- チューニング・フィードバック入力
- 管理者向け設定（モデル、テンプレート版、プロンプト版）

**HTMX方針**

- ジョブ作成: `hx-post`
- 進捗更新: polling fragment
- プレビュー差し替え: fragment swap
- 検証結果・フィードバック保存: fragment or modal

### 3.5 API Design Agent

**責務**

- FastAPIのHTTP APIとHTML fragment APIを定義する。
- REST API、認証、エラー、ジョブ状態遷移を明確にする。

**主な成果物**

- `api-definition.md`

**最小API候補**

- `POST /api/monthly-reports/jobs`
- `GET /api/monthly-reports/jobs`
- `GET /api/monthly-reports/jobs/{job_id}`
- `POST /api/monthly-reports/jobs/{job_id}/rerun`
- `POST /api/monthly-reports/jobs/{job_id}/feedback`
- `GET /monthly-reports/jobs/{job_id}/fragments/status`
- `GET /monthly-reports/jobs/{job_id}/fragments/preview`
- `GET /monthly-reports/jobs/{job_id}/fragments/validation`

**確認観点**

- 同期 `generate` API に寄せすぎていないか。
- UI fragment と JSON API の境界が分かるか。
- 429、401、403、404、422、500系の扱いがあるか。

### 3.6 Data / Persistence Agent

**責務**

- 保存すべきデータとRDBスキーマ候補を設計する。
- 将来の Supabase ポータル統合を見越した形にする。
- ソーススナップショットとマスク済みログの境界を設計する。

**主な成果物**

- `data-design.md`

**最低限のテーブル候補**

- `monthly_report_jobs`
- `monthly_report_sources`
- `monthly_report_artifacts`
- `monthly_report_validations`
- `monthly_report_feedback`
- `prompt_versions`
- `template_versions`
- `llm_call_logs`
- `audit_logs`

**確認観点**

- `prompt_version`、テンプレートハッシュ、Git SHA、モデルID、source hashが残るか。
- 後から「何が効いたか」を説明できるか。
- 保持期間・削除ポリシーが未決なら未決事項として残っているか。

### 3.7 LLM Design Agent

**責務**

- OpenRouter呼び出し、プロンプト構成、モデル分離、検証・リペアを設計する。
- プロンプトをコード内の長文字列にせず、リポジトリ内の断片として管理する方針を定義する。

**主な成果物**

- `llm-design.md`

**必須項目**

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL_REPORT`
- `OPENROUTER_MODEL_LIGHT`
- `OPENROUTER_MODEL` のフォールバック有無
- report / light の prompt_kind
- sources_hash
- prompt_version
- deterministic validation
- optional repair loop

### 3.8 Security / Operations Agent

**責務**

- 認証、認可、Secrets、Cloud Run、ログ、監査、PII保護を設計する。
- Google OAuthのスコープ、リフレッシュトークン保管、ドメイン制限を要件から仕様へ落とす。

**主な成果物**

- `security-operations.md`

**確認観点**

- ブラウザにAPIキーやSAキーを置かないことが明記されているか。
- Cloud Loggingへ本文や生ソースを出さない設計か。
- Cloud Runのタイムアウト、同時実行、メモリ、Secret参照が未決なら未決事項化されているか。

### 3.9 Test / QA Agent

**責務**

- テスト計画、ゴールデンフィクスチャ、モックLLM、受け入れ条件を定義する。
- 規約違反をコードとテストで検出できる形にする。

**主な成果物**

- `test-plan.md`

**最低限のテスト**

- バンドル切り詰め
- 必須見出し
- 禁止語
- 星5行の原文一致
- provider mockによるジョブ生成
- 429同時実行制限
- OAuth認可失敗
- PIIログ抑止

### 3.10 Development Plan Agent

**責務**

- 開発計画とWBSを作る。
- フェーズ0からMVP、品質、体験、統合までを実装単位に分解する。

**主な成果物**

- `development-plan.md`

**フェーズ**

- Phase 0: プロンプト断片の正本化、prompt_version付与
- Phase 1: MVP、チューニング記録、ジョブ保存、モック応答
- Phase 2: 決定的バリデーション、テスト、エラーハンドリング
- Phase 3: プレビュー、再生成、プロンプト版切替、HTMLエクスポート
- Phase 4: Supabaseポータル統合

---

## 4. 推奨作業順

1. Documentation Lead が `README.md` と `decision-log.md` の枠を作る。
2. Requirements Agent が `requirements.md` を作る。
3. Workflow / Functional Spec Agent が `workflow-spec.md` と `functional-spec.md` を作る。
4. UI / Screen Design Agent と API Design Agent が並行して `screen-design.md` / `api-definition.md` を作る。
5. Data / Persistence Agent と LLM Design Agent が `data-design.md` / `llm-design.md` を作る。
6. Security / Operations Agent が横断レビューし、`security-operations.md` を作る。
7. Test / QA Agent が `test-plan.md` を作る。
8. Development Plan Agent が全成果物を受けて `development-plan.md` を作る。
9. Documentation Lead がリンク、用語、未決事項、矛盾を最終整合する。

---

## 5. ドキュメント共通テンプレート

各文書は、最低限以下の構成を持つ。

```markdown
# 文書名

## 位置づけ

- 正本/補助資料の区分:
- 起点:
- 関連文書:
- 最終更新:

## 決定事項

## 詳細

## 未決事項

## 受け入れ条件

## 改訂履歴
```

---

## 6. 用語

| 用語 | 意味 |
|---|---|
| 月次レポート作成ツール | 今回作るプロダクト名。別名「レポート工房」。 |
| レポート工房 | データソース取込、LLM生成、規約検証、推敲を一体化したWebツール。 |
| ジョブ | 月次レポート生成の単位。対象月、対象世帯、ソース、モデル、プロンプト版を持つ。 |
| ソーススナップショット | Google Sheets / Docs などから取得した入力を、再実行可能な形で保存したもの。 |
| 成果物 | 生成されたMarkdown、HTML、検証結果、最終編集後Markdownなど。 |
| prompt_version | 生成に使ったプロンプト断片の版。 |
| template hash | `monthly_pattern_b_content.template.md` など、テンプレート正本の内容ハッシュ。 |
| report model | レポート本文生成に使う品質優先モデル。 |
| light model | 抽出・分類・下準備・リペアなどに使う廉価モデル。 |

---

## 7. レビュー基準

ドキュメント作成後、以下を満たすこと。

- 移行計画書の決定事項が漏れていない。
- 古い要件定義との矛盾は、本文または決定ログで扱われている。
- MVPと将来統合が混ざっていない。
- UI、API、データ、LLM、セキュリティ、テスト、開発計画が相互参照されている。
- 未決事項が明示されている。
- 実装者が次にファイルやAPIを作れる粒度になっている。
- PII、APIキー、サービスアカウント鍵の扱いが安全側に倒れている。

---

## 8. 静的 POC でのチューニング → 設計への合流（複数チャット運用）

ローカル OpenRouter、`scripts/monthly_report_*.py`、レシピ JSON、Economics／複数生徒 MTG などで先行チューニングされている内容の **引き継ぎ単一入口** は、[`docs/monthly-report-workshop/HANDOFF_STATIC_POC_TUNING.md`](docs/monthly-report-workshop/HANDOFF_STATIC_POC_TUNING.md) とする。Documentation Lead が [`decision-log.md`](docs/monthly-report-workshop/decision-log.md) の **D-046 / U-025** と同期し、[`README.md`](docs/monthly-report-workshop/README.md) の索引でも参照すること。

---

## 9. 低トークン運用・モデルルーティング

目的は、品質を落とさずに毎回のコンテキスト投入・探索・出力を最小化すること。モデル切替をホスト外から強制するのではなく、作業種別ごとの既定判断として運用する。

### 9.1 コンテキスト投入ルール

- 最初に `rg` / `rg --files` / 目次ファイルで候補を絞り、関連箇所だけ読む。
- 大きな正本は全文を読まず、必要な見出し・決定事項・改訂履歴だけを優先する。
- 生成物、lockfile、`.pytest_cache`、`node_modules`、ビルド成果物、長いログは対象でない限り読まない。
- 同じ内容を複数文書へ長文重複させない。正本1つに寄せ、他文書はリンクと短い要約にする。
- 進捗報告・最終報告は、変更点、確認結果、未確認リスクだけを短く残す。

### 9.2 モデル選択の既定

| 作業 | 既定モデル方針 | 理由 |
|---|---|---|
| ファイル探索、差分確認、単純な文書整形 | 軽量・高速モデル | 読む範囲が狭く、判断リスクが低い |
| 単一ファイルの小修正、既存パターンに沿うテスト追加 | 標準モデル | 実装判断は必要だが、範囲が限定的 |
| アーキテクチャ、セキュリティ、DB、OAuth、LLM設計、横断仕様 | 強いモデル | 誤判断のコストが高い |
| 2回以上同じ不具合修正に失敗した調査 | 強いモデルへ上げる | 仮説の立て直しが必要 |
| 大量文書の棚卸し、独立した複数観点レビュー | ユーザーが明示した場合のみサブエージェント | 並列化は有効だが、起動コストもある |

### 9.3 サブエージェントの節約ルール

- サブエージェントは、ユーザーが明示的に並列化・委任を求めた場合だけ使う。
- `fork_context=false` を既定にし、読むファイル、書く範囲、返答形式を絞る。
- 依頼文は「Task / Read / Write scope / Verify / Return」の5項目に圧縮する。
- 返答は `changed files`, `test result`, `blockers` のみを求める。

### 9.4 月次レポート工房での適用

- ドキュメント更新は、まず `docs/monthly-report-workshop/README.md` と該当正本だけ読む。
- 静的 POC の引き継ぎは `docs/monthly-report-workshop/HANDOFF_STATIC_POC_TUNING.md` を入口にし、個別レシピやサンプルは必要時だけ開く。
- LLM・API・データ・セキュリティの横断変更では、軽量化より安全性と再現性を優先する。
- 実装後の確認は focused test を先に使い、必要な場合だけ広い test / build へ進む。

## 10. Phase 1 以降の実装エージェント構成

### 10.1 体制（実装実行）

- **Phase 1 実装オーナー**
  - FastAPI基盤、認証、ジョブ実行、Google Workspace連携の全体責任を持つ
- **Backend & Data Agent**
  - `src/eb_app/monthly_reports/*` のジョブ/ストア/API実装、RLS・保存ポリシー、永続化
- **Auth & OAuth Agent**
  - Supabase JWT検証、メールドメイン制限、Google OAuth refresh token保存、provider token再取得
- **LLM Pipeline Agent**
  - `build_messages` / `call_llm` / `llm_call_logs` / providerモック、OpenRouter呼び出しと失敗分類
- **Validation & Safety Agent**
  - 決定的バリデーション、PII/secret抑止、Cloud Logging allowlist、監査イベント
- **UI/HTMX Agent**
  - ジョブ一覧、進捗、プレビュー、推敲、フィードバック、再生成UI
- **QA・運用エージェント**
  - focused pytest運用、CI接続、e2e手順、pre-e2e-setupの整備

### 10.2 役割の責任境界

- 同一ファイルの同時編集を避ける。`src/eb_app/routers`, `src/eb_app/monthly_reports`, `tests` は担当を固定し、横断変更は実装オーナーの同期確認後に着手する。
- 仕様変更は `decision-log.md` 更新後、影響する設計文書（requirements→api-definition→development-plan）へ同時反映する。
- 実装判断が必要な場合は `agents.md` と `decision-log.md` の優先更新で全体方針を固定する。

## 11. 次のE2E優先順（Phase 1以降）

### 11.1 最優先（即着手）

- `Supabase Auth Google provider` からの実トークン取得
- `POST /api/auth/google-oauth/supabase-session` と保存APIの実接続
- `POST /api/monthly-reports/jobs/{job_id}/fetch-google-sources` を実Googleソースで通す
- `POST /api/monthly-reports/jobs/{job_id}/run-openrouter` を1件実案件データで成功まで通す
- `validation` と `artifact保存` を同一ジョブで確認

### 11.2 優先（Phase 1完了条件）

- `src/eb_app/monthly_reports/worker.py` を常駐実行想定へ接続し、`queued` jobの自動claim/進行を実運用で安定化
- 3件同時実行制限（429）が実環境APIでも再現されることを確認
- 再生成時の再現性メタ継承（prompt/version/template/model/source_hash）を監査可能に可視化
- LLM失敗時の `error_type` 分類と再実行導線（再試行/再生成）をE2Eで整備

### 11.3 仕上げ（Phase 3）

- 編集後Markdown保存（編集可能な最小導線）を実装し、最終成果物まで保存する
- 再生成API/UIを公開し、プロンプト版・モデル版の比較材料を表示
- HTMLエクスポート / ファイル保存 / 送付系フローを最小実装して現行仕様との動作接続を確認
- 現行静的プレビュー経路との接続差分を吸収し、同一画面導線へ統合
- Playwright（最小シナリオ）でジョブ作成→取得→生成→検証→推敲まで通す
