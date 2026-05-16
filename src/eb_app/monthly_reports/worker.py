from __future__ import annotations

from pathlib import Path

from eb_app.monthly_reports.jobs import MockJob
from eb_app.monthly_reports.workflow import (
    JobStore,
    MonthlyReportProvider,
    run_claimed_monthly_report_job,
)


def run_next_queued_monthly_report_job(
    store: JobStore,
    *,
    provider: MonthlyReportProvider,
    template_path: Path,
) -> MockJob | None:
    claimed = store.claim_next_queued_job()
    if claimed is None:
        return None
    return run_claimed_monthly_report_job(
        store,
        claimed.public_id,
        provider=provider,
        template_path=template_path,
    )
