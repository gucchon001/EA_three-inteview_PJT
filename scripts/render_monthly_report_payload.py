#!/usr/bin/env python3
"""
ペイロード JSON + Jinja2 テンプレで Pattern B の HTML を決定的に出力する。
LLM は本文 JSON の生成にのみ使い、このスクリプトで DOM/CSS の形を固定する。

既定テンプレ: docs/samples/monthly-reports/templates/pattern_b_compact_01_05.html.j2
例（十倉・v2 形の再現確認）:

  pip install Jinja2
  python scripts/render_monthly_report_payload.py \\
    --payload docs/samples/monthly-reports/fixtures/payloads/tokura_2026-04_v2_shape.json \\
    --output docs/samples/monthly-reports/_tmp_tokura_from_payload.html

ブラウザの「生成」ボタンから叩くときは、このスクリプトと同様の処理をサーバ側で行うか、
事前に構築したペイロードを保存してレンダのみ行う。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    p = argparse.ArgumentParser(description="月次レポート: JSON ペイロードを Jinja2 で HTML にレンダする")
    p.add_argument(
        "--payload",
        type=Path,
        required=True,
        help="ペイロード JSON（fixtures/payloads/*.json）",
    )
    p.add_argument(
        "--template-dir",
        type=Path,
        default=ROOT / "docs/samples/monthly-reports/templates",
        help="Jinja テンプレのディレクトリ",
    )
    p.add_argument(
        "--template-name",
        type=str,
        default="pattern_b_compact_01_05.html.j2",
        help="テンプレファイル名（--template-dir 内）",
    )
    p.add_argument("--output", type=Path, required=True, help="出力する .html のパス")
    args = p.parse_args()

    try:
        from jinja2 import Environment, FileSystemLoader, StrictUndefined  # noqa: PLC0415
    except ImportError:
        print("Jinja2 が必要です。例: pip install Jinja2", file=sys.stderr)
        return 1

    tpl_dir = args.template_dir.resolve()
    tpl_name = args.template_name
    if not (tpl_dir / tpl_name).is_file():
        print(f"テンプレが見つかりません: {tpl_dir / tpl_name}", file=sys.stderr)
        return 1

    payload_path = args.payload.resolve()
    if not payload_path.is_file():
        print(f"payload が見つかりません: {payload_path}", file=sys.stderr)
        return 1

    raw = payload_path.read_text(encoding="utf-8")
    data = json.loads(raw)

    env = Environment(
        loader=FileSystemLoader(str(tpl_dir)),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(tpl_name)

    html = template.render(**data)

    out = args.output.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8", newline="\n")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
