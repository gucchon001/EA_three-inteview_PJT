"""
NotebookLM ノート（EA_生徒状況分析など）の notebook_get JSON から、
ソースタイトルをご家庭（または受講生）単位で件数集計する。

使用例:
  nlm notebook get <notebook_id> --json | python scripts/notebooklm_count_sources_by_household.py
  python scripts/notebooklm_count_sources_by_household.py scripts/_ea_notebook_get.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter


META_PREFIXES = (
    "【ソース】",
    "ご家庭向け面談メモ",
    "教師MTG整理メモ",
    "採用時にコピー",
    "教育現場のAI",
    "月次メール_",
    "AI文字起こし",
    "メールテンプレ",
    "ワークフロー_BeforeAfter",
    "ノウハウ可視化",
)


def canonical_key(title: str) -> str | None:
    """None = メタ（共通）にまとめる。"""
    t = title.strip()

    if any(t.startswith(p) for p in META_PREFIXES):
        return None
    if t.startswith("ご家庭向け面談メモ"):
        return None

    if t.startswith("260319_"):
        m = re.match(r"^260319_(.+?)さま\s", t)
        return m.group(1) + "さま" if m else t[:40]

    m = re.match(r"^(\d{5})\s+(.+)$", t)
    if m and "Google Drive" in t:
        rest = m.group(2)
        rest = rest.split(" - Google Drive")[0].strip()
        m2 = re.match(r"^(.+?さま)", rest)
        if m2:
            return m2.group(1).strip()
        return rest[:50]

    if t.startswith("SSST"):
        m = re.match(r"^SSST\s+(.+?さま)", t)
        return (m.group(1) + "（SSST）") if m else "SSST"

    if t == "岩井 - Google Drive":
        return "岩井さま"

    for prefix in (
        "儀賀さま",
        "十倉さま",
        "和佐田さま",
        "小林 慧さま",
        "川口さま",
        "武石さま",
        "高浜さま",
        "高藤さま",
    ):
        if t.startswith(prefix):
            return prefix

    return f"要確認: {t[:45]}"


def main() -> None:
    if len(sys.argv) < 2:
        raw = json.load(sys.stdin)
    else:
        with open(sys.argv[1], encoding="utf-8") as f:
            raw = json.load(f)
    if "value" in raw:
        raw = raw["value"]
    sources = raw["sources"]

    meta = 0
    counts: Counter[str] = Counter()
    for s in sources:
        key = canonical_key(s["title"])
        if key is None:
            meta += 1
        else:
            counts[key] += 1

    print(f"ノート: {raw.get('title', '')}  /  source_count: {raw.get('source_count', len(sources))}")
    print(f"共通・メタ: {meta}")
    print("---")
    for k, n in counts.most_common():
        print(f"{n:3d}\t{k}")
    print("---")
    print(f"個別キー計: {sum(counts.values())}  + メタ {meta}  =  {sum(counts.values()) + meta}")


if __name__ == "__main__":
    main()
