from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eb_app.monthly_reports.jobs import JobStatus, MockJob
from eb_app.monthly_reports.workflow import (
    JobStore,
    MonthlyReportProvider,
    run_claimed_monthly_report_job,
)


class WorkerRunStatus:
    NO_JOB = "no_job"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY_SCHEDULED = "retry_scheduled"


@dataclass(frozen=True)
class WorkerRunResult:
    status: str
    claimed_job_id: str | None = None
    job: MockJob | None = None
    error_type: str | None = None
    error_message: str | None = None


def run_next_queued_monthly_report_job(
    store: JobStore,
    *,
    provider: MonthlyReportProvider,
    template_path: Path,
    owner_user_id: str | None = None,
    lease_timeout_seconds: int | None = None,
    prompt_version: str | None = None,
    model_report: str | None = None,
    app_version: str | None = None,
) -> MockJob | None:
    result = run_next_queued_monthly_report_job_result(
        store,
        provider=provider,
        template_path=template_path,
        owner_user_id=owner_user_id,
        lease_timeout_seconds=lease_timeout_seconds,
        prompt_version=prompt_version,
        model_report=model_report,
        app_version=app_version,
    )
    return result.job


def run_next_queued_monthly_report_job_result(
    store: JobStore,
    *,
    provider: MonthlyReportProvider,
    template_path: Path,
    owner_user_id: str | None = None,
    lease_timeout_seconds: int | None = None,
    prompt_version: str | None = None,
    model_report: str | None = None,
    app_version: str | None = None,
) -> WorkerRunResult:
    claim_runnable = getattr(store, "claim_next_runnable_job", None)
    if callable(claim_runnable):
        claimed = claim_runnable(
            owner_user_id=owner_user_id,
            lease_timeout_seconds=lease_timeout_seconds,
        )
    else:
        claimed = store.claim_next_queued_job(owner_user_id=owner_user_id)
    if claimed is None:
        return WorkerRunResult(status=WorkerRunStatus.NO_JOB)

    claimed = store.get(claimed.public_id)
    cancelled = _finish_cancel_if_requested(store, claimed.public_id)
    if cancelled is not None:
        return cancelled
    _touch_claimed_worker_job_if_supported(store, claimed.public_id)

    try:
        job = run_claimed_monthly_report_job(
            store,
            claimed.public_id,
            provider=provider,
            template_path=template_path,
            prompt_version=prompt_version,
            model_report=model_report,
            app_version=app_version,
        )
    except Exception as exc:
        cancelled = _finish_cancel_if_requested(store, claimed.public_id)
        if cancelled is not None:
            return cancelled
        failed = store.fail_current_job(
            claimed.public_id,
            error_type="worker_unhandled_error",
            error_message=str(exc),
        )
        failed = _retry_if_available(
            store,
            failed.public_id,
            error_type="worker_unhandled_error",
            error_message=str(exc),
        )
        return WorkerRunResult(
            status=_worker_status_for_job(failed),
            claimed_job_id=claimed.public_id,
            job=failed,
            error_type="worker_unhandled_error",
            error_message=str(exc),
        )

    if job.status == JobStatus.FAILED and job.error_type == "provider_call_failed":
        job = _retry_if_available(
            store,
            job.public_id,
            error_type=job.error_type,
            error_message=job.error_message or "provider call failed",
        )

    return WorkerRunResult(
        status=_worker_status_for_job(job),
        claimed_job_id=claimed.public_id,
        job=job,
        error_type=job.error_type,
        error_message=job.error_message,
    )


def _worker_status_for_job(job: MockJob) -> str:
    if job.status == JobStatus.SUCCEEDED:
        return WorkerRunStatus.SUCCEEDED
    if job.status == JobStatus.CANCELLED:
        return WorkerRunStatus.CANCELLED
    if job.status == JobStatus.QUEUED:
        return WorkerRunStatus.RETRY_SCHEDULED
    return WorkerRunStatus.FAILED


def _retry_if_available(
    store: JobStore,
    public_id: str,
    *,
    error_type: str,
    error_message: str,
) -> MockJob:
    retry = getattr(store, "retry_current_job", None)
    if not callable(retry):
        return store.get(public_id)
    return retry(public_id, error_type=error_type, error_message=error_message)


def _touch_claimed_worker_job_if_supported(
    store: JobStore,
    public_id: str,
) -> None:
    touch = getattr(store, "touch_worker_job", None)
    if callable(touch):
        touch(public_id)


def _finish_cancel_if_requested(
    store: JobStore,
    public_id: str,
) -> WorkerRunResult | None:
    job = store.get(public_id)
    if job.status == JobStatus.CANCELLED:
        return WorkerRunResult(
            status=WorkerRunStatus.CANCELLED,
            claimed_job_id=public_id,
            job=job,
        )
    if job.status != JobStatus.CANCEL_REQUESTED:
        return None
    cancelled = store.complete_current_stage(public_id)
    return WorkerRunResult(
        status=WorkerRunStatus.CANCELLED,
        claimed_job_id=public_id,
        job=cancelled,
    )
