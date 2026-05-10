# Normalization Rules（Phase -1 / Step 4）

実データ（35タブ）から検出した表記ゆれを、パーサー前処理で正規化するルール。
データ: `docs/sheets-migration/variants.json`

---

## 1. 共通プリプロセス（全フィールド適用）

| 順序 | 処理 | 対象 |
|---|---|---|
| 1 | `\r\n` / `\n` を半角スペースに置換 | 全文字列 |
| 2 | 制御文字（U+0000〜U+001F 除く改行）を除去 | 全文字列 |
| 3 | 連続空白（半角・全角混在）を **1つの半角スペース** に統一 | 全文字列 |
| 4 | 前後 strip | 全文字列 |

---

## 2. 学年（grade）

### 観測されたバリエーション（8 種）
`高1`, `高1`, `高2`, `高2`, `高2 DP1`, `高3`, `高3`, `高3 DP2`

### ルール
1. 全角数字 → 半角数字（`０-９` → `0-9`）
2. 全角空白 → 半角空白
3. 改行を半角空白に置換（"高3\nDP2" → "高3 DP2"）
4. **本体（学年）と DP 情報を分離**:
   - 正規表現 `^高([1-3])(?:\s*(DP[12]))?$` でマッチ
   - 結果: `grade = 高N` / `dp_phase = DP1|DP2|None`
5. マッチしないものは `import_errors` 行き

### 出力スキーマ案
```python
class StudentGrade:
    grade: Literal["高1","高2","高3","中1","中2","中3","小N",...]  # 拡張可
    dp_phase: Literal["DP1","DP2"] | None
    raw: str  # 元の文字列を保存
```

---

## 3. 教師名（teacher_name）

### 観測されたバリエーション（36 種）と canonical 56 種

**主な揺れ**:
- 苗字のみ: `関`, `関月歌`, `関 月歌`, `関　月歌`（canon: `関　月歌`）
- 苗字のみ: `Kim`（canon: `Kim　Hyojin`）／`広谷`（canon: `広谷　美咲`）／`池田` `池田和永`（canon: `池田　和永`）
- スペース表記: 全角/半角混在
- 大文字小文字: `Deshpande　ria` ⇄ canonical `Deshpande Ria`
- 苗字単独: `中橋`, `原田`, `北川廉`, `橋本`, `森田`, `林`, `松村`, `城`, `李`, `坂部`, `大須賀`, `宗澤`, `山口`, `稲益`, `竹本`, `瀧田`, `佐藤`, `横井` 等

### ルール（Match 関数）

```python
def normalize_teacher(raw: str, canonical: list[str]) -> MatchResult:
    """3 段階で照合する。"""
    s = raw
    s = s.replace("　", " ")   # 全角空白 → 半角
    s = re.sub(r"\s+", " ", s).strip()
    s = s.lower() if is_ascii(s) else s  # ASCII のみ小文字化

    # 段階1: 完全一致（同じ正規化を canonical 側にも適用）
    norm_canon = {normalize(c): c for c in canonical}
    if s in norm_canon:
        return Match(canonical=norm_canon[s], confidence=1.0, method="exact")

    # 段階2: 苗字一致（canonical の最初のスペース前を取る）
    surname_map: dict[str, list[str]] = defaultdict(list)
    for c in canonical:
        sn = c.split(" ")[0] if " " in c else c
        surname_map[sn].append(c)
    if s in surname_map:
        cands = surname_map[s]
        if len(cands) == 1:
            return Match(canonical=cands[0], confidence=0.8, method="surname_unique")
        return Ambiguous(candidates=cands, raw=raw)  # → import_errors

    # 段階3: 部分一致（生徒タブ名が canonical の連結文字列に含まれる）
    no_space = s.replace(" ", "")
    for c in canonical:
        if no_space and no_space == c.replace(" ", "").replace("　", ""):
            return Match(canonical=c, confidence=0.9, method="space_normalized")

    return Unmatched(raw=raw)  # → import_errors
```

### 既知の解決不能ケース（PO 確認候補）
| raw | 候補 | 備考 |
|---|---|---|
| `林` | `林 史奈` / `林 裕美` | 苗字のみで判別不可 → import_errors |
| `橋本` | `橋本 直樹` のみ | 単一なら段階2で解決 |
| `広谷` | `広谷　美咲` のみ | 単一なら段階2で解決 |

---

## 4. 科目名（subject）

### 観測されたバリエーション（17 種）
`Biology(HL)`, `Biology(SL)`, `Chemistry(HL)`, `Economics(HL)`, `Economics(SL)`,
`English A LL(SL)`, `History(SL)`, `Math AA (HL)`, `Math AA (SL)`, `Math AA(HL)`,
`Math AA(SL)`, `Math AI(HL)`, `Math(HL)`, `Math　AA`, `Physics(HL)`, `Physics(SL)`,
`SSST`

### 正規ラベル辞書（提案）
```python
SUBJECT_CANONICAL = {
    "Biology HL": ["Biology(HL)", "Biology (HL)", "Bio HL"],
    "Biology SL": ["Biology(SL)", "Biology (SL)"],
    "Chemistry HL": ["Chemistry(HL)", "Chemistry (HL)", "Chem HL"],
    "Chemistry SL": ["Chemistry(SL)", "Chemistry (SL)"],
    "Economics HL": ["Economics(HL)", "Economics (HL)", "Econ HL"],
    "Economics SL": ["Economics(SL)", "Economics (SL)"],
    "English A LL SL": ["English A LL(SL)", "English A LL (SL)"],
    "History SL": ["History(SL)", "History (SL)"],
    "Math AA HL": ["Math AA(HL)", "Math AA (HL)", "Math AA HL"],
    "Math AA SL": ["Math AA(SL)", "Math AA (SL)", "Math AA SL"],
    "Math AI HL": ["Math AI(HL)", "Math AI (HL)"],
    "Physics HL": ["Physics(HL)", "Physics (HL)"],
    "Physics SL": ["Physics(SL)", "Physics (SL)"],
    "SSST": ["SSST"],
    # 不明: "Math(HL)" → Math AA HL か Math AI HL か判別不可
    # 不明: "Math　AA" → レベル(HL/SL) 不明
}
```

### ルール
1. 全角空白 → 半角空白
2. 半角空白を 1 つに統一
3. 括弧前の空白を統一: `Math AA(HL)` → `Math AA HL`（カッコと空白を「半角スペース」に統一）
4. canonical 完全一致 → そのまま正規ラベルを返す
5. 含まれる場合は曖昧解決ルール（PO 確認）:
   - `Math(HL)` のみは曖昧 → import_errors
   - `Math　AA` はレベル不明 → import_errors

### 既知の制約
- IB 科目体系を踏まえた canonical は **Phase 0 で PO レビュー**
- HL/SL の片方しか書かれていない場合の扱い（推測 or import_errors）も PO 確認

---

## 5. 真偽値（チェックボックス／Boolean）

### 観測
- `TRUE` / `FALSE` の文字列値（指導報告書の月次セル等）
- 大量の `FALSE` がデフォルト値として残存
- 日本語チェックの欄なし（数値で代用される場面あり）

### ルール
| raw | 出力 | 補足 |
|---|---|---|
| `TRUE` | `True` | |
| `FALSE` | `False` | **未操作と区別不可** — `is_explicit=False` を併記 |
| `""`（空）| `None` | 未入力 |
| `1` / `0` | `True` / `False` | （あれば）|
| その他 | `None` + warning | `import_errors` には入れない |

### 既知の制約（再掲）
**チェックボックスのデフォルト `FALSE` と明示 `FALSE` は区別不可**。
月次レポートの「報告書提出済み」判定は、**実施時間 > 0** など別シグナルと組み合わせる。

---

## 6. 月（month）と年度

### 観測
- `4`, `5`, ..., `3` の数字が縦軸（B 列）または横軸（D 列以降）に展開
- 日本の塾年度（4月始まり）

### ルール
1. 数値を `int` に変換
2. 順序: 4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3
3. **物理的な並び順から年度を補完**:
   - シートタイトル「2026年度」を起点
   - 4月 〜 12月 = 2026年
   - 1月 〜 3月 = 2027年（**年度繰り上げ**）
4. 出力形式: `year_month = "2026-04"` / `"2027-01"` / `"2027-03"`

---

## 7. 数値・契約時間

### 観測
- 契約時間（月）: `5` のような整数
- 実施時間: 整数または小数（0.5 単位 推測）
- 充足率: 数値文字列 or 空欄

### ルール
1. カンマ・空白を除去
2. `int` 変換可能なら `int`、`float` 変換可能なら `float`、それ以外は `import_errors`
3. 空欄は `None`
4. **`実施時間 = 0` と空欄は区別**（0 は明示的にゼロ実施）

---

## 8. 適用順序

```
原文セル
  ↓ Step 1: 共通プリプロセス
  ↓ Step 2-7: フィールドごとの正規化
  ↓ canonical 照合
正規化済み値 + match_method + confidence
  ↓ confidence >= 0.8 → DB
  ↓ confidence < 0.8 or 不一致 → import_errors テーブル
```

---

## 9. テスト観点（Phase 3 実装時に使用）

- `tests/test_normalization/test_grade.py`: 8 種の grade variant をすべて期待値にマッピング
- `tests/test_normalization/test_teacher.py`: 36 variant のうち、35 以上が canonical にマッピングされること
- `tests/test_normalization/test_subject.py`: 17 variant のうち、15 以上が正規ラベルにマッピング
- `tests/test_normalization/test_boolean.py`: 4 入力パターン × 期待値
