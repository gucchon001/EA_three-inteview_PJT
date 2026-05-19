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
     - 今回プロジェクトの完了条件はレポート工房MVPのstaging環境動作確認とする。production昇格と指導管理ポータル統合は後続スコープ
     - MVPの主目的はチューニング、ログ・スナップショット・生成物保存を必須

3. **MVPの境界**
   - 「エディタのみ」ではない。
   - スコープは、データソース取込・LLM生成・規約検証・推敲（プレビュー／エディタ）を一体で扱う。
   - 既存の静的HTML/Vercel配信は当面維持してよいが、レポート工房本体は Cloud Run 上の FastAPI とする。
   - `draft_markdown` / `final_markdown` は再現性・差分・承認基準のための中間成果物として保存するが、通常運用ユーザーにMarkdown直編集を要求しない。主編集対象は配布面プレビュー/HTML側とする。

4. **セキュリティ**
   - サービスアカウント鍵や OpenRouter API キーをフロントへ置かない。
   - PIIをログへ生出力しない。
   - ソーススナップショット・生成物・検証結果は保存するが、権限・保持期間・削除ポリシーを必ず設計対象に含める。

5. **HTMX / Auth / 運用境界**
   - レポート工房の通常画面操作は Jinja2 + HTMX のHTMLページまたはHTML断片を返す。`/api/monthly-reports/*` のJSON APIは worker、E2E、管理スクリプト、将来連携用に残すが、通常UIからDOM更新目的で直接叩かない。
   - SSR/HTMXの本番認証は `HTTPOnly`, `Secure`, `SameSite=Lax` Cookie を正とし、POST/PUT/DELETE相当の画面操作にはCSRF対策を設計・実装する。Bearer token検証はE2E・内部API・移行中の互換経路として扱い、最終UI境界にはしない。
   - Supabase RLSを主境界として効かせる方針に寄せる。リクエストごとにユーザーJWT付きSupabase Clientを生成する経路を第一候補とし、service role / direct DB接続は管理処理・worker・移行期の限定用途に閉じる。
   - Cloud Run上の長時間生成は、workerの起動方式、lease timeout、stuck job再claim、再試行上限、冪等性キーを決めてから本番運用へ進める。
   - Google Docs/Sheets由来の本文は信頼済み指示として扱わず、プロンプトインジェクション対策・送付前の人間承認・保持期間削除ジョブ・監視/費用上限を設計対象に含める。

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
- Cloud Run MVPでは staging 環境を必須で用意し、migration、RLS、Google OAuth、OpenRouter、HTML UI smoke、ライブE2Eをstagingで確認する。今回プロジェクトの完了条件はstaging動作確認までで、production昇格は後続とする
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
- 画面操作の成功・失敗レスポンスは、差し替え先にそのまま挿入できるHTML断片を優先する。JSONを受けてフロントJSでDOMを組み立てる設計にはしない。

**UIコンポーネント方針**

- Tailwind CSS + DaisyUIを標準とし、Jinja2 partial / HTMX fragmentへそのまま載せる。
- Alpine.jsはモーダル、タブ、トーストなど局所状態に限定する。
- FlowbiteはMVP標準依存にしない。DaisyUIで不足した場合のみ個別採用を判断する。
- 業務画面はtable/section中心にし、カードはジョブ・検証項目・フィードバックなど繰り返し単位に限定する。
- HTMX error fragmentはDaisyUI `alert` 系で返し、長文プレビューはカードではなく読み物領域として扱う。

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
- UI fragment と JSON API の境界が分かるか。通常UIはHTML断片、JSON APIはworker/E2E/管理/将来連携用に限定されているか。
- 429、401、403、404、422、500系の扱いがあるか。
- POST系の冪等性、二重送信、再試行、HTMXエラー断片が定義されているか。

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
- 本番UI認証がHTTPOnly/Secure/SameSite Cookie + CSRF対策として定義され、Bearer tokenはUI境界の主方式になっていないか。
- Supabase RLSを主境界として効かせるためのユーザーJWT付きSupabase Client生成方針と、service role/direct DBの限定範囲が明記されているか。
- Cloud Loggingへ本文や生ソースを出さない設計か。
- Cloud Runのタイムアウト、同時実行、メモリ、Secret参照が未決なら未決事項化されているか。
- worker lease、stuck job回収、保持期間削除、監視・費用上限が運用対象に入っているか。

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
- Phase 4: Supabaseポータル統合（今回プロジェクトの完了条件外）

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

## 10. Codex運用ベストプラクティス

この節はOpenAI Codex Best Practicesをレポート工房運用へ落とした常時ルール。詳細手順は `.agents/skills/codex-operational-check/SKILL.md` を使う。

### 10.1 タスク入力の4点セット

大きめの実装・調査・レビューを始める前に、依頼または自分の作業メモを次の4点へ圧縮する。

- Goal: 何を作る/変える/調べるか
- Context: 関連ファイル、正本、エラー、E2E結果
- Constraints: アーキ、セキュリティ、禁止事項、ユーザー指定
- Done when: テスト、E2E、文書更新、受け入れ条件

4点が欠けていても合理的に補える場合は進める。補うと危険な場合だけ、短く質問する。

### 10.2 計画・委任・スレッド

- 認証、DB/RLS、マイグレーション、Cloud Run、複数ファイル横断、曖昧な仕様は調査/計画を先に置く。
- サブエージェントはユーザーが明示的に並行化を求めたときだけ使い、各agentのwrite scopeを分離する。
- 1スレッドは1つの coherent task を原則にする。別テーマへ広がる場合は、handoff/compact/forkを検討する。

### 10.3 Doneの定義

完了報告前に、該当する最小ゲートを通す。

- 実装: focused test → 必要なら広いsuite → diff確認
- UI: HTML断片/画面確認 → 必要ならブラウザ/Playwright
- セキュリティ/認証/RLS: 失敗系と権限境界のテスト
- 文書/計画: 正本、decision-log、development-plan、rules/skillsの整合確認

検証できなかったものは、完了報告で明示する。

### 10.4 反復改善

- 同じ指摘やミスが2回出たら、`agents.md` / `.cursor/rules` / skill のどれへ昇格するか判断する。
- 毎回守る短い原則は `agents.md` または `.cursor/rules`、依頼時に使う手順はskill、安定した定期実行はautomationへ置く。
- MCPや外部connectorは、変化する外部情報を毎回貼り付けている場合にだけ追加を検討する。最初から広げすぎない。

## 11. Phase 1 以降の実装エージェント構成

### 11.1 体制（実装実行）

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

### 11.2 役割の責任境界

- 同一ファイルの同時編集を避ける。`src/eb_app/routers`, `src/eb_app/monthly_reports`, `tests` は担当を固定し、横断変更は実装オーナーの同期確認後に着手する。
- 仕様変更は `decision-log.md` 更新後、影響する設計文書（requirements→api-definition→development-plan）へ同時反映する。
- 実装判断が必要な場合は `agents.md` と `decision-log.md` の優先更新で全体方針を固定する。

## 12. 次の開発優先順（2026-05-19時点）

### 12.1 達成済みとして固定するゲート

- ✅ 通常UI境界は `/monthly-reports/*` のHTMLページ/HTML断片へ寄せる。通常画面から `/api/monthly-reports/*` をDOM更新目的で直接叩かない。
- ✅ HTML actionの第一弾はHTTPOnly/SameSite Cookie + CSRF hidden tokenで守る。Bearer token経路はE2E/内部JSON API/移行互換として残す。
- ✅ Supabase RLS主境界の第一弾として、ユーザーJWT付きSupabase client生成、実DB RLS評価テスト、通常ユーザーJSON読み取りAPIと通常UI一覧のRLS read store優先化まで完了。
- ✅ 達成（2026-05-16、ローカル Supabase + 実 Google OAuth）: `Supabase Auth Google provider` 実トークン取得 → `POST /api/auth/google-oauth/supabase-session` 実接続 → `fetch-google-sources` 実 Google ソース通電 → `run-openrouter` 実 API 通電 → `validation` 記録（`validation_failed` 経路を含む）。詳細は [development-plan.md](docs/monthly-report-workshop/development-plan.md) と [decision-log.md](docs/monthly-report-workshop/decision-log.md) D-059 / D-060
- ✅ 達成（2026-05-17、ライブE2E初succeeded）: 実 Google Docs + 実 OpenRouter + 決定的バリデーションで `status=succeeded`、`draft_markdown` artifact保存、`llm_call_logs` 記録まで到達。`prompt_version` / `template_hash` / `model_report` / `resolved_model_report` / `source_bundle_hash` / `app_version` は全て非null
- ✅ 達成（2026-05-17、E2E画面成功サンプル）: job `mrj_2b15b194636a4457b590e3ef73afa5b2` をRLS/Google OAuth/OpenRouter成功サンプルとして記録。`Gemini メモ` / `Google Meetメモ` 系の配布面語彙チューニングは後続P2-11へ回す。
- ✅ 達成（focused + ライブE2E、2026-05-17）: `/run-openrouter` / `run-mock` / claimed worker完了時に `monthly_report_jobs` の再現性メタを書き戻す。Mock/Postgres focused testとライブE2Eの両方でnull解消を確認済み
- ✅ 一部達成（focused、2026-05-17）: P2-09として `POST /api/monthly-reports/jobs`、`/run-mock`、`/run-openrouter` に `Idempotency-Key` 対応を追加。`monthly_report_idempotency_keys` migrationとPostgres store入口、新規ジョブ作成・生成開始HTML formのhidden keyも追加し、永続冪等性へ進めた。
- ✅ 達成（実DB focused、2026-05-17）: P2-09の `monthly_report_idempotency_keys` migrationをローカル実DBへ適用し、Postgres lookup/remember focused testを通過。
- ✅ 一部達成（focused + 実DB、2026-05-17）: P2-10として `WorkerRunResult` / `WorkerRunStatus` とprovider実行前キャンセル境界を追加。さらに `worker_attempts`, `max_worker_attempts`, `worker_last_claimed_at` migration、stale `running/fetch_sources` 再claim、retryable failureのqueued復帰を実DB focused testで固定。
- ✅ 一部達成（focused、2026-05-17）: P2-11として `Gemini メモ` / `Google Meetメモ` / Google生成メモ系の配布面メタ語彙をdraft artifact側で狭くsanitizationし、source evidence内の同語彙は許容する。
- ✅ 一部達成（focused、2026-05-17）: P1-15として `eb_auth_session` HTTPOnly Cookieから検証済みSupabase JWTを受ける移行ブリッジを追加。Bearer token互換はE2E/内部JSON向けに維持する。
- ✅ 一部達成（focused、2026-05-17）: P3-01/P3-02として詳細画面に編集後Markdown保存と再生成のHTMXフォーム/backend routeを追加。編集後Markdownは `final_markdown` artifactとして保存し、再生成は新しいqueued jobのstatus fragmentを返す。
- ✅ 一部達成（focused、2026-05-17）: P1-16第五弾として通常HTML UIのGET detail/status/preview/sources/validation fragment読み取りをRLS read store優先へ移行し、編集後Markdown保存、再生成、source保存、Google source取得、feedback保存、生成開始の主要HTML write actionへRLS read preflight認可を追加。full RLS write化は後続。
- ✅ 達成（focused、2026-05-16）: ES256/RS256 JWKS 検証経路の focused test を追加し、既存 HS256 テストとの併走で回帰を防ぐ
- ✅ 達成（focused、2026-05-17）: 通常HTML UIから `POST /monthly-reports/jobs/{job_id}/fragments/google-sources` でGoogle Docs/Sheetsを取得し、sources fragmentを差し替える。通常画面から `/api/monthly-reports/*` をDOM更新目的で直接叩かない
- ✅ 達成（Playwright、2026-05-17）: detail画面の押せる/押せない制御、共通ローディング、Google source表示、空Sheets URL時のリクエスト抑止、Sheets URL入力時のsheet-selector成功を実ブラウザ相当で確認。`tests/test_monthly_report_playwright_smoke.py` を追加し、通常はskip、`MONTHLY_REPORT_PLAYWRIGHT_SMOKE=1` + `MONTHLY_REPORT_JOB_ID` でローカルライブスモークを実行できる。
- ✅ 達成（focused、2026-05-17）: P3-06/P3-12として通常UIに `POST /fragments/approval` と `POST /fragments/export` を追加。承認はCSRF、RLS read preflight、Idempotency-Key、生成成功、validation errorなし、最新配布artifact hash一致を要求し、HTML exportは現行承認がある場合のみ `export_html` artifactを作成する。
- ✅ 達成（CI/docs、2026-05-17）: P2-13として `.github/workflows/monthly-report-operational-guardrails.yml` を追加。PR/pushでは実Secretなしでmigration危険操作、RLS policy存在、schema/PII/logging/worker entry focused testを実行し、Cloud Run smokeは手動dispatch + repository secret時だけ実行する。
- ✅ 一部達成（focused、2026-05-17）: P1-11としてジョブ一覧・詳細・プレビューの実運用導線を強化。次の操作、source/artifact件数、最新artifact、validation error、承認/export状態、ショートカット、preview artifact種別、編集欄prefillを通常UIへ追加。
- ✅ 一部達成（focused、2026-05-17）: P3-01/P3-02としてプレビュー/編集を2ペイン化し、`final_markdown` 優先表示、未保存変更、base hash、保存済み/ドラフト状態を通常UIへ追加。
- ✅ 一部達成（focused、2026-05-17）: P1-14として通常HTML UIにキャンセルactionを追加。CSRF、RLS read preflight、Idempotency-Keyを必須にし、queued/runningのみキャンセル可能にした。
- ✅ 一部達成（focused、2026-05-17）: P3-03として新規ジョブ作成と再生成フォームにadmin限定の `prompt_version` / `model_report` / `model_light` overrideを追加。一般ユーザーの直接投稿値は破棄し、再生成比較fragmentで変更メタを確認できる。
- ✅ 一部達成（focused + Playwright、2026-05-17）: P3-10として自己完結Playwright smokeを、手動source保存→mock生成→final Markdown保存→承認→HTML export→リロード復元→distribution package固定→rerun comparisonまで拡張済み。残りは実Google取得/要約を含むライブE2E。
- ✅ 一部達成（focused、2026-05-17）: P3-11として既存 `monthly_report_full_editor.html` を同一オリジンで開く互換routeと、最新 `export_html` artifactをlocalStorageへ投入して既存全文エディタを開くbridgeを追加。
- ✅ 一部達成（focused + Playwright、2026-05-17）: P3-13として承認/export/html source/distribution panelを定期pollingから `monthly-report-refresh` イベント更新へ変更し、共通 `htmx-error-banner` と編集保存のstale base hash 409 conflictを追加。
- ✅ 達成（focused + Playwright、2026-05-19）: P3-12として approval / export / HTML source edit / distribution package の server-side 監査ログを追加し、artifact write は RLS write store、audit は direct store へ分離した。さらに管理者/一般ユーザーのチューニング欄表示差分を self-contained Playwright で固定し、承認/export/distribution の状態遷移を focused + Playwright で確認済み。
- ✅ 一部達成（Playwright、2026-05-19）: P3-14として detail 画面の workflow board / summary / quick nav / operation log / sources / preview / validation / approval / advanced compare / distribution の連続 UI 確認を self-contained Playwright で追加し、主要パネルの空状態・再読込復元・HTML fragment 更新が崩れないことを確認した。
- ✅ 一部達成（focused、2026-05-17）: P2-09としてvalidation保存にも `Idempotency-Key` を追加し、同一キー再送時にvalidationを二重登録しない。
- ✅ 一部達成（focused、2026-05-17）: P2-10としてlease指定時のprovider call中best-effort heartbeat、後段stageの自動再claim禁止、`manual_recovery_required` summary、worker entry runbookを固定。
- ✅ 一部達成（unit/docs、2026-05-17）: P2-12として保持期間削除planner/executorと `retention_entry` を追加。既定dry-run、`--delete` 明示、PII-safe JSON summary、監査metadataをsecret不要unit testで固定。
- ✅ 一部達成（focused、2026-05-17）: P3-01/P3-02として再生成時に新しいqueued jobの作成通知と新ジョブ詳細リンクを返し、`rerun-comparison` は同一世帯/同一ユーザーの比較候補をdatalistで選べるようにした。
- ✅ 一部達成（focused + Playwright、2026-05-17）: P3-01/P3-02として `rerun-diff` fragmentを追加し、元/比較先ジョブの最新Markdown本文を行単位で比較できるようにした。active job再生成拒否、同一世帯比較制約、Markdown専用diff、同一Idempotency-Key二重送信ロックもfocused testで固定し、自己完結Playwright smokeにも接続済み。
- ✅ 一部達成（focused、2026-05-17）: P3-13としてrunning中のstatus fragmentに「ページを閉じても処理継続/自動更新/再読み込み復元」を表示し、後段stageで長時間heartbeatがない場合はworker runbook確認を促す。
- ✅ 達成（focused + Playwright、2026-05-18）: P1-11/P3-14として詳細画面のファーストビューをMVP検証ワークベンチから、左サイドバー + 確認ガイド + 折りたたみ式の登録/生成/確認/管理セクションへ整理。自己完結Playwrightと起動中ローカル画面smokeで確認済み。
- ✅ 達成（focused + Cloud Run smoke、2026-05-19）: Cloud Run HTTP smoke用の安全なhealth endpointを `/health` に変更し、ローカル互換として `/healthz` も維持。Cloud Runでは末尾 `z` 系の予約URLにより `/healthz` がGoogle Frontend HTML 404となりrevisionへ到達しないため、staging/prod smokeでは `/health` を使う。`tests/test_health.py` は2件通過。
- ✅ 達成（Playwright live、2026-05-18）: 実Google Docs/Sheets取得 + source summary（実OpenRouter light経路）を通常UIライブsmokeで確認。実入力がある場合のみ `MONTHLY_REPORT_LIVE_GOOGLE_E2E=1` / `MONTHLY_REPORT_LIVE_SOURCE_SUMMARY=1` で実行する。
- ✅ 達成（APIライブE2E、2026-05-18）: job `mrj_d3e6e1e884ba4cb4b44c2c9d2044250b` で実 Google Docs 1件 + Sheets 2件（`student`, `lesson plan`）取得、実 OpenRouter report生成、`status=succeeded`、`draft_markdown` artifact、validation 2件、llm_call 1件、再現性メタ非nullを確認。本文・ソース本文・Secret値は記録しない。
- ✅ 達成（Cloud Run staging、2026-05-19）: image `asia-northeast1-docker.pkg.dev/gen-lang-client-0360012476/monthly-report-workshop/monthly-report-workshop:01c993a-health-20260519` をbuild/pushし、service revision `monthly-report-workshop-staging-00003-mg6` へdeploy。staging smokeは `/health` 200、`/monthly-reports/jobs` 401（未認証として期待通り）、`/auth/google` 200を確認。
- ✅ 達成（Cloud Run Jobs worker smoke、2026-05-19）: worker jobを同imageへ再deployし、smoke execution `monthly-report-worker-staging-fpfks` が成功完了。
- ✅ 達成（staging API live E2E、2026-05-19）: image packaging 漏れで `run-openrouter` が `/app/docs/samples/monthly-reports/monthly_pattern_b_content.template.md` を読めず 500 になることを特定し、`Dockerfile` に template copy を追加。image `asia-northeast1-docker.pkg.dev/gen-lang-client-0360012476/monthly-report-workshop/monthly-report-workshop:01c993a-templatefix-20260519`、service revision `monthly-report-workshop-staging-00004-9vt` へ更新後、seeded real Google OAuth refresh token を使う staging API live E2E job `mrj_b2695817af474330a2eed6b43cc3be00` が `status=succeeded`。Google source 3件、`draft_markdown` artifact 1件、validation 2件、llm_call 1件、`resolved_model=anthropic/claude-4.6-sonnet-20260217` を確認。

### 12.2 次に実装する順番

1. **P1-11/P3-14 UI/UX整理 継続**: 現在の詳細画面はMVP検証ワークベンチ。次は「データソース登録 → 取得内容確認 → 生成 → 編集/承認」の通常業務導線をさらに絞り、一覧/新規作成/詳細のDaisyUI統一、検索/フィルタ、確認すべき項目のガイドを整える。
2. **P3-01/P3-02 編集保存・再生成UI 継続**: 保存後の次アクション導線、再生成比較の見た目調整、実Google取得済みジョブ同士の比較確認を通常UIへ入れる。
3. **P1-16 RLS client化 継続**: source / artifact / feedback / validation / final Markdown までは user-JWT 側へ寄せた。残りの direct DB 用途を worker・admin・migration・retention・audit に限定したまま固定し、通常ユーザー経路に generic direct write を残さない。
4. **P2-10 worker本番化 継続**: Cloud Run Jobsのstaging smokeは成功済み。`manual-recovery/fail` の最小管理入口と monitoring helper script までは追加済み。残りは Cloud Monitoring policy の実反映、通知先設定、必要なら管理操作入口の追加。
5. **P2-14 / P2-12 運用**: monitoring helper script、保持削除 planner / executor / entry の契約までは揃った。残りは alert policy apply、日次token/cost集計、保持削除の実DB dry-run/delete確認、OAuth credential削除の管理入口を入れる。

### 12.2.1 一部完了タスクの管理

- `development-plan.md` の状態を `一部完了` にする場合は、同じ文書の「一部完了タスクの済条件」表へ必ず済条件を1行で追加・更新する。
- 済条件は「残り作業」ではなく、「この確認が通れば状態を `済` に変更してよい」という判定基準として書く。
- ライブE2E、staging smoke、Cloud Run Jobs、RLS実DB、UI Playwrightなど外部状態を含む条件は、検証結果を `verification-log.md` に残してから `済` に変更する。

### 12.2.2 開発期間の目安

- ローカルMVPを手動UIレビューしやすい状態: 2〜4開発日。
- staging投入前のコード準備: Cloud Run service/jobのbuild・deploy・基本smoke、template packaging fix、worker monitoring helper script までは完了。残る外部ブロッカーは browser `/auth/google` 実同意確認の client-side blocker 解消と、Cloud Monitoring policy の実反映。
- stagingでのMVP実証: service smoke / worker smoke / seeded real Google OAuth refresh token による staging API live E2E は完了。browser `/auth/google` 実同意確認は client-side blocker 解消後の追加確認項目。Cloud Monitoring は script apply と通知着弾確認が残る。
- production MVP昇格: 後続 2〜4開発日。
- 指導管理ポータル統合は今回プロジェクトの完了条件外。ポータル本体の要件・DB・権限設計後に別枠で2〜4週間以上を見込む。
- 外部環境なしで進める優先は P1-11/P3-14、P3-01/P3-02、P1-16、P2-09、P3-12。外部環境がないと `済` に上げにくいものは P2-05、P2-06、P2-10、P2-13、P2-14、P3-10。

### 12.2.3 実装終了までの残り

今回スコープで「実装終了」と言えるために、最低限あとこれが揃っていることを正とする。

1. **通常ユーザー経路の残件整理**
   - P1-11/P3-14 と P3-01/P3-02 の仕上げで、一覧/新規作成/詳細/保存/再生成/承認/export の通常導線が迷わず辿れる。
2. **RLS / direct DB 境界の固定**
   - 通常ユーザー経路に generic direct write を残さず、direct DB は worker/admin/migration/retention/audit に閉じる。
3. **運用入口の実反映**
   - `scripts/staging/monthly_report_staging_monitoring.ps1` を使った alert policy / notification channel / runbook URL の実反映。
   - retention の実DB dry-run / delete 確認と、必要なら OAuth credential削除入口の追加。
4. **手動ブラウザ確認**
   - 通常UIの主要導線レビュー。
   - browser `/auth/google` 実同意確認は client-side blocker 解消後の追加確認として扱う。

### 12.2.4 手動ブラウザレビュー開始の目安

あなた側で手動ブラウザレビューを始めてよいタイミングは、次の2段階で考える。

1. **今すぐ始めてよいレビュー**
   - ローカルまたは staging で、一覧/新規作成/詳細/ソース登録/生成開始/preview/validation/編集保存/承認/export の通常導線確認。
   - 2026-05-19時点で service smoke、worker smoke、seeded real Google OAuth refresh token による staging API live E2E は成功済みなので、通常UIの使い勝手レビューはもう始めてよい。
2. **追加で待った方がよいレビュー**
   - browser `/auth/google` の実同意確認。
   - Cloud Monitoring alert の実通知確認。
   - retention の実削除確認。

つまり、**UI/導線レビューはもう開始可**、**運用通知/OAuth実同意の最終レビューは残件反映後**、という整理にする。

### 12.3 並行で進めやすいPhase 2/3タスク

- P2-11の配布面語彙チューニングは、成功サンプルを複数集めてから forbidden / safe replacement / warning に分類する。
- P2-13はsecret不要のCI guardrailまで完了。2026-05-19時点でstaging service smokeとworker smokeは手動確認済み。Cloud Runの `/healthz` はGoogle Frontend 404になるため、manual smoke / staging-prod smokeは `/health` を正とする。
- P2-14はMVP監視runbookを文書化済み。残りはCloud Monitoring alert policy、ログベースmetric、日次token/cost集計、budget guardrail停止手順を実装する。
- P3-10は `tests/test_monthly_report_playwright_smoke.py` を入口にする。自己完結smokeはsource保存からdistribution/rerun comparison/rerun diffまで通過済み。ライブGoogle取得/source summaryも通過済み。CIではskipを既定とし、ライブ確認時だけ `MONTHLY_REPORT_PLAYWRIGHT_SMOKE=1`、`MONTHLY_REPORT_LIVE_GOOGLE_E2E=1`、`MONTHLY_REPORT_JOB_ID`、`MONTHLY_REPORT_GOOGLE_DOC_IDS` / `MONTHLY_REPORT_SHEET_URL`、source summary時のみ `MONTHLY_REPORT_LIVE_SOURCE_SUMMARY=1` を指定する。

### 12.4 環境変数の扱い

- `.env` はローカル実行の正本として扱うが、値をログ・ドキュメント・完了報告へ出さない。必要な場合はキー名と用途だけを共有する。
- Postgres/Supabase込みのfocused testは `EB_MONTHLY_REPORT_DATABASE_URL` が未設定だとskipされる。DB込みで確認する場合は `.env` をプロセス環境へ読み込んでから実行する。
- `EB_MONTHLY_REPORT_PROMPT_VERSION` と `EB_APP_VERSION` は未設定でも既定値で動くが、ライブE2E・Cloud Run・チューニング比較では明示設定を推奨する。
- workerの手動実行・テストでは、他ユーザーや別E2Eのqueued jobを拾わないよう `owner_user_id` filterを指定する。
- 通常HTML UIのGoogle取得は、暫定ローカル経路なら `EB_GOOGLE_WORKSPACE_ACCESS_TOKEN`、本来の保存済みOAuth経路なら `EB_MONTHLY_REPORT_DATABASE_URL` / `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` / `EB_GOOGLE_TOKEN_ENCRYPTION_KEY` が必要。値はログ・文書・完了報告へ出さない。
