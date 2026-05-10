# HANDOFF — EB塾 指導管理 Web アプリ移行

> 新しいチャット／別エージェントは、このファイルを `@HANDOFF.md` で添付し、「続き」と一言添えれば再開できる。

## メタ

| 項目 | 値 |
|---|---|
| 最終更新 | 2026-05-10 |
| ブランチ | `main` |
| プロジェクト | `c:\dev\CODE\EA_three-inteview_PJT` |
| 関係者 | PO: 原口（y-haraguchi@tomonokai-corp.com）／ 元山・藤井 |

---

## 目的

EB塾（オンライン塾）で運用中の Google Sheets「★新【EB塾】【2026年度】指導モニタリング管理表」（37タブ規模で限界）を、**FastAPI + Jinja2 + HTMX + Supabase + Cloud Run** スタックの Web アプリへ移行する。

---

## 状態

### 完了

- ✅ **要件定義 v0.3**: PO 回答を全面反映済み — [docs/requirements/v0.3.md](docs/requirements/v0.3.md)
- ✅ **Phase -1（Sheets パターン抽出）**: 全成果物揃い — [docs/sheets-migration/README.md](docs/sheets-migration/README.md)
  - 全 38 タブのフルスナップショット（[docs/sheets-migration/sample-extracts/](docs/sheets-migration/sample-extracts/)）
  - ブロックアンカー仕様（[docs/sheets-migration/anchors.md](docs/sheets-migration/anchors.md)）
  - 表記ゆれ正規化ルール（[docs/sheets-migration/normalization-rules.md](docs/sheets-migration/normalization-rules.md)）
  - パーサー仕様書 v0.1（[docs/sheets-migration/parser-spec.md](docs/sheets-migration/parser-spec.md)）
  - インベントリ・バリアント抽出（[docs/sheets-migration/tab-inventory.csv](docs/sheets-migration/tab-inventory.csv) / [docs/sheets-migration/variants.json](docs/sheets-migration/variants.json)）
  - 調査スクリプト一式（[scripts/sheets-survey/](scripts/sheets-survey/)）
- ✅ **NotebookLM ノート整備**: 「EA_生徒状況分析」に対象スプレッドシートをソース追加済み（notebook_id: `8d0e1e72-2137-485e-a524-826ba11d359c`）

### 未完了 / 次

優先度順:

1. **Phase 0: 設計確定**（2週想定）
   - PO レビュー: [docs/sheets-migration/parser-spec.md](docs/sheets-migration/parser-spec.md) §10 のオープンポイント 6 点
   - PO レビュー: [docs/requirements/v0.3.md](docs/requirements/v0.3.md) §9 残課題 10 点
   - PJC（プロジェクトチャーター）作成 → スキル `project-charter`
   - WBS 作成 → スキル `wbs`
2. **Phase 1: MVP 実装**（6〜8週）
   - スキル `fastapi-foundation-design` で基礎設計レビュー必須
   - 教師（招待メール方式）・生徒・指導枠・月次レポート CRUD ／ RBAC ／ 設定画面 ／ アクティブフィルタ
   - スキル `spec-driven-mock-ui` でモック先行
   - スキル `supabase-local-dev` でローカル開発環境
3. **Phase 2: 拡張**（4週）
   - 面談・ToDo・通知・Drive 連携
4. **Phase 3: 並行運用 + 自動パーサー実装**（12週）
   - [docs/sheets-migration/parser-spec.md](docs/sheets-migration/parser-spec.md) を実装
5. **Phase 4: Sheets 凍結 → 廃止**（1週）

---

## 決定事項（要点のみ・理由付き）

### 技術スタック
- **FastAPI + Jinja2 + HTMX + Supabase + Cloud Run**: 業務系 LOB／同時編集少／関係者≤数十名で SPA 不要、HTMX で十分。Supabase RLS で「教師は自担当のみ」を DB 層で強制。

### 認証
- **教師ログイン = 招待メール方式**: セルフサインアップ不可。管理者が `teachers` レコード作成 → `inviteUserByEmail()` → 教師が初回サインインで紐付け。トークン有効期限 72h。

### データ
- **半永久保持**: 卒業生徒・退職教師も論理削除のみ。一覧はデフォルト「アクティブのみ」、チェックボックスで過去分表示。
- **Drive 連携**: 教師契約書 PDF は Drive。**専用 SA を別途発行**（運用側で IAM・権限を通したもの）。Phase -1 では既存 SA `699555092496-compute@developer.gserviceaccount.com` を読取共有して調査に流用済み。

### Sheets 移行戦略
- **並行運用 3 か月** → Sheets 凍結 → 廃止
- 並行運用中、各エンティティに `external_sheet_url` を持たせ、Web アプリから元 Sheets へ 1 クリック遷移
- 自動パーサー実装前にパターン抽出を完了（Phase -1 = 完了）
- 解釈不能行は `import_errors` テーブルで吸収

### 設定可変項目
- 月次レポート締切日・充足率異常値の上下限・通知リマインド日数を `system_settings` テーブルで動的に保持

---

## 参照パス・コマンド

### 主要ドキュメント
- `docs/requirements/v0.3.md` — 要件定義（**正本**）
- `docs/sheets-migration/README.md` — Phase -1 索引
- `docs/sheets-migration/parser-spec.md` — Phase 3 実装の入力
- `C:\Users\yohay\.claude\plans\phase-1-magical-prism.md` — Phase -1 計画ファイル

### スプレッドシート（実データ）
- spreadsheet_id: `1inBUyjKQbFEH1tt-XnauWFKJqRU21F-GQGEzleLJLbA`
- タイトル: ★新【EB塾】【2026年度】指導モニタリング管理表
- URL: https://docs.google.com/spreadsheets/d/1inBUyjKQbFEH1tt-XnauWFKJqRU21F-GQGEzleLJLbA/

### NotebookLM
- notebook_id: `8d0e1e72-2137-485e-a524-826ba11d359c` （EA_生徒状況分析）
- スプレッドシートを drive ソースとして追加済み（source_id: `b7418ae7-e725-4b9d-b109-bf53552a4f4d`）

### 調査再実行
```powershell
python scripts/sheets-survey/probe_access.py    # SA アクセス確認
python scripts/sheets-survey/fetch_all.py        # 38タブ再取得
python scripts/sheets-survey/inventory.py        # CSV/JSON 再生成
```

### 既存資産（流用候補）
- `scripts/gdoc_to_md.py` — Google Docs → Markdown 変換（gws CLI 使用）
- `scripts/notebooklm_*.py` — NotebookLM 連携の既存 Python スクリプト
- `config/gen-lang-client-0360012476-457924b0f2ae.json` — GCP SA（gitignore 済）

### スキル（次に呼ぶべきもの）
- `fastapi-foundation-design` — Phase 1 着手前に基礎設計レビュー
- `spec-driven-mock-ui` — Phase 1 のモック先行
- `supabase-local-dev` — ローカル DB 立ち上げ
- `project-charter` — Phase 0 PJC
- `wbs` — Phase 0 WBS
- `local-quality-gate` — 実装後の検証
- `pre-implementation-critics` — 実装前クリティック

---

## 注意（次のエージェント向け）

### 触ってよい範囲
- **Phase -1 で新規作成したファイル**: `docs/sheets-migration/`、`scripts/sheets-survey/`、`docs/requirements/v0.3.md`、本 `HANDOFF.md`
- **これから新規作成**: `docs/requirements/v0.4+.md`、`docs/pjc/`、`docs/wbs/`、`src/` 配下の FastAPI コード等

### 触らないでほしい範囲（別作業の途中）
- `docs/samples/monthly-reports/` 配下と `samples/reports/` 配下、`src/reports/templates/` 配下は **このプロジェクトとは別の進行中作業**。Phase -1 の commit でも触れていない。

### 秘密情報の扱い
- `config/gen-lang-client-*.json` は SA キー。`.gitignore` 済。**読み込みは可、内容のログ出力は禁止**。
- 教師の口座情報（`bank_info` テーブル）は経理ロールのみ可視。RLS で強制。

### よくあるハマりどころ
- スプレッドシートの **全角数字 `１２３`** が混在（Phase -1 で対処済、`scripts/sheets-survey/inventory.py` の `_norm_no` 参照）
- 議事録セルが長文 → NotebookLM クエリ結果が 18万字超で context あふれた事例あり。**サブエージェント経由で読む**こと。
- PowerShell の文字化け → スクリプト実行時は `$env:PYTHONIOENCODING='utf-8'` を前置

### Plan Mode
- 3ファイル以上に影響しそうな変更は Plan Mode から始める（CLAUDE.md グローバルルール）
- 既存の Plan: `C:\Users\yohay\.claude\plans\phase-1-magical-prism.md`（Phase -1 = 承認・完了済）

### Git
- 本ファイル更新時は `git commit` → `git push` してから新スレッドへ。
- 既存の `M` 状態のファイル（monthly-reports など）は **別作業**。Phase 0 以降では触らない。
- ブランチ運用は `main` 直 push（小規模プロジェクト想定）。複数並行作業が始まったら `parallel-worktrees` スキルへ。

---

## オープンポイント（PO 確認待ち）

[docs/requirements/v0.3.md §9](docs/requirements/v0.3.md) ／ [docs/sheets-migration/parser-spec.md §10](docs/sheets-migration/parser-spec.md) を参照。
特に Phase 0 開始時に PO へまとめて出すこと。
