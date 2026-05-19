from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from html import escape
from typing import Literal


DiffRowKind = Literal["unchanged", "added", "removed"]


@dataclass(frozen=True)
class MarkdownDiffRow:
    kind: DiffRowKind
    text: str


def diff_markdown_lines(before: str, after: str) -> list[MarkdownDiffRow]:
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    rows: list[MarkdownDiffRow] = []

    matcher = SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    for tag, before_start, before_end, after_start, after_end in matcher.get_opcodes():
        if tag == "equal":
            rows.extend(
                _rows("unchanged", before_lines[before_start:before_end])
            )
        elif tag == "delete":
            rows.extend(_rows("removed", before_lines[before_start:before_end]))
        elif tag == "insert":
            rows.extend(_rows("added", after_lines[after_start:after_end]))
        elif tag == "replace":
            rows.extend(_rows("removed", before_lines[before_start:before_end]))
            rows.extend(_rows("added", after_lines[after_start:after_end]))

    return rows


def _rows(kind: DiffRowKind, lines: list[str]) -> list[MarkdownDiffRow]:
    return [MarkdownDiffRow(kind=kind, text=escape(line)) for line in lines]
