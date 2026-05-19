from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Thread
from typing import Callable

from eb_app.monthly_reports.jobs import JobStatus, MockJob, WORKER_STALE_RECLAIM_STAGES
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
    MANUAL_RECOVERY_REQUIRED = "manual_recovery_required"


@dataclass(frozen=True)
class WorkerRunResult:
    status: str
    claimed_job_id: str | None = None
    job: MockJob | None = None
    error_type: str | None = None
    error_message: str | None = None
    manual_recovery_job_count: int = 0
    manual_recovery_stages: tuple[str, ...] = ()


def run_next_queued_monthly_report_job(
    store: JobStore,
    *,
    provider: MonthlyReportProvider,
    template_path: Path,
    public_id: str | None = None,
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
        public_id=public_id,
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
    public_id: str | None = None,
    owner_user_id: str | None = None,
    lease_timeout_seconds: int | None = None,
    prompt_version: str | None = None,
    model_report: str | None = None,
    app_version: str | None = None,
) -> WorkerRunResult:
    claim_specific = getattr(store, "claim_job_for_worker", None)
    if public_id is not None and callable(claim_specific):
        claimed = claim_specific(
            public_id,
            lease_timeout_seconds=lease_timeout_seconds,
        )
    elif public_id is not None:
        claimed = None
    else:
        claim_runnable = getattr(store, "claim_next_runnable_job", None)
        if callable(claim_runnable):
            claimed = claim_runnable(
                owner_user_id=owner_user_id,
                lease_timeout_seconds=lease_timeout_seconds,
            )
        else:
            claimed = store.claim_next_queued_job(owner_user_id=owner_user_id)
    if claimed is None:
        if public_id is not None:
            return WorkerRunResult(status=WorkerRunStatus.NO_JOB)
        manual_recovery_jobs = _find_stale_later_stage_jobs_if_supported(
            store,
            owner_user_id=owner_user_id,
            lease_timeout_seconds=lease_timeout_seconds,
        )
        if manual_recovery_jobs:
            return WorkerRunResult(
                status=WorkerRunStatus.MANUAL_RECOVERY_REQUIRED,
                job=manual_recovery_jobs[0],
                error_type="manual_recovery_required",
                manual_recovery_job_count=len(manual_recovery_jobs),
                manual_recovery_stages=tuple(
                    sorted(
                        {
                            job.current_stage
                            for job in manual_recovery_jobs
                            if job.current_stage is not None
                        }
                    )
                ),
            )
        return WorkerRunResult(status=WorkerRunStatus.NO_JOB)

    claimed = store.get(claimed.public_id)
    cancelled = _finish_cancel_if_requested(store, claimed.public_id)
    if cancelled is not None:
        return cancelled
    _touch_claimed_worker_job_if_supported(store, claimed.public_id)

    try:
        job = _run_with_worker_heartbeat_if_supported(
            store,
            claimed.public_id,
            lease_timeout_seconds=lease_timeout_seconds,
            run=lambda: run_claimed_monthly_report_job(
                store,
                claimed.public_id,
                provider=provider,
                template_path=template_path,
                prompt_version=prompt_version,
                model_report=model_report,
                app_version=app_version,
            ),
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


def _run_with_worker_heartbeat_if_supported(
    store: JobStore,
    public_id: str,
    *,
    lease_timeout_seconds: int | None,
    run: Callable[[], MockJob],
) -> MockJob:
    touch = getattr(store, "touch_worker_job", None)
    if not callable(touch) or lease_timeout_seconds is None or lease_timeout_seconds <= 0:
        return run()

    stop = Event()
    interval_seconds = max(0.1, min(30.0, lease_timeout_seconds / 3))

    def heartbeat() -> None:
        while not stop.wait(interval_seconds):
            try:
                touch(public_id)
            except Exception:
                return

    thread = Thread(target=heartbeat, name=f"monthly-report-worker-heartbeat-{public_id}")
    thread.daemon = True
    thread.start()
    try:
        return run()
    finally:
        stop.set()
        thread.join(timeout=interval_seconds + 0.1)


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


def _find_stale_later_stage_jobs_if_supported(
    store: JobStore,
    *,
    owner_user_id: str | None,
    lease_timeout_seconds: int | None,
) -> list[MockJob]:
    if lease_timeout_seconds is None or lease_timeout_seconds <= 0:
        return []
    list_jobs = getattr(store, "list_jobs", None)
    if not callable(list_jobs):
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=lease_timeout_seconds)
    stale_jobs: list[MockJob] = []
    for job in list_jobs():
        if owner_user_id is not None and job.owner_user_id != owner_user_id:
            continue
        if job.status != JobStatus.RUNNING:
            continue
        if job.current_stage is None or job.current_stage in WORKER_STALE_RECLAIM_STAGES:
            continue
        claimed_at = job.worker_last_claimed_at
        if claimed_at is None:
            stale_jobs.append(job)
            continue
        if claimed_at.tzinfo is None:
            claimed_at = claimed_at.replace(tzinfo=timezone.utc)
        if claimed_at <= cutoff:
            stale_jobs.append(job)
    return stale_jobs
