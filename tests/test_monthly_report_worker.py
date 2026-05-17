from pathlib import Path
from datetime import datetime, timedelta, timezone

from eb_app.monthly_reports.jobs import JobStatus, MockJobStore
from eb_app.monthly_reports.worker import (
    WorkerRunStatus,
    run_next_queued_monthly_report_job,
    run_next_queued_monthly_report_job_result,
)
from eb_app.monthly_reports.workflow import (
    LLMCompletion,
    ProviderCallError,
    StaticMonthlyReportProvider,
)


class CountingProvider:
    def __init__(self, content: str = "# draft") -> None:
        self.content = content
        self.calls = 0

    def complete(self, *, messages, model=None):
        self.calls += 1
        return LLMCompletion(content=self.content, resolved_model="mock/report-model")


class FailingProvider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, *, messages, model=None):
        self.calls += 1
        raise ProviderCallError("temporary provider failure")


class CancelAfterClaimStore(MockJobStore):
    def claim_next_runnable_job(
        self,
        owner_user_id: str | None = None,
        *,
        lease_timeout_seconds: int | None = None,
    ):
        return self._claim_and_cancel(owner_user_id=owner_user_id)

    def claim_next_queued_job(self, owner_user_id: str | None = None):
        return self._claim_and_cancel(owner_user_id=owner_user_id)

    def _claim_and_cancel(self, owner_user_id: str | None = None):
        claimed = super().claim_next_runnable_job(owner_user_id=owner_user_id)
        if claimed is not None:
            self.request_cancel(claimed.public_id)
        return claimed


class CancelBeforeWorkflowStore(MockJobStore):
    def __init__(self) -> None:
        super().__init__()
        self.get_calls_after_claim = 0

    def get(self, public_id: str):
        job = super().get(public_id)
        if job.status == JobStatus.RUNNING:
            self.get_calls_after_claim += 1
            if self.get_calls_after_claim == 2:
                self.request_cancel(public_id)
        return super().get(public_id)


class TouchCountingStore(MockJobStore):
    def __init__(self) -> None:
        super().__init__()
        self.touched_job_ids: list[str] = []

    def touch_worker_job(self, public_id: str):
        self.touched_job_ids.append(public_id)
        return super().touch_worker_job(public_id)


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


def test_run_next_queued_monthly_report_job_fills_missing_reproducibility_meta(
    tmp_path: Path,
):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = MockJobStore()
    job = store.create_job(target_month="2026-04", household_key="meta")
    provider = StaticMonthlyReportProvider(
        "# draft",
        resolved_model="mock/resolved-model",
    )

    result = run_next_queued_monthly_report_job(
        store,
        provider=provider,
        template_path=template,
        prompt_version="monthly-report-vworker.1",
        model_report="mock/report-model",
        app_version="worker-app-version",
    )

    assert result is not None
    assert result.status == JobStatus.SUCCEEDED
    assert result.prompt_version == "monthly-report-vworker.1"
    assert result.template_hash is not None and result.template_hash.startswith("sha256:")
    assert result.model_report == "mock/report-model"
    assert result.resolved_model_report == "mock/resolved-model"
    assert result.source_bundle_hash is not None and result.source_bundle_hash.startswith(
        "sha256:"
    )
    assert result.app_version == "worker-app-version"
    assert provider.last_model == "mock/report-model"


def test_run_next_queued_monthly_report_job_can_filter_by_owner(tmp_path: Path):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = MockJobStore()
    other = store.create_job(
        target_month="2026-04",
        household_key="other",
        owner_user_id="other-owner",
    )
    target = store.create_job(
        target_month="2026-04",
        household_key="target",
        owner_user_id="target-owner",
    )

    result = run_next_queued_monthly_report_job(
        store,
        provider=StaticMonthlyReportProvider("# draft"),
        template_path=template,
        owner_user_id="target-owner",
    )

    assert result is not None
    assert result.public_id == target.public_id
    assert result.status == JobStatus.SUCCEEDED
    assert store.get(other.public_id).status == JobStatus.QUEUED


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


def test_run_next_queued_monthly_report_job_result_summarizes_success(
    tmp_path: Path,
):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = MockJobStore()
    job = store.create_job(target_month="2026-04", household_key="summary")

    result = run_next_queued_monthly_report_job_result(
        store,
        provider=StaticMonthlyReportProvider("# draft"),
        template_path=template,
    )

    assert result.status == WorkerRunStatus.SUCCEEDED
    assert result.claimed_job_id == job.public_id
    assert result.job is not None
    assert result.job.status == JobStatus.SUCCEEDED


def test_run_next_queued_monthly_report_job_result_cancels_before_provider_call(
    tmp_path: Path,
):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = CancelAfterClaimStore()
    job = store.create_job(target_month="2026-04", household_key="cancel")
    provider = CountingProvider()

    result = run_next_queued_monthly_report_job_result(
        store,
        provider=provider,
        template_path=template,
    )

    assert result.status == WorkerRunStatus.CANCELLED
    assert result.claimed_job_id == job.public_id
    assert result.job is not None
    assert result.job.status == JobStatus.CANCELLED
    assert provider.calls == 0


def test_run_next_queued_monthly_report_job_result_treats_cancel_race_as_cancelled(
    tmp_path: Path,
):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = CancelBeforeWorkflowStore()
    job = store.create_job(target_month="2026-04", household_key="cancel-race")
    provider = CountingProvider()

    result = run_next_queued_monthly_report_job_result(
        store,
        provider=provider,
        template_path=template,
    )

    assert result.status == WorkerRunStatus.CANCELLED
    assert result.claimed_job_id == job.public_id
    assert result.job is not None
    assert result.job.status == JobStatus.CANCELLED
    assert provider.calls == 0


def test_run_next_queued_monthly_report_job_result_records_worker_attempt(
    tmp_path: Path,
):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = MockJobStore()
    job = store.create_job(target_month="2026-04", household_key="attempt")

    result = run_next_queued_monthly_report_job_result(
        store,
        provider=StaticMonthlyReportProvider("# draft"),
        template_path=template,
    )

    assert result.status == WorkerRunStatus.SUCCEEDED
    assert result.job is not None
    assert result.job.public_id == job.public_id
    assert result.job.worker_attempts == 1
    assert result.job.worker_last_claimed_at is not None


def test_run_next_queued_monthly_report_job_result_touches_claimed_job(
    tmp_path: Path,
):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = TouchCountingStore()
    job = store.create_job(target_month="2026-04", household_key="heartbeat")

    result = run_next_queued_monthly_report_job_result(
        store,
        provider=StaticMonthlyReportProvider("# draft"),
        template_path=template,
    )

    assert result.status == WorkerRunStatus.SUCCEEDED
    assert store.touched_job_ids == [job.public_id]
    assert result.job is not None
    assert result.job.worker_last_claimed_at is not None


def test_run_next_queued_monthly_report_job_result_reclaims_stale_fetch_sources_job(
    tmp_path: Path,
):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = MockJobStore()
    stale = store.create_job(target_month="2026-04", household_key="stale")
    store.claim_next_queued_job()
    stale.worker_last_claimed_at = datetime.now(timezone.utc) - timedelta(seconds=120)

    result = run_next_queued_monthly_report_job_result(
        store,
        provider=StaticMonthlyReportProvider("# draft"),
        template_path=template,
        lease_timeout_seconds=60,
    )

    assert result.status == WorkerRunStatus.SUCCEEDED
    assert result.claimed_job_id == stale.public_id
    assert result.job is not None
    assert result.job.worker_attempts == 2
    assert result.job.status == JobStatus.SUCCEEDED


def test_run_next_queued_monthly_report_job_result_does_not_reclaim_fresh_running_job(
    tmp_path: Path,
):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = MockJobStore()
    store.create_job(target_month="2026-04", household_key="fresh")
    store.claim_next_queued_job()

    result = run_next_queued_monthly_report_job_result(
        store,
        provider=StaticMonthlyReportProvider("# draft"),
        template_path=template,
        lease_timeout_seconds=60,
    )

    assert result.status == WorkerRunStatus.NO_JOB


def test_run_next_queued_monthly_report_job_result_requeues_provider_failure_until_limit(
    tmp_path: Path,
):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = MockJobStore()
    job = store.create_job(
        target_month="2026-04",
        household_key="retry",
        max_worker_attempts=2,
    )
    provider = FailingProvider()

    first = run_next_queued_monthly_report_job_result(
        store,
        provider=provider,
        template_path=template,
    )

    assert first.status == WorkerRunStatus.RETRY_SCHEDULED
    assert first.job is not None
    assert first.job.status == JobStatus.QUEUED
    assert first.job.worker_attempts == 1

    second = run_next_queued_monthly_report_job_result(
        store,
        provider=provider,
        template_path=template,
    )

    assert second.status == WorkerRunStatus.FAILED
    assert second.job is not None
    assert second.job.public_id == job.public_id
    assert second.job.status == JobStatus.FAILED
    assert second.job.worker_attempts == 2
    assert provider.calls == 2
