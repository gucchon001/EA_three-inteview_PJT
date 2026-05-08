"""
NotebookLM MCP の source_get_content の応答 JSON から content を取り出し、UTF-8 で書き出す。

- 出力パスが .txt のとき: 本文のみ（従来どおり）
- 出力パスが .md のとき: YAML フロントマター（JSON のメタ＋ schema_version）のあとに本文

例（PowerShell）:
  python scripts/notebooklm_json_to_txt.py samples/reports/household_giga/sources/_nl_response.json samples/reports/household_giga/sources/01_教師MTG_20260225_全文.md

stdin から読む場合:
  type _nl_response.json | python scripts/notebooklm_json_to_txt.py - -
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _markdown_with_frontmatter(data: dict, body: str) -> str:
    lines = ["---", "schema_version: 1", "kind: notebooklm_export"]
    for k, v in data.items():
        if k == "content":
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    src, dst = sys.argv[1], sys.argv[2]
    if src == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(src).read_text(encoding="utf-8")
    data = json.loads(raw)
    if isinstance(data, dict) and "content" in data:
        text = data["content"]
    else:
        text = str(data)
    # Meet メモの縦タブなどを改行に近づける
    text = text.replace("\u000b", "\n")
    out = Path(dst)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".md" and isinstance(data, dict) and "content" in data:
        payload = _markdown_with_frontmatter(data, text)
    else:
        payload = text
    out.write_text(payload, encoding="utf-8", newline="\n")
    print(f"Wrote {len(payload)} chars -> {out.resolve().as_posix()}")


if __name__ == "__main__":
    main()
