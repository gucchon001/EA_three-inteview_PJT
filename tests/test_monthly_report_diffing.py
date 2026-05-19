from eb_app.monthly_reports.diffing import diff_markdown_lines


def _pairs(rows):
    return [(row.kind, row.text) for row in rows]


def test_diff_markdown_lines_returns_unchanged_rows_for_identical_text():
    rows = diff_markdown_lines("alpha\nbeta", "alpha\nbeta")

    assert _pairs(rows) == [
        ("unchanged", "alpha"),
        ("unchanged", "beta"),
    ]


def test_diff_markdown_lines_marks_added_line():
    rows = diff_markdown_lines("alpha", "alpha\nbeta")

    assert _pairs(rows) == [
        ("unchanged", "alpha"),
        ("added", "beta"),
    ]


def test_diff_markdown_lines_marks_removed_line():
    rows = diff_markdown_lines("alpha\nbeta", "alpha")

    assert _pairs(rows) == [
        ("unchanged", "alpha"),
        ("removed", "beta"),
    ]


def test_diff_markdown_lines_represents_changed_line_as_removed_then_added():
    rows = diff_markdown_lines("alpha\nold", "alpha\nnew")

    assert _pairs(rows) == [
        ("unchanged", "alpha"),
        ("removed", "old"),
        ("added", "new"),
    ]


def test_diff_markdown_lines_returns_no_rows_for_empty_texts():
    assert diff_markdown_lines("", "") == []


def test_diff_markdown_lines_escapes_plain_text_payloads():
    rows = diff_markdown_lines("<old & value>", "<new & value>")

    assert _pairs(rows) == [
        ("removed", "&lt;old &amp; value&gt;"),
        ("added", "&lt;new &amp; value&gt;"),
    ]
