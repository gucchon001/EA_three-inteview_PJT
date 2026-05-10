# Design System: EB塾 指導モニタリング（Web アプリ）

> **ステータス**: 仮置き（Phase 0〜1）。トークンは `frontend-design` スキルに準拠し、モック先行で PO と突き合わせながら更新する。

## 1. Visual Theme & Atmosphere

**Industrial / utilitarian（業務用ユーティリティ）** を基調にする。データ密度は高めだが、ロール別に「いま何をすべきか」が一目でわかることを優先する。教育現場の信頼感（落ち着き・可読性）を損なわないよう、装飾は抑え、**グリッド・タイポ・余白の規則性**で秩序を示す。カジュアルな消費者アプリ感や、テンプレート的な「白＋紫グラデ」の UI は避ける。

## 2. Color Palette & Roles

| 名称 | Hex | 役割 |
|------|-----|------|
| Ink Slate | `#1C2333` | プライマリテキスト・強調ナビ |
| Paper Mist | `#F4F1EC` | メイン背景（軽い暖色で長時間閲覧に耐える） |
| Panel Cloud | `#FFFFFF` | カード・パネル表面 |
| Deep Teal | `#0F5959` | プライマリアクション・キーリンク |
| Deep Teal Hover | `#0A4545` | ホバー時 |
| Accent Amber | `#C27B1A` | 「要対応」「締切接近」など注意喚起（控えめに使用） |
| Rule Line | `#D4CFC4` | 区切り線・ボーダー |
| Text Muted | `#5C6472` | 補助テキスト・メタ情報 |
| Success Fern | `#2E6B4E` | 正常・完了 |
| Warning Ochre | `#B8860B` | 警告 |
| Error Rust | `#A33A2A` | エラー・否認 |

## 3. Typography

（Google Fonts 想定。実装は `base.html` の link とフォントファミリで同期すること。）

- **Display / H1**: **Fraunces**, 600, clamp(1.75rem, 2vw + 1rem, 2.25rem) — 短い画面タイトルのみ。字面に品格、読みやすいセリフ。
- **H2 / セクション**: **Lexend**, 600, 1.25rem — サンセリフでセクション断ち。
- **H3 / カード見出し**: **Lexend**, 500, 1.05rem
- **Body**: **Lexend**, 400, 16px, line-height 1.6 — 表・フォームの主読み字体。
- **Caption / ラベル**: **Lexend**, 500, 0.75rem, letter-spacing 0.02em, uppercase 可（フォームラベルのみ）
- **数値 / 集計**: **Lexend**, 500, tabular-nums を推奨（`font-variant-numeric: tabular-nums`）

※ **Inter / Roboto / Arial を UI のデフォルトにしない**（frontend-design の禁止事項に合わせる）。

## 4. Spacing & Layout

- **Base unit**: 4px
- **スケール**: 4, 8, 12, 16, 24, 32, 48, 64
- **コンテナ最大幅**: 1280px（ダッシュボード）、フォーム詳細は 720px まで絞ることも可
- **グリッド**: 12 カラム想定、ガター 24px（モバイル 16px）
- **Breakpoints**: Mobile `< 640px` / Tablet `640–1024px` / Desktop `> 1024px`

ダッシュボードの**情報優先順位**は `dashboard-first-view-ux` スキルと要件 FR-6 に従う（「自分宛て」を最上段）。

## 5. Component Stylings

- **Primary button**: 角はやや丸（`8px` 前後）—「pill 全面」にはしない。背景 Deep Teal、白文字、ホバーで Deep Teal Hover。
- **Secondary button**: 透明背景、Ink Slate のアウトライン 1px、ホバーで Paper Mist 近接塗り。
- **Card**: 角 8px、背景 Panel Cloud、境界 Rule Line 1px、影は極弱（拡散の薄いシャドウ 1 段のみ）。
- **Input / Select**: 下線のみではなく 1px 境界、フォーカス時 Deep Teal の 2px ring（アクセシビリティ確保）。
- **ナビ**: 左サイドバー想定（Desktop）。アクティブ項目は左ボーダー 3px Deep Teal。
- **Badge / タグ**: 小さめ Pill、補助色は意味に対応（Amber = 締切系）。
- **テーブル**: ゼブラ行は Paper Mist と Panel Cloud の交互、行高はタッチしやすい 44px 以上を目安。

## 6. Motion & Interaction

- **標準**: 150–200ms、ease-out。レイアウトを揺らす animation は避け、色・opacity のみ。
- **HTMX**: スワップ時は短いフェード（`opacity`）に統一し、連打時の体感を悪化させない。
- **Reduced motion**: `prefers-reduced-motion: reduce` ではアニメーションを实质的に無効化。

## 7. Notes & Decisions

- 本ファイルは**唯一のデザイントークン正本**。テンプレート内のハードコード色は、追って CSS 変数（`:root`）へ寄せ、ここと双方向に齟齬が出ないようにする。
- モック（`/mock`）は本番では無効。境界は [docs/web-app/mock-ui-boundary.md](docs/web-app/mock-ui-boundary.md) を参照。
