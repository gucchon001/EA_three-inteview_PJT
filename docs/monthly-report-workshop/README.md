# 月次レポート作成ツール 開発ドキュメント索引

## 位置づけ

- 正本/補助資料の区分: 月次レポート作成ツール（レポート工房）の開発ドキュメント入口
- 起点: `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md`
- **北極星（自動生成の最終ゴール／POCと工房の接続・非交渉）**: [AUTOMATION_NORTH_STAR.md](AUTOMATION_NORTH_STAR.md)（変更時は [decision-log.md](decision-log.md) も）
- 関連文書: `agents.md`, `docs/samples/monthly-reports/monthly_pattern_b_content.template.md`, `docs/samples/monthly-reports/DATA_CONTRACT_05_学習の進捗.md`, `docs/requirements/v0.3.md`, `docs/web-app/screen-design.md`, `DESIGN.md`
- 最終更新: 2026-05-18（今回プロジェクト完了条件をレポート工房MVP staging環境へ固定）

## 正本スタック

| 優先 | 文書 | 役割 |
|---:|---|---|
| 0 | `docs/monthly-report-workshop/AUTOMATION_NORTH_STAR.md` | ブラウザ完結をゴールとする戦略・アーキ方針（ぶれ防止） |
| 1 | `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md` | 本ツールの最新決定事項 |
| 2 | `docs/samples/monthly-reports/monthly_pattern_b_content.template.md` | 月次レポート本文テンプレート正本 |
| 3 | `docs/samples/monthly-reports/DATA_CONTRACT_05_学習の進捗.md` ほか | レポート内データ契約 |
| 4 | `docs/requirements/v0.3.md` / `docs/web-app/screen-design.md` / `DESIGN.md` | 将来統合先ポータルの要件・UI規約 |
| 5 | 本ディレクトリ | 上記を実装可能な設計文書へ展開したもの |

`docs/project/レポート自動化システム_要件定義.md` は参考資料です。移行計画書と矛盾する場合は移行計画書を優先します。`AUTOMATION_NORTH_STAR.md` と移行計画書の両立ができないときは **[decision-log.md](decision-log.md)** で解決し、両文書と本 README の優先表を同期してください。

## 今回プロジェクトの完了条件

今回の完了条件は、指導管理ポータル統合ではなく **レポート工房MVPがstaging環境で動作すること** とする。具体的には、stagingでHTTP smoke、Cloud Run Jobs worker smoke、RLS、Google OAuth、OpenRouter、HTML UI smoke、ライブE2Eを確認し、[verification-log.md](verification-log.md) に結果を残す。production昇格と指導管理ポータル統合は後続スコープとして扱う。

## 文書一覧

| 文書 | 目的 | 主な読者 |
|---|---|---|
| [HANDOFF_STATIC_POC_TUNING.md](HANDOFF_STATIC_POC_TUNING.md) | **静的 POC／ローカル OpenRouter のチューニング実装を他エージェントへ渡す合流入り口**（パス一覧・build_prompts 順・リスク・U-025） | 別エージェント・Documentation Lead・LLM実装者 |
| [AUTOMATION_NORTH_STAR.md](AUTOMATION_NORTH_STAR.md) | ブラウザ自動生成への北極星・静的 POC と工房の接続・非交渉事項 | 全員・エージェント |
| [requirements.md](requirements.md) | 業務・機能・非機能・制約・成功基準 | PO、設計者、実装者 |
| [workflow-spec.md](workflow-spec.md) | 現行からTo-Beへの業務フロー、ジョブ処理 | PO、実装者 |
| [activity-diagram.md](activity-diagram.md) | 業務・画面・API・ジョブを横断したアクティビティ図 | PO、実装者、QA |
| [functional-spec.md](functional-spec.md) | 機能単位の振る舞い、状態、検証、再生成 | 実装者、QA |
| [screen-design.md](screen-design.md) | 画面、HTMX断片、表示状態、操作導線 | UI実装者 |
| [api-definition.md](api-definition.md) | JSON API / HTML fragment API | バックエンド実装者 |
| [data-design.md](data-design.md) | 永続化、RDB候補、成果物、監査ログ | バックエンド実装者 |
| [llm-design.md](llm-design.md) | OpenRouter、プロンプト、モデル、検証・リペア | LLM実装者 |
| [security-operations.md](security-operations.md) | 認証、認可、PII、Secrets、Cloud Run | インフラ、実装者 |
| [staging-deploy-runbook.md](staging-deploy-runbook.md) | レポート工房MVPをstaging環境へ出すためのCloud Run/Secret/IAM/smoke準備 | インフラ、実装者、QA |
| [rls-direct-db-audit.md](rls-direct-db-audit.md) | RLS主境界とdirect DB許可範囲の棚卸し、P1-16次スライス | バックエンド実装者、セキュリティ担当 |
| [pre-e2e-setup.md](pre-e2e-setup.md) | 実Supabase Auth + Google OAuth + Google Workspace read flowのE2E前設定 | インフラ、実装者、QA |
| [test-plan.md](test-plan.md) | テスト方針、ゴールデンフィクスチャ、受け入れ | QA、実装者 |
| [development-plan.md](development-plan.md) | 現在のロードマップ、次優先、フェーズ、WBS、完了条件 | PO、開発者 |
| [development-history.md](development-history.md) | `development-plan.md` から分離した詳細な進捗ログ・改訂履歴 | PO、開発者、引き継ぎ担当 |
| [verification-log.md](verification-log.md) | `development-plan.md` から分離した検証コマンド履歴 | QA、実装者 |
| [decision-log.md](decision-log.md) | 決定事項、未決事項、変更履歴 | 全員 |

## 更新ルール

- 要件・仕様・API・データ・画面の変更は、関連文書と [decision-log.md](decision-log.md) を同時に確認する。
- APIを変更したら [api-definition.md](api-definition.md) と [functional-spec.md](functional-spec.md) を同時更新する。
- 画面やHTMX断片を変更したら [screen-design.md](screen-design.md) と [api-definition.md](api-definition.md) を同時更新する。
- P2/P3の実装進捗を更新したら [development-plan.md](development-plan.md), [development-history.md](development-history.md), [verification-log.md](verification-log.md), [agents.md](../../agents.md), [test-plan.md](test-plan.md), [decision-log.md](decision-log.md) の重複ステータスを同時確認する。
- DB・保存項目を変更したら [data-design.md](data-design.md), [security-operations.md](security-operations.md), [test-plan.md](test-plan.md) を確認する。
- 開発フェーズや完了条件を変更したら [development-plan.md](development-plan.md) と [decision-log.md](decision-log.md) を更新する。
