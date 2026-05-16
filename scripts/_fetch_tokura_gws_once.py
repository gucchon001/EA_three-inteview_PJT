"""十倉世帯向けの後方互換ラッパ。新規世帯は fetch_monthly_gws_sources.py を直接使用すること。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    script = ROOT / "scripts" / "fetch_monthly_gws_sources.py"
    out_dir = ROOT / "samples" / "reports" / "household_tokura" / "sources"
    cmd = [
        sys.executable,
        str(script),
        "--spreadsheet-id",
        "1d0_0kj2C-kjgikWRGsorTw8wADYIk0Z4j59AwFDzaDo",
        "--document-id",
        "1KbH40l3U3oXkXTLrlKAfnIZUmIr5_OcrITz1L_QS-fs",
        "--out-dir",
        str(out_dir),
    ]
    raise SystemExit(subprocess.call(cmd, cwd=ROOT))


if __name__ == "__main__":
    main()
