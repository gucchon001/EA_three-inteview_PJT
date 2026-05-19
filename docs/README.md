# docs フォルダ構成

プロジェクト関連ドキュメントを用途ごとに分けています。

| フォルダ | 内容 |
|----------|------|
| **`project/`** | プロジェクト正本：計画概要、PJC、WBS、要件定義、セキュリティ、技術タスク、課題一覧 JSON、**月次レポート生成ワークフロー**など |
| **`monthly-report-workshop/`** | **月次レポート作成ツール（レポート工房）**の開発ドキュメント：要件、仕様、画面、API、データ、LLM、セキュリティ、テスト、開発計画 |
| **`requirements/`** | **指導管理ポータル**の要件定義。レポート工房とは別プロジェクトとして管理し、後段で統合する |
| **`web-app/`** | 指導管理ポータルの画面設計・モック境界 |
| **`sheets-migration/`** | 指導管理ポータルへ移行する既存管理表の抽出・正規化・パーサー仕様 |
| **`instruction-portal-transfer/`** | 指導管理ポータルを別プロジェクトへ移管する計画 |
| **`meetings/raw/`** | 会議の**取り込み原本**（Gemini メモの md/json など）。`scripts/fetch-docs-interview.mjs` の出力先 |
| **`meetings/minutes/`** | **整理済み議事録**（週次など、編集・要約したテキスト） |
| **`reference/`** | **参考資料**：ワークフロー比較、ヒアリングワークシートなど（計画本体ではない補助資料） |
| **`samples/notebooklm-reports/`** | NotebookLM / GDoc から落とした**レポート出力サンプル・テンプレ**（`scripts/download_reports.py` の出力先） |

## 運用メモ

- 新しい Gemini 取り込み → `meetings/raw/`、定例の清書 → `meetings/minutes/`。
- 仕様・マイルストーンの一次情報 → `project/`。
- 月次レポート作成ツールの実装向け設計 → `monthly-report-workshop/`。
- 指導管理ポータルの要件・画面・Sheets/BigQuery移行仕様 → `requirements/`, `web-app/`, `sheets-migration/`。
- 指導管理ポータルを別プロジェクトへ切り出す作業 → `instruction-portal-transfer/`。
- 生徒別・分析系の大量サンプルは `samples/notebooklm-reports/` に集約（本番仕様書と混ぜない）。

## ドキュメントライフサイクル

- 本リポジトリのドキュメント更新ルールは [DOCUMENTATION_LIFECYCLE.md](DOCUMENTATION_LIFECYCLE.md) を参照。
