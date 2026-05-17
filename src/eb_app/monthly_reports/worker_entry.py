from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
from typing import Sequence

from eb_app.config import Settings, get_settings
from eb_app.monthly_reports.postgres_store import PostgresJobStore
from eb_app.monthly_reports.worker import (
    WorkerRunResult,
    WorkerRunStatus,
    run_next_queued_monthly_report_job_result,
)
from eb_app.monthly_reports.workflow import OpenRouterMonthlyReportProvider


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MONTHLY_REPORT_TEMPLATE = (
    _PROJECT_ROOT
    / "docs"
    / "samples"
    / "monthly-reports"
    / "monthly_pattern_b_content.template.md"
)


def run_worker_once(
    *,
    settings: Settings | None = None,
    owner_user_id: str | None = None,
    lease_timeout_seconds: int | None = None,
    template_path: Path = DEFAULT_MONTHLY_REPORT_TEMPLATE,
) -> WorkerRunResult:
    settings = settings or get_settings()
    if not settings.monthly_report_database_url:
        raise RuntimeError("EB_MONTHLY_REPORT_DATABASE_URL is required for worker")
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required for worker")
    return run_next_queued_monthly_report_job_result(
        PostgresJobStore(settings.monthly_report_database_url),
        provider=OpenRouterMonthlyReportProvider(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model_report,
            timeout=settings.openrouter_timeout_seconds,
            max_tokens=settings.openrouter_max_tokens,
        ),
        template_path=template_path,
        owner_user_id=owner_user_id,
        lease_timeout_seconds=lease_timeout_seconds,
        prompt_version=settings.monthly_report_prompt_version,
        model_report=settings.openrouter_model_report,
        app_version=settings.app_version,
    )


def run_worker_batch(
    *,
    max_jobs: int,
    sleep_seconds: float,
    owner_user_id: str | None = None,
    lease_timeout_seconds: int | None = None,
    settings: Settings | None = None,
) -> list[WorkerRunResult]:
    results: list[WorkerRunResult] = []
    while max_jobs <= 0 or len(results) < max_jobs:
        result = run_worker_once(
            settings=settings,
            owner_user_id=owner_user_id,
            lease_timeout_seconds=lease_timeout_seconds,
        )
        results.append(result)
        if result.status == WorkerRunStatus.NO_JOB:
            break
        if max_jobs <= 0 and sleep_seconds > 0:
            time.sleep(sleep_seconds)
    return results


def worker_result_summary(result: WorkerRunResult) -> dict[str, str | None]:
    return {
        "status": result.status,
        "claimed_job_id": result.claimed_job_id,
        "job_id": result.job.public_id if result.job else None,
        "job_status": result.job.status if result.job else None,
        "error_type": result.error_type,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run monthly report worker jobs.")
    parser.add_argument("--owner-user-id", default=os.environ.get("EB_WORKER_OWNER_USER_ID"))
    parser.add_argument(
        "--lease-timeout-seconds",
        type=int,
        default=_optional_int(os.environ.get("EB_WORKER_LEASE_TIMEOUT_SECONDS")),
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=int(os.environ.get("EB_WORKER_MAX_JOBS", "1")),
        help="Number of jobs to process. Use 0 for a loop until no job is found.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=float(os.environ.get("EB_WORKER_SLEEP_SECONDS", "0")),
    )
    args = parser.parse_args(argv)

    results = run_worker_batch(
        max_jobs=args.max_jobs,
        sleep_seconds=args.sleep_seconds,
        owner_user_id=args.owner_user_id,
        lease_timeout_seconds=args.lease_timeout_seconds,
    )
    print(json.dumps([worker_result_summary(result) for result in results], ensure_ascii=False))
    if any(result.status == WorkerRunStatus.FAILED for result in results):
        return 1
    return 0


def _optional_int(raw: str | None) -> int | None:
    if raw is None or raw.strip() == "":
        return None
    return int(raw.strip())


if __name__ == "__main__":
    raise SystemExit(main())
