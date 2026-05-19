from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print(f"+ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> int:
    checks = [
        [sys.executable, "-m", "compileall", "src", "tests"],
        [sys.executable, "-m", "pytest"],
    ]

    for command in checks:
        run(command)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
