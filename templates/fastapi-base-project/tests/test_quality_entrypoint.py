from __future__ import annotations

from pathlib import Path


def test_quality_check_entrypoint_is_documented_and_present():
    project_root = Path(__file__).resolve().parents[1]
    check_script = project_root / "scripts" / "check.py"
    readme = (project_root / "README.md").read_text(encoding="utf-8")

    assert check_script.exists()
    assert "python scripts/check.py" in readme
