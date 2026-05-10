# Sheets Parser Spec（Phase -1 / Step 6）

「★新【EB塾】【2026年度】指導モニタリング管理表」を Web アプリ DB に取り込む自動パーサーの仕様書（v0.1）。
本仕様は Phase 3（並行運用フェーズ）でパーサー実装に着手する際の入力。

参照:
- `anchors.md` — ブロックアンカー設計
- `normalization-rules.md` — 表記ゆれ正規化ルール
- `tab-inventory.csv` — タブごとの検出結果
- `variants.json` — 表記ゆれの全数

---

## 0. ゴール

- 35 件の生徒個別タブから DB レコードを自動生成する
- 失敗を **明示的に** `import_errors` に記録し、人手で復旧可能にする
- 同一タブの再投入で結果が変わらない（**冪等**）
- Phase 0〜2 で確定する DB スキーマと整合する

---

## 1. 入出力契約

### 入力
| 項目 | 型 | 補足 |
|---|---|---|
| spreadsheet_id | str | 環境変数で固定 |
| service_account_path | str | `config/gen-lang-client-*.json` |
| target_sheets | list[str] | デフォルト全タブ。デバッグ時は絞れる |

### 出力（DB 書込前のドメインオブジェクト）

```python
@dataclass
class ParseResult:
    job_id: str
    spreadsheet_id: str
    fetched_at: datetime
    teachers: list[Teacher]               # マスター由来
    students: list[Student]               # 個別タブ由来
    assignments: list[Assignment]         # 個別タブ Block 2 由来
    monthly_reports: list[MonthlyReport]  # Block 3-6 + 月次セルから生成
    meetings: list[Meeting]               # Block 7 から生成
    todos: list[Todo]                     # Block 7 議事録由来
    errors: list[ImportError]
```

### 出力先テーブル
| Source ブロック | 生成レコード | UPSERT キー |
|---|---|---|
| Block 1 (生徒情報) | `students` | `student_no` |
| Block 2 (選考情報) | `assignments` | `selection_no` |
| Block 3 (契約時間充足率) + 月次列 | `monthly_reports.actual_hours / fulfillment_rate` | `(assignment_id, year_month)` |
| Block 4 (教師評価) + 月次列 | `monthly_reports.teacher_eval_*` | 同上 |
| Block 5 (指導報告書) + 月次列 | `monthly_reports.report_*` | 同上 |
| Block 6 (学習進捗確認) + 月次列 | `monthly_reports.progress_*` | 同上 |
| Block 7 (月別記録表) | `meetings` + `todos` | `(student_id, held_at, kind)` |

---

## 2. 処理フロー

```
┌──────────────────────────────────────┐
│ 1. fetch_all                         │
│    Sheets API spreadsheets.get       │
│    + values.batchGet                 │
│    → SheetSnapshot (raw)             │
└────────────┬─────────────────────────┘
             ↓
┌──────────────────────────────────────┐
│ 2. dispatch_by_kind                  │
│    - master_teacher                  │
│    - master_student                  │
│    - template (skip)                 │
│    - student_individual              │
└────────────┬─────────────────────────┘
             ↓
┌──────────────────────────────────────┐
│ 3. parse_master_teacher              │
│    → Teacher canonical list          │
└────────────┬─────────────────────────┘
             ↓
┌──────────────────────────────────────┐
│ 4. parse_student_tab (×35)           │
│    a. detect_anchors (anchors.md)    │
│    b. parse_block1_5 + 6             │
│    c. for month in 4..3:             │
│         parse_monthly_column         │
│    d. parse_block7 (meetings/todos)  │
└────────────┬─────────────────────────┘
             ↓
┌──────────────────────────────────────┐
│ 5. normalize                         │
│    - teacher → canonical (3段階)     │
│    - subject → canonical             │
│    - grade → grade + dp_phase        │
│    - boolean / numeric / month       │
└────────────┬─────────────────────────┘
             ↓
┌──────────────────────────────────────┐
│ 6. validate + emit_errors            │
│    Pydantic 検証 → import_errors     │
└────────────┬─────────────────────────┘
             ↓
┌──────────────────────────────────────┐
│ 7. upsert_db (transactional)         │
│    各テーブル UPSERT、ジョブ ID 付与 │
└──────────────────────────────────────┘
```

---

## 3. パース詳細

### 3.1 Block 1: Student
```python
def parse_block1(values, b1_row):
    # b1_row + 1: header (生徒番号 / 生徒氏名 / 学年 / 最終試験時期 / 入会日)
    # b1_row + 2: data
    return Student(
        student_no=int(cell(values, b1_row+2, 1)),  # B 列
        name=cell(values, b1_row+2, 2),              # C 列
        grade_raw=cell(values, b1_row+2, 3),         # D 列
        exam_term=cell(values, b1_row+2, 4),         # E 列
        enrolled_at=parse_date(cell(values, b1_row+2, 6)),  # G 列（A 型のみ）
    )
```

### 3.2 Block 2: Assignments
```python
def parse_block2(values, b2_row, n_subjects):
    out = []
    for i in range(n_subjects):
        r = b2_row + 2 + i  # data rows
        if not (cell(values, r, 1) or cell(values, r, 2)):
            break  # No / 選考番号 ともに空 → 終端
        out.append(Assignment(
            selection_no=cell(values, r, 2),    # C
            teacher_raw=cell(values, r, 3),     # D
            course=cell(values, r, 5),          # F
            subject_raw=cell(values, r, 7),     # H
            monthly_hours=parse_int(cell(values, r, 9)),  # J
        ))
    return out
```

### 3.3 Block 3〜6 + 月次列
- ヘッダ行（4月〜3月）の列マップを 1 度だけ取得
- 各サブ項目（実施時間、計画性、メッセージ有無 等）について 12 ヶ月分のセルを横読み
- 値は `normalize_boolean` / `parse_int` / `parse_float` で変換
- 1 タブから最大 `n_subjects × 12` 行の `monthly_reports` を生成

### 3.4 Block 7: Meetings
- B 列に `4`〜`3`（4 月〜3 月）の月数値が縦展開
- 同じ行の `三者面談実施日`（H 列）と `教師mtg実施日`（P 列）を読む
- 議事録セル（隣接の長文セル）を `body` として保存
- 既知の制約: ToDo は議事録本文に混在 → Phase 3 では本文をまるごと格納し、Phase 4 で構造化解析

---

## 4. データ生成ルール

### 4.1 1 タブから生成されるレコード
| エンティティ | 件数 |
|---|---|
| Student | 1 |
| Assignment | 1〜3（科目数 N）|
| MonthlyReport | N × 12（最大 36）|
| Meeting | 0〜12（記入分のみ）|
| Todo | meeting 数に準ずる |

### 4.2 全 35 タブの予想生成量
- Student: 35
- Assignment: 〜70（平均 2 科目）
- MonthlyReport: 〜840（70 × 12）
- Meeting: 〜400（推測）

---

## 5. 冪等性

### UPSERT キー定義
| テーブル | キー | 衝突時の挙動 |
|---|---|---|
| students | `student_no` | 全列上書き、`updated_at = now()` |
| assignments | `selection_no` | 全列上書き |
| monthly_reports | `(assignment_id, year_month)` | 全列上書き |
| meetings | `(student_id, held_at, kind, source_hash)` | source_hash で重複検出 |
| import_errors | `(job_id, sheet_name, row_no)` | 累積 |

### 注意
- **削除は行わない**（部分削除はリスク高）
- スプレッドシート側で行が消えた場合、DB レコードは残る → 半永久保持の方針と整合

---

## 6. import_errors の発生条件

| 条件 | 例 |
|---|---|
| ブロックアンカー未検出 | `Block2_Selection` が見つからない |
| 数値変換失敗 | `monthly_hours` に「5h」など単位が混入 |
| 教師名未マッチ | canonical / 苗字一致のいずれにも該当せず |
| 教師名曖昧 | `林` → 候補 2 名以上 |
| 科目名曖昧 | `Math(HL)` → AA か AI か判別不可 |
| Pydantic 検証失敗 | 必須フィールド欠損、型不一致 |
| Block 2 の subject_count > 3 | 想定外（要 PO 確認） |
| 独自列の非空 | `tab-inventory.csv` で flag 済 |

`import_errors` レコード:
```sql
CREATE TABLE import_errors (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL,
    sheet_name TEXT NOT NULL,
    row_no INT,
    column_no INT,
    error_kind TEXT NOT NULL,  -- 'missing_anchor' | 'normalize_fail' | ...
    error_message TEXT NOT NULL,
    raw_payload_json JSONB,
    resolved_at TIMESTAMPTZ,
    resolved_by UUID,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 7. 既知の例外パターンと対応

| パターン | 件数 | 対応 |
|---|---|---|
| Block 7（三者面談）非搭載 | 2 件（近添・伴場）| `meetings` 件数 0 で OK |
| 教師列空欄 | C 型タブで複数 | `import_errors` に記録、Skip |
| 科目数 0（記入待ち）| 値賀・大塚 等 | warning ログ、 monthly_reports 生成スキップ |
| 独自列追加 | C 型タブで散見 | Phase 0 で **取り込み列の確定**まで保留 |

---

## 8. 実行モード

| モード | 用途 | 副作用 |
|---|---|---|
| `dryrun` | DB 書込なし、`ParseResult` を JSON 出力 | なし |
| `staging` | staging DB に投入、PR レビュー | staging のみ |
| `production` | 本番 DB に UPSERT、`audit_log` 追加 | 本番反映 |

並行運用期間中は **毎晩 dryrun → 翌朝レビュー → 手動 production 実行** を想定。

---

## 9. テスト観点

| 観点 | 内容 |
|---|---|
| 単体 | 各 normalize_* 関数を `variants.json` の全種類で検証 |
| 結合 | 35 タブの fixture を入力、期待 ParseResult JSON と diff |
| 回帰 | スプレッドシート更新後の差分検出（前回 ParseResult との比較） |
| 性能 | 35 タブを 60 秒以内に処理 |

`tests/fixtures/sample-extracts/` に Phase -1 で取得した JSON をそのまま使用する。

---

## 10. オープンポイント（Phase 0 で PO 確認）

1. 教師の苗字のみ表記（`林` 等）が複数 canonical に該当する場合の扱い（手動マッピング UI を作るか）
2. `Math(HL)` のレベル＆種別不明な科目表記の扱い
3. 独自列で **取り込むべき情報があるか**（事業観点）
4. 退職教師の表記が canonical にない場合の運用（教師マスターに復活登録 or 別キーで残す）
5. 並行運用期間中、同タブを **複数回** インポートする頻度（毎晩 / 週次）
6. dryrun の差分閾値（`monthly_reports` を 100 件以上書き換えるなら警告等）

---

## 11. 受け入れ条件（Phase 3 完了基準）

- [ ] dryrun で 35 タブを 60 秒以内に処理し、`ParseResult` JSON を出力
- [ ] `import_errors` 件数が **30 件以下**（≒ 1 タブあたり 1 件未満）
- [ ] staging で UPSERT を 2 回連続実行し、2 回目の差分が **ゼロ**（冪等）
- [ ] 教師名のマッチ率 ≥ 95%（`variants.json` ベース）
- [ ] 科目名のマッチ率 ≥ 90%
- [ ] PO 受け入れレビュー完了
