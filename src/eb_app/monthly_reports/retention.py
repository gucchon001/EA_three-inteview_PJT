from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from eb_app.monthly_reports.ids import new_public_id


@dataclass(frozen=True)
class RetentionTarget:
    name: str
    table: str
    timestamp_sql: str
    retention_days: int
    has_retention_until: bool = False
    pii_sensitive: bool = False


@dataclass(frozen=True)
class RetentionPlanItem:
    target: RetentionTarget
    cutoff_at: datetime
    eligible_count: int = 0
    deleted_count: int = 0


@dataclass(frozen=True)
class RetentionPlan:
    generated_at: datetime
    dry_run: bool
    items: tuple[RetentionPlanItem, ...]

    @property
    def total_eligible_count(self) -> int:
        return sum(item.eligible_count for item in self.items)

    @property
    def total_deleted_count(self) -> int:
        return sum(item.deleted_count for item in self.items)

    def audit_metadata(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "generated_at": self.generated_at.isoformat(),
            "targets": [
                {
                    "name": item.target.name,
                    "cutoff_at": item.cutoff_at.isoformat(),
                    "eligible_count": item.eligible_count,
                    "deleted_count": item.deleted_count,
                    "pii_sensitive": item.target.pii_sensitive,
                }
                for item in self.items
            ],
            "total_eligible_count": self.total_eligible_count,
            "total_deleted_count": self.total_deleted_count,
        }


class RetentionRepository(Protocol):
    def count_expired(self, target: RetentionTarget, *, now: datetime) -> int:
        ...

    def delete_expired(self, target: RetentionTarget, *, now: datetime) -> int:
        ...

    def record_audit_log(
        self,
        *,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str | None,
        metadata: dict[str, Any],
    ) -> None:
        ...


RETENTION_TARGETS: tuple[RetentionTarget, ...] = (
    RetentionTarget(
        name="sources",
        table="monthly_report_sources",
        timestamp_sql="coalesce(fetched_at, created_at)",
        retention_days=365,
        has_retention_until=True,
        pii_sensitive=True,
    ),
    RetentionTarget(
        name="artifacts",
        table="monthly_report_artifacts",
        timestamp_sql="created_at",
        retention_days=365 * 3,
        has_retention_until=True,
        pii_sensitive=True,
    ),
    RetentionTarget(
        name="validations",
        table="monthly_report_validations",
        timestamp_sql="created_at",
        retention_days=365 * 3,
    ),
    RetentionTarget(
        name="feedback",
        table="monthly_report_feedback",
        timestamp_sql="created_at",
        retention_days=365 * 3,
        pii_sensitive=True,
    ),
    RetentionTarget(
        name="llm_call_logs",
        table="llm_call_logs",
        timestamp_sql="created_at",
        retention_days=365 * 3,
    ),
    RetentionTarget(
        name="jobs",
        table="monthly_report_jobs",
        timestamp_sql="created_at",
        retention_days=365 * 3,
        has_retention_until=True,
    ),
)


def build_retention_plan(
    repository: RetentionRepository,
    *,
    now: datetime | None = None,
    dry_run: bool = True,
    targets: tuple[RetentionTarget, ...] = RETENTION_TARGETS,
) -> RetentionPlan:
    current_time = _as_aware_utc(now)
    items = tuple(
        RetentionPlanItem(
            target=target,
            cutoff_at=current_time - timedelta(days=target.retention_days),
            eligible_count=repository.count_expired(target, now=current_time),
        )
        for target in targets
    )
    return RetentionPlan(generated_at=current_time, dry_run=dry_run, items=items)


class RetentionExecutor:
    def __init__(
        self,
        repository: RetentionRepository,
        *,
        actor_id: str = "monthly-report-retention-job",
    ) -> None:
        self._repository = repository
        self._actor_id = actor_id

    def run(
        self,
        *,
        now: datetime | None = None,
        dry_run: bool = True,
        audit: bool = True,
    ) -> RetentionPlan:
        current_time = _as_aware_utc(now)
        planned = build_retention_plan(
            self._repository,
            now=current_time,
            dry_run=dry_run,
        )
        if dry_run:
            result = planned
        else:
            result = RetentionPlan(
                generated_at=planned.generated_at,
                dry_run=False,
                items=tuple(
                    RetentionPlanItem(
                        target=item.target,
                        cutoff_at=item.cutoff_at,
                        eligible_count=item.eligible_count,
                        deleted_count=self._repository.delete_expired(
                            item.target,
                            now=current_time,
                        ),
                    )
                    for item in planned.items
                ),
            )

        if audit:
            self._repository.record_audit_log(
                actor_id=self._actor_id,
                action=(
                    "monthly_report_retention_dry_run"
                    if dry_run
                    else "monthly_report_retention_delete"
                ),
                target_type="monthly_report_retention",
                target_id=None,
                metadata=result.audit_metadata(),
            )
        return result


class PostgresRetentionRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        return psycopg.connect(self._database_url, row_factory=dict_row)

    def count_expired(self, target: RetentionTarget, *, now: datetime) -> int:
        _ensure_known_target(target)
        with self._connect() as conn:
            row = conn.execute(
                f"""
                select count(*) as count
                from public.{target.table}
                where {_expired_where_sql(target)}
                """,
                _expired_params(target, now),
            ).fetchone()
            return int(row["count"]) if row else 0

    def delete_expired(self, target: RetentionTarget, *, now: datetime) -> int:
        _ensure_known_target(target)
        with self._connect() as conn:
            cursor = conn.execute(
                f"""
                delete from public.{target.table}
                where {_expired_where_sql(target)}
                """,
                _expired_params(target, now),
            )
            return cursor.rowcount if cursor.rowcount is not None else 0

    def record_audit_log(
        self,
        *,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str | None,
        metadata: dict[str, Any],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into public.audit_logs
                    (public_id, actor_id, action, target_type, target_id, metadata)
                values (%s, %s, %s, %s, %s, %s)
                """,
                (
                    new_public_id("aud"),
                    actor_id,
                    action,
                    target_type,
                    target_id,
                    Jsonb(metadata),
                ),
            )


def _as_aware_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _expired_where_sql(target: RetentionTarget) -> str:
    if target.has_retention_until:
        return (
            "(retention_until is not null and retention_until <= %s) "
            f"or (retention_until is null and {target.timestamp_sql} <= %s)"
        )
    return f"{target.timestamp_sql} <= %s"


def _expired_params(target: RetentionTarget, now: datetime) -> tuple[datetime, ...]:
    cutoff = now - timedelta(days=target.retention_days)
    if target.has_retention_until:
        return (now, cutoff)
    return (cutoff,)


def _ensure_known_target(target: RetentionTarget) -> None:
    if target not in RETENTION_TARGETS:
        raise ValueError(f"unknown retention target: {target.name}")
