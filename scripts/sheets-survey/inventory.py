"""sample-extracts/ から:
  - tab-inventory.csv: タブ × 検出結果のマトリクス
  - variants.json: 教師名・科目名・学年のバリエーション収集

を生成する。anchors.md に基づく検出ロジック。
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXTRACTS_DIR = REPO_ROOT / "docs" / "sheets-migration" / "sample-extracts"
OUT_DIR = REPO_ROOT / "docs" / "sheets-migration"

MASTER_TEACHER = "★EB塾教師一覧"
MASTER_STUDENT = "★EB塾生徒一覧"  # title may have trailing space
TEMPLATE_PREFIX = "【原本】"

# anchors.md と整合した検出設定
BLOCKS: list[tuple[str, str, int, tuple[int, int]]] = [
    # (block_name, anchor_label, expected_col_zero_based, row_range_inclusive_1based)
    ("Block1_StudentInfo", "生徒情報", 1, (2, 5)),
    ("Block2_Selection", "選考情報", 1, (5, 10)),
    ("Block3_Fulfillment", "契約時間充足率", 1, (10, 15)),
    ("Block4_TeacherEval", "教師評価", 1, (15, 25)),
    ("Block5_Reports", "指導報告書", 1, (22, 35)),
    ("Block6_Progress", "学習進捗確認", 1, (28, 47)),
    ("Block7_MonthlyTable", "月", 1, (35, 60)),
]

THREE_PARTY_LABEL = "三者面談"  # Block7 の B 型/C 型判定用
TEACHER_MTG_LABEL = "教師mtg"


def cell(values: list[list[str]], r: int, c: int) -> str:
    if r >= len(values):
        return ""
    row = values[r]
    if c >= len(row):
        return ""
    return (row[c] or "").strip()


def load_extracts() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in sorted(EXTRACTS_DIR.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        out[d["title"]] = d
    return out


def is_student_tab(title: str) -> bool:
    t = title.strip()
    if t == MASTER_TEACHER or t == MASTER_STUDENT:
        return False
    if title.startswith(TEMPLATE_PREFIX):
        return False
    return True


def find_anchor(values: list[list[str]], label: str, col: int, row_range: tuple[int, int]) -> int:
    """Return 0-based row index where label found in column `col`, or -1."""
    lo, hi = row_range[0] - 1, row_range[1] - 1  # convert to 0-based
    for r in range(lo, min(hi + 1, len(values))):
        v = cell(values, r, col)
        if v == label:
            return r
    # Try expanded range with col±1 fallback
    for r in range(lo, min(hi + 1, len(values))):
        for c in (col - 1, col + 1):
            if c < 0:
                continue
            if cell(values, r, c) == label:
                return r
    return -1


_NO_VALUES = {
    "1", "2", "3", "4", "５", "１", "２", "３", "４",  # 半角・全角
}


def _norm_no(s: str) -> str:
    """No 列の値を半角数字に正規化（全角数字 → 半角）。"""
    table = str.maketrans("０１２３４５", "012345")
    return s.translate(table).strip()


def detect_subject_count(values: list[list[str]], block2_row: int) -> int:
    """Block2 ヘッダ直下から最大4行、No or 選考番号 が埋まっている行数を数える。"""
    count = 0
    for offset in range(2, 6):
        r = block2_row + offset
        no_v = _norm_no(cell(values, r, 1))  # B 列
        sel_v = cell(values, r, 2)            # C 列（選考番号）
        # No が 1〜4 の数字か、選考番号が非空数値なら 1 件カウント
        if no_v in {"1", "2", "3", "4"} or (sel_v and sel_v.isdigit()):
            count += 1
        else:
            break
    return count


def detect_subjects(values: list[list[str]], block2_row: int, n: int) -> list[dict]:
    """選考情報の行 N 件を読み出す。ヘッダ列 C/D/F/H/J = 1+1=2/3/5/7/9（0-based: 2,3,5,7,9）"""
    rows: list[dict] = []
    # 列マップ（anchors.md: B7=No / C7=選考番号 / D7=採用教師名 / F7=指導コース / H7=指導科目 / J7=契約時間）
    cols = {
        "no": 1,
        "selection_no": 2,
        "teacher": 3,
        "course": 5,
        "subject": 7,
        "hours": 9,
    }
    for i in range(n):
        r = block2_row + 2 + i
        rows.append({k: cell(values, r, c) for k, c in cols.items()})
    return rows


def detect_grade(values: list[list[str]], block1_row: int) -> str:
    """Block1: 学年は D 列（C=2,D=3）の row block1_row+2（ヘッダの直下）にあるはず。"""
    # block1_row 0-based。block1_row+1 = ヘッダ行（B3=生徒番号 等）
    # block1_row+2 = データ行（学年の値）
    return cell(values, block1_row + 2, 3)


def has_3party_table(values: list[list[str]], block7_row: int) -> bool:
    if block7_row < 0:
        return False
    # 同じ行か近傍に "三者面談" ラベル
    for r in range(block7_row, min(block7_row + 3, len(values))):
        for c in range(0, min(20, len(values[r]) if r < len(values) else 0)):
            if cell(values, r, c) == THREE_PARTY_LABEL:
                return True
    return False


def collect_teacher_canon(d: dict) -> list[str]:
    """teacher master タブから教師正規氏名を抽出。氏名列の特定はヒューリスティック。"""
    values = d["values"]
    # ヘッダ行から「氏名」「名前」「Name」等を検出
    name_cols: list[int] = []
    for r in range(0, min(5, len(values))):
        for c, v in enumerate(values[r]):
            if v and ("氏名" in v or v == "名前" or "Name" in v):
                name_cols.append(c)
    # データ行は r=2 以降を想定
    names: set[str] = set()
    for r in range(1, len(values)):
        for c in name_cols or [3, 4]:
            v = cell(values, r, c)
            if v and 1 <= len(v) <= 30 and not any(x in v for x in ["氏名", "名前", "Name"]):
                names.add(v)
    return sorted(names)


def main() -> int:
    extracts = load_extracts()

    teacher_canon: list[str] = []
    if MASTER_TEACHER in extracts:
        teacher_canon = collect_teacher_canon(extracts[MASTER_TEACHER])
    print(f"# Teacher canonical names: {len(teacher_canon)}")

    inventory_rows: list[dict] = []
    teacher_variants: dict[str, list[str]] = defaultdict(list)
    subject_variants: dict[str, list[str]] = defaultdict(list)
    grade_variants: dict[str, list[str]] = defaultdict(list)

    for title, d in extracts.items():
        if not is_student_tab(title):
            continue
        values = d["values"]
        row = {
            "tab": title,
            "gid": d["gid"],
            "rows": len(values),
            "merges": len(d["merged_ranges"]),
        }
        anchors_found: dict[str, int] = {}
        for name, label, col, rng in BLOCKS:
            r = find_anchor(values, label, col, rng)
            anchors_found[name] = r
            row[name] = r + 1 if r >= 0 else ""

        # subject count
        b2_row = anchors_found.get("Block2_Selection", -1)
        n_sub = detect_subject_count(values, b2_row) if b2_row >= 0 else 0
        row["subject_count"] = n_sub

        # 3party table (B7 anchor)
        b7_row = anchors_found.get("Block7_MonthlyTable", -1)
        row["has_3party_block"] = "Y" if has_3party_table(values, b7_row) else "N"

        # blocks missing
        missing = [n for n, r in anchors_found.items() if r < 0]
        row["missing_blocks"] = ";".join(missing)

        # collect variants
        b1_row = anchors_found.get("Block1_StudentInfo", -1)
        if b1_row >= 0:
            grade = detect_grade(values, b1_row)
            if grade:
                grade_variants[title].append(grade)
        if b2_row >= 0 and n_sub > 0:
            for s in detect_subjects(values, b2_row, n_sub):
                if s["teacher"]:
                    teacher_variants[title].append(s["teacher"])
                if s["subject"]:
                    subject_variants[title].append(s["subject"])

        inventory_rows.append(row)

    # CSV
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / "tab-inventory.csv"
    fieldnames = [
        "tab", "gid", "rows", "merges",
        "Block1_StudentInfo", "Block2_Selection", "Block3_Fulfillment",
        "Block4_TeacherEval", "Block5_Reports", "Block6_Progress",
        "Block7_MonthlyTable",
        "subject_count", "has_3party_block", "missing_blocks",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in inventory_rows:
            w.writerow(r)
    print(f"Wrote: {csv_path}")

    # Variants summary
    all_teachers_seen: set[str] = set()
    for tlist in teacher_variants.values():
        all_teachers_seen.update(tlist)
    all_subjects_seen: set[str] = set()
    for slist in subject_variants.values():
        all_subjects_seen.update(slist)
    all_grades_seen: set[str] = set()
    for glist in grade_variants.values():
        all_grades_seen.update(glist)

    variants = {
        "teacher_canonical": teacher_canon,
        "teacher_variants_seen": sorted(all_teachers_seen),
        "subject_variants_seen": sorted(all_subjects_seen),
        "grade_variants_seen": sorted(all_grades_seen),
        "by_tab": {
            t: {
                "teachers": sorted(set(teacher_variants.get(t, []))),
                "subjects": sorted(set(subject_variants.get(t, []))),
                "grades": sorted(set(grade_variants.get(t, []))),
            }
            for t in sorted({*teacher_variants, *subject_variants, *grade_variants})
        },
    }
    var_path = OUT_DIR / "variants.json"
    var_path.write_text(json.dumps(variants, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote: {var_path}")

    # 簡易サマリ
    n_tabs = len(inventory_rows)
    print(f"\nTabs: {n_tabs}")
    print(f"Teacher canonical: {len(teacher_canon)}")
    print(f"Teacher variants seen in student tabs: {len(all_teachers_seen)}")
    print(f"Subject variants: {len(all_subjects_seen)}")
    print(f"Grade variants: {len(all_grades_seen)}")
    missing_count = sum(1 for r in inventory_rows if r["missing_blocks"])
    print(f"Tabs with missing blocks: {missing_count}")
    no_3party = sum(1 for r in inventory_rows if r["has_3party_block"] == "N")
    print(f"Tabs without 三者面談 block: {no_3party}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
