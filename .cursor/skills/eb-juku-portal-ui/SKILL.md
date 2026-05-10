---
name: eb-juku-portal-ui
description: "EB塾指導管理ポータル（FastAPI+Jinja2+HTMX）のUI。DESIGN.md と docs/web-app/screen-design.md を正本にし、frontend-design・dashboard-first-view-ux・ui-frontend-patterns・spec-driven-mock-ui を併用。React/shadcn 前提の汎用塾テンプレは流用せず本スタックへ落とす。Triggers: EB塾 UI, 指導管理ポータル, モック Jinja, screen-design, 塾 管理画面デザイン."
---

# EB塾 指導管理ポータル UI（本プロジェクト）

## 正本

| 優先 | パス |
|------|------|
| トークン・トーン | リポジトリ直下 [DESIGN.md](../../../DESIGN.md) |
| 画面・IA・モック URL | [docs/web-app/screen-design.md](../../../docs/web-app/screen-design.md) |
| `/mock` 境界 | [docs/web-app/mock-ui-boundary.md](../../../docs/web-app/mock-ui-boundary.md) |
| ナビ組み立て（モック） | `src/eb_app/fixtures/portal_frame.py` |
| 共通シェル | `src/eb_app/templates/mock/base.html` |

## グローバルスキル（Read してから実装）

1. **frontend-design** — DESIGN.md 未登録の色・フォントを増やさない。Cool utilitarian（紫グラデ禁止等）。
2. **dashboard-first-view-ux** — ダッシュで「自分宛て・アラート」を上に。
3. **ui-frontend-patterns** — コントラスト・CTA・`:focus-visible`・44px タッチ目安。
4. **spec-driven-mock-ui** — 要件を先に直し、モックとテストを追従。

## スタック注意

- 本番想定: **FastAPI + Jinja2 + HTMX**（要件 v0.3）。Next.js 用のスキルだけを鵜呑みにしない。
- モックは `EB_ENABLE_MOCK_UI=1` のときのみ `/mock` を有効化。

## 手順（短縮）

1. `DESIGN.md` のトークンを確認 → `base.html` の `:root` と整合。
2. 新画面は `screen-design.md` の SCR ID → `mock_screens.MOCK_INDEX` → `portal_frame._nav_groups` を必要なら更新。
3. 仕様変更は要件 MD 先行。
