from pathlib import Path

from eb_app.monthly_reports.jobs import JobStatus, MockJobStore
from eb_app.monthly_reports.worker import run_next_queued_monthly_report_job
from eb_app.monthly_reports.workflow import StaticMonthlyReportProvider


def test_run_next_queued_monthly_report_job_runs_oldest_queued_job(tmp_path: Path):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = MockJobStore()
    first = store.create_job(target_month="2026-04", household_key="first")
    second = store.create_job(target_month="2026-04", household_key="second")
    store.record_source(
        first.public_id,
        source_type="text",
        display_name="source",
        snapshot_text="first source",
    )
    store.record_source(
        second.public_id,
        source_type="text",
        display_name="source",
        snapshot_text="second source",
    )

    result = run_next_queued_monthly_report_job(
        store,
        provider=StaticMonthlyReportProvider("# draft"),
        template_path=template,
    )

    assert result is not None
    assert result.public_id == first.public_id
    assert result.status == JobStatus.SUCCEEDED
    assert store.get(second.public_id).status == JobStatus.QUEUED
    assert store.list_artifacts(first.public_id)[0].content == "# draft"
    assert store.list_llm_calls(first.public_id)[0].prompt_kind == "report"


def test_run_next_queued_monthly_report_job_returns_none_when_no_queued_job(
    tmp_path: Path,
):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = MockJobStore()
    running = store.create_job(target_month="2026-04", household_key="running")
    store.start_next(running.public_id)

    result = run_next_queued_monthly_report_job(
        store,
        provider=StaticMonthlyReportProvider("# draft"),
        template_path=template,
    )

    assert result is None
    assert store.get(running.public_id).status == JobStatus.RUNNING
