# 関連スキル・サブワークフロー対応表

## 本スキル（プロジェクト）

- **monthly-report-notebooklm-patterns**（`.cursor/skills/monthly-report-notebooklm-patterns/`）  
  本リポジトリの `samples/reports`・`scripts`・`docs/project` を前提とした **エンドツーエンド手順**。

## グローバルスキル（汎用・ここから参照）

NotebookLM の接続・CLI・MCP 登録など **リポジトリに依存しない**内容は、ユーザーの **グローバル SKILLS_ROOT**（例: `~/.cursor/skills/`）にあるスキルを正とする。

| スキル | 役割 |
|--------|------|
| **notebooklm-mcp** | MCP インストール、認証、`source_get_content` の前提 |
| **skill-builder** | 手順を別スキルに切り出す・スキャフォールド |
| **skill-growing** | スキル改修・分割・description 更新 |
| **frontend-design** | Pattern の大幅な視覚リニューアル（任意） |

## プロジェクト内ドキュメント（リポジトリ相対）

- `docs/project/月次レポート生成ワークフロー.md`: スコープ・3ソース・品質ゲート
- `scripts/notebooklm_json_to_txt.py`: JSON から md 出力
- `scripts/serve_project.py`: 静的配信・UTF-8

## 分割の目安（将来）

取得のみは **notebooklm-mcp** に寄せる。HTML テンプレ同期だけを別スキルに分けるのは、Pattern 差分が安定してからがよい。
