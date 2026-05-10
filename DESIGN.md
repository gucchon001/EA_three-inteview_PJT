# Design System: EB塾 指導モニタリング（Web アプリ）

> **ステータス**: 仮置き（Phase 0〜1）。トークンは **Agent Skill `frontend-design`**（＋本番 UI 確認時 **`ui-frontend-patterns`**）に準拠。モック先行で PO と突き合わせながら更新する。

## 1. Visual Theme & Atmosphere

**Cool utilitarian（クール・ユーティリティ）** — *Industrial* をベースに、「教育現場の信頼感」と「一日中見ても疲れない明快さ」を両立する。  
「クール」は **グラデ乱用やテンプレ UI** ではなく、**締まったタイポ階層・深いティール基調・アクセント一本化・紙のような背景**で表現する。データ密度は高めにできるが、**ファーストビューでは `dashboard-first-view-ux` に従い「自分宛て・アラート」を最上段**に置く。

禁止: Inter/Roboto 依存、白地×紫グラデの汎用ダッシュ、装飾のための装飾。

## 2. Color Palette & Roles

| 名称 | Hex | 役割 |
|------|-----|------|
| Ink Slate | `#1C2333` | プライマリテキスト・強調ナビ |
| Paper Mist | `#F4F1EC` | メイン背景（軽い暖色で長時間閲覧に耐える） |
| Panel Cloud | `#FFFFFF` | カード・パネル表面 |
| Deep Teal | `#0F5959` | プライマリ CTA・キーリンク・アクティブボーダー |
| Deep Teal Hover | `#0A4545` | ホバー時 |
| Teal Muted Surface | `rgba(15, 89, 89, 0.08)` | サイドバーアクティブ行・控えたハイライト |
| Accent Amber | `#C27B1A` | 「要対応」「締切接近」（**支配はティール、アンバーは意味があるときだけ**） |
| Rule Line | `#D4CFC4` | 区切り線・ボーダー |
| Text Muted | `#5C6472` | 補助テキスト・メタ情報 |
| Success Fern | `#2E6B4E` | 正常・完了 |
| Warning Ochre | `#B8860B` | 警告 |
| Error Rust | `#A33A2A` | エラー・否認 |

## 3. Typography

（Google Fonts 想定。実装は `base.html` の link とフォントファミリで同期すること。）

- **Display / H1**: **Fraunces**, 600, clamp(1.75rem, 2vw + 1rem, 2.25rem) — 短い画面タイトルのみ。
- **H2 / セクション**: **Lexend**, 600, 1.25rem
- **H3 / カード見出し**: **Lexend**, 500, 1.05rem
- **Body**: **Lexend**, 400, 16px, line-height 1.6
- **Caption / ラベル**: **Lexend**, 500, 0.75rem, letter-spacing 0.02em（ラベルは uppercase 可）
- **数値 / 集計**: **Lexend**, 500, `font-variant-numeric: tabular-nums`

※ **Inter / Roboto / Arial を UI のデフォルトにしない**。

## 4. Spacing & Layout

- **Base unit**: 4px
- **スケール**: 4, 8, 12, 16, 24, 32, 48, 64
- **コンテナ最大幅**: 1280px（ダッシュボード）、フォーム詳細は 720px まで可
- **Breakpoints**: Mobile `< 640px` / Tablet `640–1024px` / Desktop `> 1024px`
- **タッチターゲット**: サイドナビ行・主要ボタンは **最低 44px 相当**（`ui-frontend-patterns`）

## 5. Component Stylings

- **グローバルバー**: 表面 Panel Cloud、**下縁にティールの極細エッジ**（スキン深度・方向感）。
- **ブランドマーク**: 小さな円点＋ソフトグロー（ロゴ画像なしでも**想起点**を作る）。
- **Primary button**: 角 8px、Deep Teal 充填、白文字、ホバー Deep Teal Hover。
- **Secondary button**: 透明＋ Ink アウトライン 1px。
- **Card**: 角 8px、境界 Rule Line、影は **ティール寄りの極弱二層**（浮きすぎない）。
- **Input / Select**: 1px 境界、**`:focus-visible` で 2px のティール系リング**（WCAG のキーボード可視性）。
- **ナビ（サイド）**: アクティブは左 3px Deep Teal ＋ Teal Muted Surface 背景。
- **テーブル**: ゼブラ行、行高 ≥ 44px 目安。

## 6. Motion & Interaction

- **標準**: 150–200ms、ease-out。色・opacity のみ（レイアウトシフト禁止）。
- **HTMX**: スワップは短い opacity に統一。
- **Reduced motion**: `prefers-reduced-motion: reduce` で実質無効化。

## 7. Notes & Decisions

- 本ファイルは**唯一のデザイントークン正本**。未登録の色・フォント・radius を増やさない（`frontend-design` Phase 3 チェックリスト）。
- モック境界: [docs/web-app/mock-ui-boundary.md](docs/web-app/mock-ui-boundary.md)
- 画面 IA: [docs/web-app/screen-design.md](docs/web-app/screen-design.md)

## 8. Agent Skills（このリポジトリでの使い分け）

| スキル | 使う場面 |
|--------|----------|
| **frontend-design** | DESIGN.md・美的方向性・トークン・新規コンポーネントの作り込み |
| **ui-frontend-patterns** | 既存モックの軽量レビュー（コントラスト・CTA・フォーカス） |
| **dashboard-first-view-ux** | ダッシュ・トップの情報順、「自分宛て」最上段 |
| **spec-driven-mock-ui** | Jinja + HTMX モックと要件正本の同期 |
- グローバル **誘導** | 本リポ `.cursor/skills/eb-juku-portal-ui`（**FastAPI + Jinja + HTMX**。React / shadcn 前提の汎用記事は**そのまま流用しない**） |

## 9. 改訂履歴

| 日付 | 内容 |
|------|------|
| 2026-05-10 | Cool utilitarian 方針、トークン追記、`ui-frontend-patterns`・Skills マッピング |
