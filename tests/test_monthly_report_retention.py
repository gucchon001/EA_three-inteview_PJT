from __future__ import annotations

from datetime import datetime, timedelta, timezone

from eb_app.monthly_reports.retention import (
    RETENTION_TARGETS,
    RetentionExecutor,
    RetentionTarget,
    build_retention_plan,
)


class FakeRetentionRepository:
    def __init__(self, counts: dict[str, int] | None = None) -> None:
        self.counts = counts or {}
        self.count_calls: list[tuple[str, datetime]] = []
        self.delete_calls: list[tuple[str, datetime]] = []
        self.audit_logs: list[dict] = []

    def count_expired(self, target: RetentionTarget, *, now: datetime) -> int:
        self.count_calls.append((target.name, now))
        return self.counts.get(target.name, 0)

    def delete_expired(self, target: RetentionTarget, *, now: datetime) -> int:
        self.delete_calls.append((target.name, now))
        return self.counts.get(target.name, 0)

    def record_audit_log(
        self,
        *,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str | None,
        metadata: dict,
    ) -> None:
        self.audit_logs.append(
            {
                "actor_id": actor_id,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "metadata": metadata,
            }
        )


def test_build_retention_plan_counts_all_monthly_report_targets_without_deleting():
    now = datetime(2026, 5, 17, tzinfo=timezone.utc)
    repository = FakeRetentionRepository(
        {
            "sources": 4,
            "artifacts": 3,
            "validations": 2,
            "feedback": 1,
            "llm_call_logs": 5,
            "jobs": 1,
        }
    )

    plan = build_retention_plan(repository, now=now, dry_run=True)

    assert plan.dry_run is True
    assert [item.target.name for item in plan.items] == [
        "sources",
        "artifacts",
        "validations",
        "feedback",
        "llm_call_logs",
        "jobs",
    ]
    assert plan.total_eligible_count == 16
    assert plan.total_deleted_count == 0
    assert repository.delete_calls == []
    assert [item.cutoff_at for item in plan.items] == [
        now - timedelta(days=target.retention_days)
        for target in RETENTION_TARGETS
    ]


def test_retention_executor_dry_run_records_audit_without_deleting():
    now = datetime(2026, 5, 17, 9, 0, tzinfo=timezone.utc)
    repository = FakeRetentionRepository({"sources": 2})
    executor = RetentionExecutor(repository, actor_id="pytest-retention")

    result = executor.run(now=now, dry_run=True)

    assert result.total_eligible_count == 2
    assert result.total_deleted_count == 0
    assert repository.delete_calls == []
    assert repository.audit_logs == [
        {
            "actor_id": "pytest-retention",
            "action": "monthly_report_retention_dry_run",
            "target_type": "monthly_report_retention",
            "target_id": None,
            "metadata": result.audit_metadata(),
        }
    ]


def test_retention_executor_delete_runs_targets_in_safe_order_and_audits_counts():
    now = datetime(2026, 5, 17, 9, 0, tzinfo=timezone.utc)
    repository = FakeRetentionRepository(
        {
            "sources": 4,
            "artifacts": 3,
            "validations": 2,
            "feedback": 1,
            "llm_call_logs": 5,
            "jobs": 1,
        }
    )

    result = RetentionExecutor(repository).run(now=now, dry_run=False)

    assert result.total_eligible_count == 16
    assert result.total_deleted_count == 16
    assert [name for name, _ in repository.delete_calls] == [
        "sources",
        "artifacts",
        "validations",
        "feedback",
        "llm_call_logs",
        "jobs",
    ]
    assert repository.audit_logs[0]["action"] == "monthly_report_retention_delete"
    assert repository.audit_logs[0]["metadata"]["total_deleted_count"] == 16


def test_retention_audit_metadata_uses_counts_and_hash_safe_target_names_only():
    now = datetime(2026, 5, 17, tzinfo=timezone.utc)
    repository = FakeRetentionRepository({"sources": 1, "feedback": 1})

    metadata = build_retention_plan(repository, now=now).audit_metadata()

    assert metadata["total_eligible_count"] == 2
    assert "household_key" not in str(metadata)
    assert "snapshot_text" not in str(metadata)
    assert "draft_markdown" not in str(metadata)
    assert {
        item["name"]
        for item in metadata["targets"]
        if item["pii_sensitive"]
    } == {"sources", "artifacts", "feedback"}
