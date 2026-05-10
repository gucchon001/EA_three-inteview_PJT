# 画面設計書（Phase 1 MVP）

> **正本の位置づけ**: 要件 [v0.3 §6 画面・URL設計](../requirements/v0.3.md) を分解・追記したもの。レイアウト・コンポーネントの詳細は本書と [DESIGN.md](../../DESIGN.md) を併用。モック URL は `EB_ENABLE_MOCK_UI=1` 時のみ（[mock-ui-boundary.md](mock-ui-boundary.md)）。

**更新ルール**: 画面を追加・変更したら、(1) 本表を更新 (2) `src/eb_app/fixtures/mock_screens.py` の `MOCK_INDEX` を同期 (3) モックルート・テンプレ・テストを追従。

---

## 1. 全体方針

| 項目 | 内容 |
|------|------|
| 技術 | FastAPI + Jinja2 + HTMX（部分更新はテーブル行・モーダル・タブ単位） |
| ロール | 管理者 / 教師 / 経理（閲覧中心）— [v0.3 §2](../requirements/v0.3.md) |
| IA | ダッシュは **「自分宛て」最上段**（[FR-6.3](../requirements/v0.3.md)／`dashboard-first-view-ux`） |
| 一覧 | **デフォルトはアクティブのみ**、「過去分も表示」で HTMX 再フェッチ（[FR-11](../requirements/v0.3.md)） |
| 並行運用 | 各画面で `external_sheet_url` があるときのみ「元のシートを開く」（[FR-8.3](../requirements/v0.3.md)） |

---

## 2. 画面一覧（本番 URL・要件対応）

| ID | 画面名 | 主ロール | 本番 URL（案） | 対応要件 | モック URL | モック状態 |
|----|--------|----------|----------------|----------|------------|------------|
| SCR-L01 | ログイン／招待受諾 | 全員 | Supabase Hosted UI 経由 | FR-1.6〜1.8 | ※後日 | ☐ |
| SCR-D01 | ダッシュボード | 管理者 | `/`（admin 時） | FR-6.1, 6.3 | `/mock/dashboard/admin` | ☑ 一部 |
| SCR-D02 | ダッシュボード | 教師 | `/`（teacher 時） | FR-6.2, 6.3 | `/mock/dashboard/teacher` | ☑ スタブ |
| SCR-T01 | 教師一覧 | 管理者 | `/teachers` | FR-1 | `/mock/teachers` | ☑ スタブ |
| SCR-T02 | 教師詳細・編集 | 管理者 | `/teachers/{id}` | FR-1, F-1.3 | `/mock/teachers/demo` | ☑ スタブ |
| SCR-T03 | 契約書（Drive） | 管理者・経理 | `/teachers/{id}/contract` | FR-10 | ※Phase 2 寄り | ☐ |
| SCR-S01 | 生徒一覧 | 管理者・教師※ | `/students` | FR-2 | `/mock/students` | ☑ スタブ |
| SCR-S02 | 生徒詳細 | 管理者・教師※ | `/students/{id}` | FR-2 | `/mock/students/demo` | ☑ スタブ |
| SCR-A01 | 指導枠詳細＋月次 | 管理者・教師※ | `/students/{id}/assignments/{selection_no}` | FR-3, 4 | `/mock/assignments/demo` | ☑ スタブ |
| SCR-R01 | 月次レポート一覧 | 管理者 | `/reports/monthly?ym=` | FR-4 | `/mock/reports/monthly` | ☑ スタブ |
| SCR-M01 | 面談記録（登録） | 管理者・教師※ | `/meetings/new?student_id=` | FR-5 | `/mock/meetings/new` | ☑ スタブ |
| SCR-U01 | 自分宛 ToDo | 管理者・教師 | `/me/todos` | FR-5.3, 7.2 | `/mock/me/todos` | ☑ スタブ |
| SCR-C01 | システム設定 | 管理者 | `/settings` | FR-9 | `/mock/settings` | ☑ スタブ |
| SCR-I01 | 取込エラー一覧 | 管理者 | `/import-errors`（案） | FR-8.7 | `/mock/import-errors` | ☑ スタブ |
| SCR-X01 | 断片: 管理者アラート | 管理者 | —（HTMX） | FR-6.1 | `/mock/fragments/admin-alerts` | ☑ |

※教師・経理の列レベル閲覧制限は RLS／要件 FR 参照。経理向け専用ダッシュは Phase 1 では `/` 共有または一覧から遷移で代替可（要 PO 確認）。

---

## 3. 画面別メモ（追記用）

### SCR-D01 / SCR-D02 ダッシュボード

| ブロック（上→下） | 管理者 | 教師 |
|-------------------|--------|------|
| 1 | 未提出月次／充足率異常／面談関連のサマリー | **自分宛て・今月締切・ToDo** |
| 2 | 直近アラート一覧（HTMX 断片可） | 担当スロット一覧への導線 |
| 3 | ショートカット（教師・生徒・レポート） | 同上 |

### SCR-T01 教師一覧

- 列: v0.3 F-1.2 を参照。フィルタ: アクティブのみ既定、検索（氏名・メール）。
- 行アクション: 詳細、招待再送（`invited` 時）。

### SCR-S01 生徒一覧

- 教師ロール時は **自担当生徒のみ**（サーバ側フィルタ）。

### SCR-A01 指導枠詳細

- 上部: 選考番号・科目・契約時間・教師。下部: **月次タイムライン**（年月 × 実施・充足率・提出）。

### SCR-C01 設定

- 鍵: `monthly_report_deadline`, `fulfillment_rate_warn`, `reminder_days_before`, `parallel_operation` 等。変更は `audit_log`（FR-9.3）。

---

## 4. HTMX 断片（初期）

| 断片 ID | 親画面 | GET（モック） | 用途 |
|---------|--------|---------------|------|
| FMT-A01 | SCR-D01 | `/mock/fragments/admin-alerts` | 管理者向けアラートブロックの差し替え |

---

## 5. 改訂履歴

| 日付 | 内容 |
|------|------|
| 2026-05-10 | 初版。MVP 画面の本番 URL 案・モック URL・SCR ID を定義。 |
