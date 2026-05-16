from pathlib import Path
import re


FIXTURE_DIR = Path("tests/fixtures/monthly_reports/economics_multistudent_scope")


def test_economics_multistudent_scope_fixture_is_anonymized_and_complete():
    expected_files = {
        "README.md",
        "_gws_doc_teacher_MTG_gemini.txt",
        "_gws_SL_lesson_plan_A1-M250_values.json",
        "_gws_student_A1-Z200_values.json",
        "expected_prompt_scope_notes.txt",
    }

    assert {path.name for path in FIXTURE_DIR.iterdir()} == expected_files

    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(FIXTURE_DIR.iterdir())
        if path.is_file()
    )
    assert "対象生徒A" in combined
    assert "対象外生徒B" in combined
    assert "Economics" in combined
    assert "prompt_scope_notes" in combined

    forbidden_patterns = [
        r"https?://",
        r"docs\.google\.com",
        r"spreadsheets",
        r"\b[A-Za-z0-9_-]{25,}\b",
        r"REAL_",
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, combined) is None
