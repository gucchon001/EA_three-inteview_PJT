from __future__ import annotations

import argparse
import json
from typing import Any, Sequence

from eb_app.config import get_settings
from eb_app.monthly_reports.retention import (
    PostgresRetentionRepository,
    RetentionExecutor,
    RetentionPlan,
)


def retention_summary(plan: RetentionPlan) -> dict[str, Any]:
    return {
        "ok": True,
        "dry_run": plan.dry_run,
        "generated_at": plan.generated_at.isoformat(),
        "total_eligible_count": plan.total_eligible_count,
        "total_deleted_count": plan.total_deleted_count,
        "targets": [
            {
                "name": item.target.name,
                "cutoff_at": item.cutoff_at.isoformat(),
                "eligible_count": item.eligible_count,
                "deleted_count": item.deleted_count,
                "pii_sensitive": item.target.pii_sensitive,
            }
            for item in plan.items
        ],
    }


def retention_summary_with_post_check(
    plan: RetentionPlan,
    *,
    actor_id: str,
    post_delete_plan: RetentionPlan | None = None,
) -> dict[str, Any]:
    summary = retention_summary(plan)
    summary["actor_id"] = actor_id
    if post_delete_plan is not None:
        summary["post_delete_generated_at"] = post_delete_plan.generated_at.isoformat()
        summary["post_delete_total_eligible_count"] = (
            post_delete_plan.total_eligible_count
        )
        summary["post_delete_targets"] = [
            {
                "name": item.target.name,
                "eligible_count": item.eligible_count,
            }
            for item in post_delete_plan.items
        ]
    return summary


def error_summary(
    *,
    error_type: str,
    message: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = {
        "ok": False,
        "error_type": error_type,
        "message": message,
    }
    if extra:
        summary.update(extra)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run monthly report retention cleanup."
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Physically delete expired rows. Defaults to dry-run.",
    )
    parser.add_argument(
        "--confirm-total-eligible-count",
        type=int,
        default=None,
        help=(
            "Required with --delete. Must match the current dry-run "
            "total_eligible_count before physical deletion runs."
        ),
    )
    parser.add_argument(
        "--post-delete-expected-total-eligible-count",
        type=int,
        default=None,
        help=(
            "Optional with --delete. If provided, the post-delete dry-run "
            "must match this total_eligible_count."
        ),
    )
    parser.add_argument(
        "--actor-id",
        default="monthly-report-retention-job",
        help="Audit actor_id recorded for this retention run.",
    )
    args = parser.parse_args(argv)

    if args.delete and args.confirm_total_eligible_count is None:
        print(
            json.dumps(
                error_summary(
                    error_type="delete_confirmation_required",
                    message=(
                        "--confirm-total-eligible-count is required when "
                        "--delete is used"
                    ),
                ),
                ensure_ascii=False,
            )
        )
        return 1
    if args.post_delete_expected_total_eligible_count is not None and not args.delete:
        print(
            json.dumps(
                error_summary(
                    error_type="post_delete_expectation_requires_delete",
                    message=(
                        "--post-delete-expected-total-eligible-count requires "
                        "--delete"
                    ),
                ),
                ensure_ascii=False,
            )
        )
        return 1

    settings = get_settings()
    if not settings.monthly_report_database_url:
        print(
            json.dumps(
                error_summary(
                    error_type="missing_database_url",
                    message=(
                        "EB_MONTHLY_REPORT_DATABASE_URL is required for retention"
                    ),
                ),
                ensure_ascii=False,
            )
        )
        return 1

    try:
        executor = RetentionExecutor(
            PostgresRetentionRepository(settings.monthly_report_database_url),
            actor_id=args.actor_id,
        )
        if args.delete:
            dry_run_plan = executor.run(dry_run=True)
            if (
                dry_run_plan.total_eligible_count
                != args.confirm_total_eligible_count
            ):
                print(
                    json.dumps(
                        error_summary(
                            error_type="delete_confirmation_mismatch",
                            message=(
                                "confirmed count does not match current "
                                "dry-run count"
                            ),
                            extra={
                                "confirmed_total_eligible_count": (
                                    args.confirm_total_eligible_count
                                ),
                                "actual_total_eligible_count": (
                                    dry_run_plan.total_eligible_count
                                ),
                            },
                        ),
                        ensure_ascii=False,
                    )
                )
                return 1
            plan = executor.run(dry_run=False)
            post_delete_plan = executor.run(dry_run=True)
            if (
                args.post_delete_expected_total_eligible_count is not None
                and post_delete_plan.total_eligible_count
                != args.post_delete_expected_total_eligible_count
            ):
                print(
                    json.dumps(
                        error_summary(
                            error_type="post_delete_verification_mismatch",
                            message=(
                                "post-delete count does not match expected "
                                "count"
                            ),
                            extra={
                                "expected_post_delete_total_eligible_count": (
                                    args.post_delete_expected_total_eligible_count
                                ),
                                "actual_post_delete_total_eligible_count": (
                                    post_delete_plan.total_eligible_count
                                ),
                            },
                        ),
                        ensure_ascii=False,
                    )
                )
                return 1
        else:
            plan = executor.run(dry_run=True)
            post_delete_plan = None
    except Exception:
        print(
            json.dumps(
                error_summary(
                    error_type="retention_failed",
                    message="retention execution failed",
                ),
                ensure_ascii=False,
            )
        )
        return 1

    print(
        json.dumps(
            retention_summary_with_post_check(
                plan,
                actor_id=args.actor_id,
                post_delete_plan=post_delete_plan,
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
