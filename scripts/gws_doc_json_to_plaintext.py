"""Google Docs API 形式の JSON（gws documents get）からプレーンテキストを抽出する。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

def _walk_structural(items: list | None, chunks: list[str]) -> None:
    for item in items or []:
        if "paragraph" in item:
            for el in item["paragraph"].get("elements") or []:
                if "textRun" in el:
                    chunks.append(el["textRun"].get("content", ""))
                elif "dateElement" in el:
                    props = el["dateElement"].get("dateElementProperties") or {}
                    chunks.append(props.get("displayText", ""))
            continue
        if "table" in item:
            for row in item["table"].get("tableRows") or []:
                for cell in row.get("tableCells") or []:
                    _walk_structural(cell.get("content"), chunks)
            chunks.append("\n")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("input_json", type=Path)
    p.add_argument("output_txt", type=Path)
    args = p.parse_args()
    data = json.loads(args.input_json.read_text(encoding="utf-8"))
    body = data.get("body") or {}
    chunks: list[str] = []
    _walk_structural(body.get("content"), chunks)
    text = "".join(chunks)
    args.output_txt.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
