# DOCUMENTATION_LIFECYCLE

## 位置づけ

- 正本/補助資料の区分: 本リポジトリのドキュメント更新ルール
- 起点: `docs/README.md`, `agents.md`
- 関連文書: `docs/monthly-report-workshop/README.md`
- 最終更新: 2026-05-13

## 正本スタック

| 優先 | 対象 | 役割 |
|---:|---|---|
| 1 | `docs/README.md` | docs全体の入口 |
| 2 | `docs/monthly-report-workshop/README.md` | 月次レポート作成ツールの開発ドキュメント入口 |
| 3 | `docs/project/月次レポート_プログラム化_LLMワークフロー移行計画.md` | レポート工房の最新決定事項 |
| 4 | `docs/requirements/v0.3.md` | 指導管理ポータル全体の既存要件 |
| 5 | `HANDOFF.md` | 次スレッド・次作業への引き継ぎ |

## 更新トリガー

| 文書 | 更新タイミング | トリガー種別 |
|---|---|---|
| `docs/README.md` | docs配下に新カテゴリを追加したとき | event |
| `docs/monthly-report-workshop/README.md` | レポート工房の設計文書を追加・削除したとき | event |
| `docs/monthly-report-workshop/requirements.md` | スコープ、MVP、非機能、成功基準が変わったとき | event |
| `docs/monthly-report-workshop/workflow-spec.md` | 業務フロー、ジョブ段階、例外フローが変わったとき | event |
| `docs/monthly-report-workshop/functional-spec.md` | 機能の振る舞い、状態、検証方針が変わったとき | event |
| `docs/monthly-report-workshop/screen-design.md` | 画面、URL、HTMX fragmentが変わったとき | event |
| `docs/monthly-report-workshop/api-definition.md` | API、レスポンス、エラー、認可が変わったとき | event |
| `docs/monthly-report-workshop/data-design.md` | 保存項目、テーブル、保持方針が変わったとき | event |
| `docs/monthly-report-workshop/llm-design.md` | モデル、prompt_version、プロンプト構成が変わったとき | event |
| `docs/monthly-report-workshop/security-operations.md` | 認証、Secrets、PII、Cloud Run設定が変わったとき | event |
| `docs/monthly-report-workshop/test-plan.md` | テスト、フィクスチャ、品質ゲートが変わったとき | event |
| `docs/monthly-report-workshop/development-plan.md` | フェーズ、WBS、状態、完了条件が変わったとき | milestone |
| `docs/monthly-report-workshop/decision-log.md` | 決定・未決事項が増減したとき | event |
| `HANDOFF.md` | 作業状態や次アクションを引き継ぐとき | milestone |

## 周期レビュー

| 周期 | 内容 |
|---|---|
| スプリント開始時 | `development-plan.md` と `decision-log.md` の未決事項を確認 |
| MVP実案件投入後 | `requirements.md`, `llm-design.md`, `test-plan.md` を実運用結果で更新 |
| 本番デプロイ前 | `security-operations.md`, `api-definition.md`, `test-plan.md` を確認 |

## 横断更新ルール

- API変更時は `api-definition.md`, `functional-spec.md`, `screen-design.md` を同時確認する。
- 画面変更時は `screen-design.md`, `api-definition.md`, `test-plan.md` を同時確認する。
- DB保存項目変更時は `data-design.md`, `security-operations.md`, `test-plan.md` を同時確認する。
- LLMモデル・プロンプト変更時は `llm-design.md`, `data-design.md`, `test-plan.md`, `decision-log.md` を同時確認する。
- フェーズやマイルストーン変更時は `development-plan.md`, `decision-log.md`, `HANDOFF.md` を確認する。

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-13 | 初版作成 |

