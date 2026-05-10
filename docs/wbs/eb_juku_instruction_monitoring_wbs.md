# プロジェクト WBS — EB塾 指導モニタリング管理 Web アプリ移行

| 項目 | 内容 |
|------|------|
| 更新日 | 2026-05-10 |
| 起点日 | Phase 0 開始を起点とする（絶対日は PO と調整） |
| 参照 | [PJC](../pjc/eb_juku_instruction_monitoring_charter.md)・[要件 v0.3](../requirements/v0.3.md)・[HANDOFF.md](../../HANDOFF.md) |

成功状態・スコープは [PJC](../pjc/eb_juku_instruction_monitoring_charter.md) と一致。  
**スプレッドシートへ転記する場合**: Agent スキル `wbs` の `references/wbs-structure.md` に従い、Phase 行（B のみ）／中項目（C のみ）／小項目（D のみ）／タスク（E〜L、B〜D 空）の **4 行種** に分割すること。

---

## WBS 本文（Markdown 用フラット表）

| NO | フェーズ | タスク | ステータス | オーナー | 備考 |
|----|----------|--------|------------|----------|------|
| 1 | Phase 0 | PO へ [PO レビューパッケージ](../phase0/PO_REVIEW_PACKAGE.md) を送付し P-1〜P-10 を決裁 | 未着手 | PO | 肝 |
| 2 | Phase 0 | 回答を反映（要件 v0.4 または v0.3 追補、parser-spec §10） | 未着手 | Dev | P-1〜P-6 はパーサーに直結 |
| 3 | Phase 0 | 仕様レビュー参加体制の確定（P-9） | 未着手 | PO | |
| 4 | Phase 0 | PJC 合意（本リポジトリ正本またはスプレッドシート化） | 未着手 | PO / Dev | |
| 5 | Phase 0 | WBS のオーナー・開始／終了日の確定 | 進行中 | Dev | |
| 6 | Phase 0 | Phase 1 前の `fastapi-foundation-design` レビュー | 未着手 | Dev | 非機能・並行性 |
| 7 | Phase 1 | Supabase ローカル・マイグレ・型同期 | 未着手 | Dev | `supabase-local-dev` |
| 8 | Phase 1 | FastAPI スケルトン・CI 下準備 | 未着手 | Dev | |
| 9 | Phase 1 | モック先行（主要画面） | 未着手 | Dev | `spec-driven-mock-ui` |
| 10 | Phase 1 | データモデル＋RLS 設計（teachers / students / slots / monthly_reports / settings） | 未着手 | Dev | RLS は後付け不可想定で同時 |
| 11 | Phase 1 | 招待フロー・users↔teachers 紐付け（72h） | 未着手 | Dev | |
| 12 | Phase 1 | 教師・生徒・指導枠・月次レポート CRUD | 未着手 | Dev | |
| 13 | Phase 1 | system_settings・audit_log・設定画面 | 未着手 | Dev | P-10 決定後に権限分割 |
| 14 | Phase 1 | デフォルトアクティブのみ・過去表示フィルタ | 未着手 | Dev | |
| 15 | Phase 1 | ローカル品質ゲート（lint→typecheck→build→test）運用 | 未着手 | Dev | `local-quality-gate` |
| 16 | Phase 2 | 面談記録・ToDo・タグ検索（FR-5 中心） | 未着手 | Dev | |
| 17 | Phase 2 | 通知（リマインド・ToDo 期限） | 未着手 | Dev | |
| 18 | Phase 2 | 教師契約書 Drive（専用 SA・権限・UI） | 未着手 | Dev / 運用 | |
| 19 | Phase 3 | parser-spec 実装・fixtures 回帰・import_errors | 未着手 | Dev | |
| 20 | Phase 3 | バッチ頻度・dryrun 閾値の実装反映（P-5, P-6） | 未着手 | PO / Dev | |
| 21 | Phase 3 | external_sheet_url・並行運用時の差分監視 | 未着手 | Dev | |
| 22 | Phase 4 | Sheets 凍結・アナウンス・読み取り専用期間・廃止 | 未着手 | PO | HANDOFF 順序 |

---

## 肝タスク（抜け防止）

1. **P-1〜P-6 の PO 決裁**（教師ゆれ・科目・独自列・退職教師・頻度・dryrun）— 未確定のままパーサー実装すると手戻りが大きい。
2. **RLS をデータモデルと同時に設計** — 後付けで漏れが出やすい。
3. **招待メール**（文面・From ドメイン／C-1・P-7）— 運用イメージ・信頼性に直結。

---

## スケール目安（PJC より）

| フェーズ | 目安 |
|----------|------|
| Phase 0 | 約 2 週 |
| Phase 1 | 6〜8 週 |
| Phase 2 | 約 4 週 |
| Phase 3 | 約 12 週 |
| Phase 4 | 約 1 週 |
