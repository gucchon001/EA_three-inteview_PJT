# モック UI の境界（`GET /mock/...`）

FastAPI + Jinja2 + HTMX で仕様を固めるための **モック専用ルート**。本番（Cloud Run）では登録しない。

## 有効化条件

| 環境変数 | 意味 |
|----------|------|
| `EB_ENABLE_MOCK_UI` | `1` / `true` / `yes` / `on`（大小無視）で **のみ** `/mock` ルーターをマウントする。未設定または偽 → **ルーターなし**（`/mock/*` はアプリ未定義として 404）。 |

**推奨**:

- ローカル: `EB_ENABLE_MOCK_UI=1` を付けて起動。
- 本番: 変数を **設定しない**（または明示的に `0`）。必要なら Ingress / リバースプロキシで `/mock` を拒否する二重化も可。

## ルート一覧（初期スキャフォールド）

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/mock/` | モック索引・ルート説明 |
| GET | `/mock/dashboard/admin` | 管理者ダッシュボード（フィクスチャデータ） |
| GET | `/mock/fragments/admin-alerts` | HTMX 用アラート断片（`HX-Request` 想定のサンプル） |

今後、教師ビュー・生徒一覧・月次レポートなどは **`/mock/<ロール>/<画面>`** のように増やし、同ファイルの表を更新する。

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
