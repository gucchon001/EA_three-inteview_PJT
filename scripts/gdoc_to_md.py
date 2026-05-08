"""Google Docs JSON → Markdown 変換スクリプト
Usage: gws docs documents get --params '{"documentId":"DOC_ID"}' | python gdoc_to_md.py
"""
import json, sys

HEADING_MAP = {
    "HEADING_1": "# ",
    "HEADING_2": "## ",
    "HEADING_3": "### ",
    "HEADING_4": "#### ",
    "HEADING_5": "##### ",
    "HEADING_6": "###### ",
    "NORMAL_TEXT": "",
    "TITLE": "# ",
    "SUBTITLE": "## ",
}

def extract_text(elements):
    text = ""
    for el in elements:
        tr = el.get("textRun", {})
        text += tr.get("content", "")
    return text

def convert(data):
    content = data.get("body", {}).get("content", [])
    lines = []
    list_state = {}  # listId -> indent level

    for block in content:
        if "paragraph" in block:
            para = block["paragraph"]
            style = para.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
            prefix = HEADING_MAP.get(style, "")
            text = extract_text(para.get("elements", []))

            bullet = para.get("bullet")
            if bullet:
                nest = bullet.get("nestingLevel", 0)
                indent = "  " * nest
                text = text.rstrip("\n")
                lines.append(f"{indent}- {text}")
            else:
                text = text.rstrip("\n")
                if text:
                    lines.append(f"{prefix}{text}")
                else:
                    lines.append("")

    return "\n".join(lines)

if __name__ == "__main__":
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
        if "error" in data:
            print(f"ERROR: {data['error']}", file=sys.stderr)
            sys.exit(1)
        print(convert(data))
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        sys.exit(1)
