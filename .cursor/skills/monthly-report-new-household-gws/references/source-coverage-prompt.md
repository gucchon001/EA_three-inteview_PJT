# 一次ソース読み取り可否 × 配布レポート反映チェック（汎用プロンプト）

**用途**: Pattern B の HTML（または MD）について、`student` シート・lesson plan・教師 MTG（文字起こし／Gemini メモなど）から**読み取れる情報**と**実際に本文へ反映されているか**を切り分け、手動編集の妥当性／自動パイプラインのギャップを整理する。

**関連**: [data-contract.md](data-contract.md)（どの節がどのソースか）、家庭向け方針は [family-facing-tone.md](../monthly-report-notebooklm-patterns/references/family-facing-tone.md)。

---

## 入力プレースホルダ一覧（実行前に全部埋める）

| 変数 | 説明 | 例 |
|------|------|-----|
| `{{HOUSEHOLD_SLUG}}` | ディレクトリ名の slug | `tokura` |
| `{{TARGET_MONTH}}` | レポート対象の暦月 | `2026-04` |
| `{{TARGET_MONTH_JA}}` | 読みやすい表現 | `2026年4月` |
| `{{REPORT_FILE}}` | 照合する配布ファイル（プロジェクトからのパス） | `docs/samples/monthly-reports/monthly_2026-04_tokura_v2_report.html` |
| `{{REPORT_VARIANT}}` | ドラフト名・ブランチ名など | `tokura_v2` |
| `{{AUDIT_DATE}}` | 本ドキュメントの作成日（運用上の「最新」） | `2026-05-13` |
| `{{S_STUDENT}}` | `_gws_*` で取得した student 値 JSON のパス | `samples/reports/household_{{HOUSEHOLD_SLUG}}/sources/_gws_student_A1-Z200_values.json` |
| `{{S_LESSON}}` | lesson plan（SL 等）の values JSON パス | `samples/reports/household_{{HOUSEHOLD_SLUG}}/sources/_gws_SL_lesson_plan_A1-M250_values.json` |
| `{{S_MTG}}` | MTG Doc 由来のプレーンテキスト（推奨） | `.../_gws_doc_teacher_MTG_gemini.txt` |
| `{{S_META}}` | （任意）`spreadsheets.get` のメタ JSON | `.../_gws_spreadsheet_meta.json` |
| `{{S_HL}}` | （任意）HL 用 lesson plan | `.../_gws_HL_lesson_plan_A1-Z200_values.json` |
| `{{OUTPUT_PATH}}` | 今回の出力ファイル（新規） | `docs/samples/monthly-reports/SOURCE_COVERAGE_{{HOUSEHOLD_SLUG}}_{{REPORT_VARIANT}}_{{AUDIT_DATE}}.md` |

**再取得コマンド例**（ブック ID・Doc ID は世帯ごとに差し替え）:

```bash
python scripts/fetch_monthly_gws_sources.py --help
# 例: spreadsheet / doc / out / slug を指定して sources/ を更新
```

---

## ラベル定義（出力表で必ず使う）

**読み取り可否**

| 記号 | 意味 |
|------|------|
| **読取-A** | 一次ソースに**ほぼ原文レベル**で書いてある（転記しやすい） |
| **読取-B** | 情報はあるが**要約・推定・IB／学校用語への翻訳**が必要 |
| **読取-C** | **セル／メモに無い**、または空欄（別取材・運用入力が必要） |
| **載せ方-D** | テンプレ・家庭向け方針で**あえて載せない**・社内・管理者のみ |

**反映（レポート側）**

| 語 | 意味 |
|----|------|
| 反映済 | ソースの情報が本文に明示的にある（言い換え可） |
| 一部 | 一部のみ、ニュアンス差・欠落 |
| 未反映 | ソースにあって本文に無い |
| 意図非掲載 | 読めるが方針で載せない（載せ方-D とセットで書く） |
| 要照合 | ソースと本文で**論理矛盾の疑い**（人手必須） |

**手動編集の切り分け**

- **読取-A かつ 未反映** → 自動生成の取りこぼし疑い（優先度高）。
- **読取-B かつ 反映済** → 家庭向け言い換え後にユーザーが手直ししても正常。
- **読取-C** を本文が埋めている → 口述・過去月・別チャンネルの補完の可能性。

---

## ステップバイステップ手順（汎用）

### Step 1 — スコープ固定

1. 対象月を `{{TARGET_MONTH}}` / `{{TARGET_MONTH_JA}}` にそろえる（レポートの「対象期間」と一致）。  
2. 照合ファイル `{{REPORT_FILE}}` を開く。  
3. 節 **01〜05**（およびテンプレで定義された追加節）について、各文を **事実／所見／家庭へのお願い** に分類するメモを取る。

### Step 2 — `student`（S1）を走査

1. `{{S_STUDENT}}` の `values` を上から読み、**見出しセル＋値**のペアを列挙。  
2. 少なくとも次を「値の有無」まで記録: 氏名、志望、目標・現状スコア、mock/final、SL/HL 行、英語力、前回試験メモ、IA/EE 関連、空欄行。  
3. 空欄は **読取-C**（自動では埋めない）。

### Step 3 — lesson plan（S2）から対象月だけ抽出

1. `{{S_LESSON}}` で、**`授業日` 列（または同等）が `{{TARGET_MONTH}}` に含まれる行**だけを抜き出す。  
2. 同月にまたがる **Unit test** 行は、配点・得点・得点率があれば数値も記録。  
3. **メモ列**に学校テスト・コマ数などがあればそのまま転記（後述の表の「ソース」欄に使う）。  
4. 翌月頭の数行だけ見て、**05「今後」**と対応する単元が plan 上にあるか確認（仮日を家庭向けに伏せる方針かは別途 **載せ方-D** で記録）。

### Step 4 — MTG テキスト（S3）

1. `{{S_MTG}}` の**会議日・参加者**を先頭から確認。  
2. **数値・固有名詞・動詞**（予定／確認／依頼）をマーク。  
3. Gemini 等の**明らかな人名誤記**は「内容の照合」ではなく原記録・音声へ送る旨を表に書く。

### Step 5 — `{{REPORT_FILE}}` と突合

各トピック行に **可否ラベル**と**反映ラベル**を付与。食い違いは **要照合**。

### Step 6 — 出力 Markdown を書く

- 下記「**コピペ用：エージェント／チャットプロンプト**」に従い、**`{{OUTPUT_PATH}}`** に保存。  
- 事例（十倉）: `docs/samples/monthly-reports/TOKURA_SOURCE_READABILITY_vs_V2_REPORT_2026-05-13.md`。

---

## 出力テンプレート（表の骨格）

以下を `{{OUTPUT_PATH}}` に複製し、行を埋める。

```markdown
# {{HOUSEHOLD_SLUG}} 世帯｜一次ソース × `{{REPORT_VARIANT}}` 反映チェック

**調査作成日**: {{AUDIT_DATE}}  
**対象月**: {{TARGET_MONTH_JA}}  
**照合レポート**: `{{REPORT_FILE}}`

## 一次ソース一覧

| # | パス | 役割 |
|---|------|------|
| S1 | `{{S_STUDENT}}` | student シート |
| S2 | `{{S_LESSON}}` | lesson plan（SL 等） |
| S3 | `{{S_MTG}}` | 教師 MTG テキスト |
| S4 | `{{S_META}}` | （任意）スプレッドシートメタ |

## 差分表

| # | レポート位置 | 項目 | ソース | 可否 | 反映 | メモ |
|---|-------------|------|--------|------|------|------|
| 1 | … | … | S1/S2/S3 | 読取-A | 反映済 | … |

## 優先アクション

| 症状 | 推奨 |
|------|------|
| … | … |
```

---

## コピペ用：エージェント／チャットプロンプト

次のブロックをそのまま貼り、**先頭のプレースホルダを実値に置換**してから実行する（Cursor では `@ファイル` で S1/S2/S3 とレポートを添付）。

```
あなたは EA_three-inteview_PJT の月次 Pattern B の品質レビュアです。

次のプレースホルダを埋めたうえで、添付の一次ソースと照合 HTML を読み、
「読取-A/B/C・載せ方-D」と「反映（反映済／一部／未反映／意図非掲載／要照合）」の表を作成してください。

- HOUSEHOLD_SLUG: {{HOUSEHOLD_SLUG}}
- TARGET_MONTH / TARGET_MONTH_JA: {{TARGET_MONTH}} / {{TARGET_MONTH_JA}}
- REPORT_FILE: {{REPORT_FILE}}
- REPORT_VARIANT: {{REPORT_VARIANT}}
- AUDIT_DATE: {{AUDIT_DATE}}
- S_STUDENT: {{S_STUDENT}}
- S_LESSON: {{S_LESSON}}
- S_MTG: {{S_MTG}}
- S_META（任意）: {{S_META}}

手順:
1. 対象月にスコープを限定し、レポートの 01〜05 を「事実／所見／お願い」に分類する。
2. S1 のキーと空欄を列挙。空欄は読取-C。
3. S2 から対象月の授業日行だけ抜き出し、Unit test の数値とメモ列を転記。
4. S3 から数値・固有名詞・方針を抽出。誤記は内容照合の限界として注記。
5. 各行について可否・反映を付け、読取-A かつ未反映を最優先で指摘。
6. 出力は日本語の Markdown。表のあとに「優先アクション」3〜6 行。

テンプレのラベル定義は
.cursor/skills/monthly-report-new-household-gws/references/source-coverage-prompt.md
に従うこと。
```

---

## 改訂履歴

| 日付 | 内容 |
|------|------|
| 2026-05-13 | 十倉事例から汎用化。初版。 |
