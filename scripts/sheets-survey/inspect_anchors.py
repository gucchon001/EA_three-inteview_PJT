"""sample-extracts/ から各タブの「ラベル候補」を抽出してアンカー設計を支援する。

用途:
  1. テンプレート（index 0）の構造を可視化
  2. 生徒個別タブ群で共通する文字列の頻度を集計
  3. パターン分類（行数 / マージ数）

出力: stdout に整形テキスト
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXTRACTS_DIR = REPO_ROOT / "docs" / "sheets-migration" / "sample-extracts"

MASTER_TABS = {"★EB塾教師一覧", "★EB塾生徒一覧"}
TEMPLATE_TAB_PREFIX = "【原本】"


def is_student_tab(title: str) -> bool:
    return title not in MASTER_TABS and not title.startswith(TEMPLATE_TAB_PREFIX)


def cell(values: list[list[str]], r: int, c: int) -> str:
    if r >= len(values):
        return ""
    row = values[r]
    if c >= len(row):
        return ""
    return (row[c] or "").strip()


def labels_in_col(values: list[list[str]], col: int, max_rows: int = 200) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for r in range(min(max_rows, len(values))):
        v = cell(values, r, col)
        if v and len(v) <= 60:
            out.append((r, v))
    return out


def all_text_cells(values: list[list[str]], max_rows: int = 200) -> list[tuple[int, int, str]]:
    out: list[tuple[int, int, str]] = []
    for r, row in enumerate(values[:max_rows]):
        for c, v in enumerate(row):
            v = (v or "").strip()
            if v and len(v) <= 60:
                out.append((r, c, v))
    return out


def main() -> int:
    files = sorted(EXTRACTS_DIR.glob("*.json"))
    print(f"# Inspect anchors  ({len(files)} files)\n")

    template = None
    students: list[tuple[str, dict]] = []
    masters: list[tuple[str, dict]] = []

    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        title = d["title"]
        if title.startswith(TEMPLATE_TAB_PREFIX):
            template = (title, d)
        elif title in MASTER_TABS:
            masters.append((title, d))
        else:
            students.append((title, d))

    # ===== TEMPLATE =====
    if template:
        title, d = template
        print(f"## Template: {title}")
        print(f"  rows={len(d['values'])} merges={len(d['merged_ranges'])}")
        print("  Column A (col=0) labels:")
        for r, v in labels_in_col(d["values"], 0)[:80]:
            print(f"    A{r+1}: {v}")
        print("  Column B (col=1) labels (first 40):")
        for r, v in labels_in_col(d["values"], 1)[:40]:
            print(f"    B{r+1}: {v}")
        print()

    # ===== STUDENTS: row count distribution =====
    print(f"## Students ({len(students)})")
    rows_dist = Counter(len(d["values"]) for _, d in students)
    merges_dist = Counter(len(d["merged_ranges"]) for _, d in students)
    print(f"  rows distribution: {dict(sorted(rows_dist.items()))}")
    print(f"  merges distribution: {dict(sorted(merges_dist.items()))}")
    print()

    # Cluster: by (rows, merges) signature
    clusters: dict[tuple[int, int], list[str]] = defaultdict(list)
    for title, d in students:
        sig = (len(d["values"]), len(d["merged_ranges"]))
        clusters[sig].append(title)
    print("  Clusters (rows, merges) -> count, sample:")
    for sig, names in sorted(clusters.items()):
        sample = names[0] if len(names) else ""
        print(f"    {sig} -> {len(names):>2}  e.g. {sample}")
    print()

    # ===== ANCHOR CANDIDATES =====
    # 個別タブでよく出る短い文字列を集計
    label_counter: Counter[str] = Counter()
    label_positions: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for title, d in students:
        seen: set[str] = set()
        for r, c, v in all_text_cells(d["values"]):
            if len(v) > 30:
                continue
            if re.match(r"^[\d\.\-\+/]+$", v):  # numeric only skip
                continue
            if v in seen:
                continue
            seen.add(v)
            label_counter[v] += 1
            label_positions[v].append((r, c))

    print("## Anchor candidates (frequent short labels in student tabs)")
    threshold = max(5, int(len(students) * 0.5))
    print(f"  threshold: appearing in >= {threshold} of {len(students)} tabs\n")
    high_freq = [(lab, n) for lab, n in label_counter.items() if n >= threshold]
    high_freq.sort(key=lambda x: -x[1])
    for lab, n in high_freq[:80]:
        positions = label_positions[lab]
        rows = Counter(r for r, _ in positions)
        cols = Counter(c for _, c in positions)
        top_row = rows.most_common(1)[0]
        top_col = cols.most_common(1)[0]
        print(f"  [{n:>2}] '{lab}'  most_freq_pos=(r{top_row[0]+1},c{chr(ord('A')+top_col[0])})  pos_var=rows{len(rows)}/cols{len(cols)}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
