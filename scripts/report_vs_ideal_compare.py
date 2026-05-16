"""Compare Pattern B-like HTML candidates against a user-approved reference (ideal).

Metrics:
  - plain_text_similarity: difflib.SequenceMatcher ratio on whitespace-normalized visible text (tags stripped)
  - html_line_counts: raw line counts
  - diff_histogram: +/- line counts from unified diff (excluding file headers)

Usage (repo root):
  python scripts/report_vs_ideal_compare.py \\
    --ideal docs/samples/monthly-reports/fixtures/tokura_2026-04_user_ideal.html \\
    --candidates docs/samples/monthly-reports/monthly_2026-04_tokura_v2_report.html \\
    --write-json docs/samples/monthly-reports/tokura_v2_vs_ideal_metrics.json
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path


def html_to_plain(html: str) -> str:
    t = re.sub(r"(?is)<script\b[^>]*>.*?</script>", " ", html)
    t = re.sub(r"(?is)<style\b[^>]*>.*?</style>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def diff_histogram(a_lines: list[str], b_lines: list[str]) -> tuple[int, int]:
    plus = minus = 0
    for line in difflib.unified_diff(a_lines, b_lines, lineterm=""):
        if line.startswith("+++ ") or line.startswith("--- ") or line.startswith("@@"):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            plus += 1
        elif line.startswith("-") and not line.startswith("---"):
            minus += 1
    return plus, minus


def main() -> int:
    ap = argparse.ArgumentParser(description="HTML report vs ideal 近接度（簡易）")
    ap.add_argument("--ideal", type=Path, required=True)
    ap.add_argument(
        "--candidates",
        type=Path,
        nargs="+",
        required=True,
        help="比較する HTML（v2・v3 など）",
    )
    ap.add_argument("--write-json", type=Path, default=None, help="集計結果を JSON へ")
    args = ap.parse_args()

    ideal_path = args.ideal.resolve()
    ideal_txt = ideal_path.read_text(encoding="utf-8", errors="replace")
    ideal_plain = html_to_plain(ideal_txt)
    ideal_lines = ideal_txt.splitlines()

    out: dict = {
        "ideal": str(ideal_path),
        "ideal_lines": len(ideal_lines),
        "candidates": [],
    }

    print(f"ideal: {ideal_path} ({len(ideal_lines)} lines)\n")

    for cand in args.candidates:
        p = cand.resolve()
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        plain = html_to_plain(text)
        sim = difflib.SequenceMatcher(a=ideal_plain, b=plain).ratio()
        dplus, dminus = diff_histogram(ideal_lines, lines)
        row = {
            "path": str(p),
            "lines": len(lines),
            "plain_text_similarity": round(sim, 6),
            "diff_lines_added_vs_ideal": dplus,
            "diff_lines_removed_vs_ideal": dminus,
        }
        out["candidates"].append(row)
        print(f"Candidate: {p.name}")
        print(f"  lines: {len(lines)}")
        print(f"  plain_text_similarity (vs ideal): {sim:.4f}")
        print(f"  unified diff +/- (coarse vs ideal): +{dplus} / -{dminus}")
        print()

    if args.write_json:
        args.write_json.parent.mkdir(parents=True, exist_ok=True)
        args.write_json.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.write_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
