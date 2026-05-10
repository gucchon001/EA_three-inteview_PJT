# モック UI の境界（`GET /mock/...`）

FastAPI + Jinja2 + HTMX で仕様を固めるための **モック専用ルート**。本番（Cloud Run）では登録しない。

## 有効化条件

| 環境変数 | 意味 |
|----------|------|
| `EB_ENABLE_MOCK_UI` | `1` / `true` / `yes` / `on`（大小無視）で **のみ** `/mock` ルーターをマウントする。未設定または偽 → **ルーターなし**（`/mock/*` はアプリ未定義として 404）。 |

**推奨**:

- ローカル: `EB_ENABLE_MOCK_UI=1` を付けて起動。
- 本番: 変数を **設定しない**（または明示的に `0`）。必要なら Ingress / リバースプロキシで `/mock` を拒否する二重化も可。

## ルート一覧

**正本は [screen-design.md](screen-design.md) の「画面一覧」表**。コード側の索引と同期するリストは `src/eb_app/fixtures/mock_screens.py` の `MOCK_INDEX`（モック `/mock/` ページもここから生成）。

主なパス（抜粋）: `/mock/dashboard/admin`, `/mock/dashboard/teacher`, `/mock/teachers`, `/mock/teachers/demo`, `/mock/students`, `/mock/students/demo`, `/mock/assignments/demo`, `/mock/reports/monthly`, `/mock/meetings/new`, `/mock/me/todos`, `/mock/settings`, `/mock/import-errors`, `/mock/fragments/admin-alerts`。

## データ

- ビジネスロジックはテンプレート内に持ち込まず、`src/eb_app/fixtures/` の辞書／DTO に近い形を渡す。
- 仕様変更時は **要件 MD を先に更新**し、フィクスチャとテンプレートを追従する（`spec-driven-mock-ui`）。

## 起動例（プロジェクトルート）

```powershell
$env:EB_ENABLE_MOCK_UI='1'
$env:PYTHONPATH='src'
python -m uvicorn eb_app.main:app --reload --host 127.0.0.1 --port 8000
```

ブラウザ: `http://127.0.0.1:8000/mock/`

## 関連

- 見た目のトークン: リポジトリ直下 [DESIGN.md](../../DESIGN.md)
- 要件正本: [docs/requirements/v0.3.md](../requirements/v0.3.md)
