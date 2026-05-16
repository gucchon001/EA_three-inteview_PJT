from __future__ import annotations

from pathlib import Path

from eb_app.monthly_reports.llm_messages import build_monthly_report_messages


def test_build_monthly_report_messages_preserves_static_poc_chunk_order(tmp_path: Path):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    tone = tmp_path / "tone.md"
    tone.write_text("FAMILY TONE", encoding="utf-8")

    messages = build_monthly_report_messages(
        artifact="md",
        template_path=template,
        rules_excerpt_path=tone,
        bundle="SOURCE BUNDLE",
        ideal_plain="IDEAL PLAIN",
        structure_html="<section>STRUCTURE</section>",
        prompt_scope_notes="TARGET ONLY",
    )

    assert [message["role"] for message in messages] == ["system", "user"]
    assert "複数生徒" in messages[0]["content"]
    assert "FAMILY TONE" in messages[0]["content"]

    user = messages[1]["content"]
    expected_order = [
        "## コンテンツ契約",
        "PATTERN B CONTRACT",
        "## 対象レポートのスコープ",
        "TARGET ONLY",
        "## 根拠ソース",
        "SOURCE BUNDLE",
        "## 構造レイアウト参考",
        "<section>STRUCTURE</section>",
        "## 語感・文長の参考",
        "IDEAL PLAIN",
        "## 指示",
    ]
    positions = [user.index(fragment) for fragment in expected_order]
    assert positions == sorted(positions)


def test_build_monthly_report_messages_omits_empty_prompt_scope_notes(tmp_path: Path):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")

    messages = build_monthly_report_messages(
        artifact="html",
        template_path=template,
        rules_excerpt_path=None,
        bundle="SOURCE BUNDLE",
        ideal_plain="",
        structure_html="",
        prompt_scope_notes="  ",
    )

    assert "## 対象レポートのスコープ" not in messages[1]["content"]
    assert "完全な1ファイルの UTF-8 HTML" in messages[0]["content"]


def test_build_monthly_report_messages_includes_anonymized_multistudent_scope_fixture(tmp_path: Path):
    fixture_dir = Path("tests/fixtures/monthly_reports/economics_multistudent_scope")
    bundle = "\n\n".join(
        [
            (fixture_dir / "_gws_doc_teacher_MTG_gemini.txt").read_text(encoding="utf-8"),
            (fixture_dir / "_gws_SL_lesson_plan_A1-M250_values.json").read_text(
                encoding="utf-8"
            ),
            (fixture_dir / "_gws_student_A1-Z200_values.json").read_text(encoding="utf-8"),
        ]
    )
    prompt_scope_notes = (fixture_dir / "expected_prompt_scope_notes.txt").read_text(
        encoding="utf-8"
    )
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")

    messages = build_monthly_report_messages(
        artifact="md",
        template_path=template,
        rules_excerpt_path=None,
        bundle=bundle,
        ideal_plain="",
        structure_html="",
        prompt_scope_notes=prompt_scope_notes,
    )

    user = messages[1]["content"]
    scope_position = user.index("## 対象レポートのスコープ")
    source_position = user.index("## 根拠ソース")
    assert scope_position < source_position
    assert "対象は対象生徒A様の Economics のみ" in user
    assert "対象外生徒B様" in user
    assert "対象外生徒B様の試験対策" in user
