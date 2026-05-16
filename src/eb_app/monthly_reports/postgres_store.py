from __future__ import annotations

from typing import Any, Callable

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from eb_app.monthly_reports.ids import PUBLIC_ID_PREFIXES, new_public_id
from eb_app.monthly_reports.jobs import (
    ACTIVE_JOB_STATUSES,
    DEFAULT_MOCK_OWNER_USER_ID,
    PIPELINE_STAGES,
    JobStatus,
    JobLimitExceeded,
    MockArtifact,
    MockFeedback,
    MockJob,
    MockLLMCall,
    MockSource,
    MockValidation,
    StatusTransitionError,
)


class PostgresJobStore:
    def __init__(
        self,
        database_url: str,
        id_factory: Callable[[str], str] = new_public_id,
    ) -> None:
        self._database_url = database_url
        self._id_factory = id_factory

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        return psycopg.connect(self._database_url, row_factory=dict_row)

    def _row_to_job(self, conn: psycopg.Connection[dict[str, Any]], row: dict[str, Any]) -> MockJob:
        feedback_rows = conn.execute(
            """
            select f.public_id, j.public_id as job_public_id, f.category, f.comment
            from public.monthly_report_feedback f
            join public.monthly_report_jobs j on j.id = f.job_id
            where f.job_id = %s
            order by f.created_at, f.public_id
            """,
            (row["id"],),
        ).fetchall()
        return MockJob(
            public_id=row["public_id"],
            target_month=row["target_month"],
            household_key=row["household_key"],
            owner_user_id=row["created_by"],
            status=row["status"],
            current_stage=row["current_stage"],
            completed_stages=[],
            feedback=[
                MockFeedback(
                    public_id=feedback["public_id"],
                    job_id=feedback["job_public_id"],
                    category=feedback["category"] or "",
                    comment=feedback["comment"] or "",
                )
                for feedback in feedback_rows
            ],
            error_type=row.get("error_type"),
            error_message=row.get("error_message"),
            template_key=row.get("template_key"),
            prompt_version=row.get("prompt_version"),
            template_hash=row.get("template_hash"),
            model_report=row.get("model_report"),
            model_light=row.get("model_light"),
            resolved_model_report=row.get("resolved_model_report"),
            source_bundle_hash=row.get("source_bundle_hash"),
            app_version=row.get("app_version"),
            prompt_scope_notes=row.get("prompt_scope_notes"),
        )

    def create_job(
        self,
        *,
        target_month: str,
        household_key: str,
        owner_user_id: str = DEFAULT_MOCK_OWNER_USER_ID,
        template_key: str | None = None,
        prompt_version: str | None = None,
        template_hash: str | None = None,
        model_report: str | None = None,
        model_light: str | None = None,
        resolved_model_report: str | None = None,
        source_bundle_hash: str | None = None,
        app_version: str | None = None,
        prompt_scope_notes: str | None = None,
    ) -> MockJob:
        with self._connect() as conn:
            row = self._insert_job(
                conn,
                target_month=target_month,
                household_key=household_key,
                owner_user_id=owner_user_id,
                template_key=template_key,
                prompt_version=prompt_version,
                template_hash=template_hash,
                model_report=model_report,
                model_light=model_light,
                resolved_model_report=resolved_model_report,
                source_bundle_hash=source_bundle_hash,
                app_version=app_version,
                prompt_scope_notes=prompt_scope_notes,
            )
            return self._row_to_job(conn, row)

    def create_job_with_active_limit(
        self,
        *,
        target_month: str,
        household_key: str,
        owner_user_id: str = DEFAULT_MOCK_OWNER_USER_ID,
        max_active_jobs: int,
        template_key: str | None = None,
        prompt_version: str | None = None,
        template_hash: str | None = None,
        model_report: str | None = None,
        model_light: str | None = None,
        resolved_model_report: str | None = None,
        source_bundle_hash: str | None = None,
        app_version: str | None = None,
        prompt_scope_notes: str | None = None,
    ) -> MockJob:
        with self._connect() as conn:
            conn.execute("select pg_advisory_xact_lock(hashtext(%s))", (owner_user_id,))
            row = conn.execute(
                """
                select count(*) as count
                from public.monthly_report_jobs
                where created_by = %s
                  and status = any(%s)
                  and deleted_at is null
                """,
                (owner_user_id, list(ACTIVE_JOB_STATUSES)),
            ).fetchone()
            if row and int(row["count"]) >= max_active_jobs:
                raise JobLimitExceeded("user already has 3 active generation jobs")
            inserted = self._insert_job(
                conn,
                target_month=target_month,
                household_key=household_key,
                owner_user_id=owner_user_id,
                template_key=template_key,
                prompt_version=prompt_version,
                template_hash=template_hash,
                model_report=model_report,
                model_light=model_light,
                resolved_model_report=resolved_model_report,
                source_bundle_hash=source_bundle_hash,
                app_version=app_version,
                prompt_scope_notes=prompt_scope_notes,
            )
            return self._row_to_job(conn, inserted)

    def _insert_job(
        self,
        conn: psycopg.Connection[dict[str, Any]],
        *,
        target_month: str,
        household_key: str,
        owner_user_id: str,
        template_key: str | None,
        prompt_version: str | None,
        template_hash: str | None,
        model_report: str | None,
        model_light: str | None,
        resolved_model_report: str | None,
        source_bundle_hash: str | None,
        app_version: str | None,
        prompt_scope_notes: str | None,
    ) -> dict[str, Any]:
        row = conn.execute(
            """
            insert into public.monthly_report_jobs
                (
                    public_id,
                    created_by,
                    target_month,
                    household_key,
                    status,
                    template_key,
                    prompt_version,
                    template_hash,
                    model_report,
                    model_light,
                    resolved_model_report,
                    source_bundle_hash,
                    app_version,
                    prompt_scope_notes
                )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            returning *
            """,
            (
                self._id_factory(PUBLIC_ID_PREFIXES.job),
                owner_user_id,
                target_month,
                household_key,
                JobStatus.QUEUED,
                template_key,
                prompt_version,
                template_hash,
                model_report,
                model_light,
                resolved_model_report,
                source_bundle_hash,
                app_version,
                prompt_scope_notes,
            ),
        ).fetchone()
        assert row is not None
        return row

    def get(self, public_id: str) -> MockJob:
        with self._connect() as conn:
            row = conn.execute(
                "select * from public.monthly_report_jobs where public_id = %s",
                (public_id,),
            ).fetchone()
            if row is None:
                raise KeyError(public_id)
            return self._row_to_job(conn, row)

    def list_jobs(self) -> list[MockJob]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select *
                from public.monthly_report_jobs
                where deleted_at is null
                order by created_at desc, public_id desc
                """
            ).fetchall()
            return [self._row_to_job(conn, row) for row in rows]

    def count_active_jobs(self, owner_user_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                select count(*) as count
                from public.monthly_report_jobs
                where created_by = %s
                  and status = any(%s)
                  and deleted_at is null
                """,
                (owner_user_id, list(ACTIVE_JOB_STATUSES)),
            ).fetchone()
            return int(row["count"]) if row else 0

    def claim_next_queued_job(self, owner_user_id: str | None = None) -> MockJob | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                with candidate as (
                    select id
                    from public.monthly_report_jobs
                    where status = %s
                      and deleted_at is null
                      and (%s::text is null or created_by = %s)
                    order by created_at asc, public_id asc
                    for update skip locked
                    limit 1
                )
                update public.monthly_report_jobs j
                set status = %s,
                    current_stage = %s,
                    updated_at = now()
                from candidate
                where j.id = candidate.id
                returning j.*
                """,
                (
                    JobStatus.QUEUED,
                    owner_user_id,
                    owner_user_id,
                    JobStatus.RUNNING,
                    PIPELINE_STAGES[0],
                ),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_job(conn, row)

    def record_feedback(
        self,
        public_id: str,
        *,
        category: str,
        comment: str,
    ) -> MockFeedback:
        with self._connect() as conn:
            job_row = conn.execute(
                "select id, public_id, created_by from public.monthly_report_jobs where public_id = %s",
                (public_id,),
            ).fetchone()
            if job_row is None:
                raise KeyError(public_id)
            feedback_public_id = f"mrf_{self._id_factory('mrf').split('_', 1)[1]}"
            row = conn.execute(
                """
                insert into public.monthly_report_feedback
                    (public_id, job_id, created_by, category, comment)
                values (%s, %s, %s, %s, %s)
                returning public_id, category, comment
                """,
                (
                    feedback_public_id,
                    job_row["id"],
                    job_row["created_by"],
                    category,
                    comment,
                ),
            ).fetchone()
            assert row is not None
            return MockFeedback(
                public_id=row["public_id"],
                job_id=job_row["public_id"],
                category=row["category"] or "",
                comment=row["comment"] or "",
            )

    def record_source(
        self,
        public_id: str,
        *,
        source_type: str,
        display_name: str | None = None,
        snapshot_text: str | None = None,
        content_hash: str | None = None,
    ) -> MockSource:
        with self._connect() as conn:
            job_row = conn.execute(
                "select id, public_id from public.monthly_report_jobs where public_id = %s",
                (public_id,),
            ).fetchone()
            if job_row is None:
                raise KeyError(public_id)
            row = conn.execute(
                """
                insert into public.monthly_report_sources
                    (public_id, job_id, source_type, display_name, snapshot_text, content_hash)
                values (%s, %s, %s, %s, %s, %s)
                returning public_id, source_type, display_name, snapshot_text, content_hash
                """,
                (
                    self._id_factory(PUBLIC_ID_PREFIXES.source),
                    job_row["id"],
                    source_type,
                    display_name,
                    snapshot_text,
                    content_hash,
                ),
            ).fetchone()
            assert row is not None
            return MockSource(
                public_id=row["public_id"],
                job_id=job_row["public_id"],
                source_type=row["source_type"],
                display_name=row["display_name"],
                snapshot_text=row["snapshot_text"],
                content_hash=row["content_hash"],
            )

    def list_sources(self, public_id: str) -> list[MockSource]:
        with self._connect() as conn:
            job_row = conn.execute(
                "select id, public_id from public.monthly_report_jobs where public_id = %s",
                (public_id,),
            ).fetchone()
            if job_row is None:
                raise KeyError(public_id)
            rows = conn.execute(
                """
                select public_id, source_type, display_name, snapshot_text, content_hash
                from public.monthly_report_sources
                where job_id = %s and deleted_at is null
                order by created_at, public_id
                """,
                (job_row["id"],),
            ).fetchall()
            return [
                MockSource(
                    public_id=row["public_id"],
                    job_id=job_row["public_id"],
                    source_type=row["source_type"],
                    display_name=row["display_name"],
                    snapshot_text=row["snapshot_text"],
                    content_hash=row["content_hash"],
                )
                for row in rows
            ]

    def record_artifact(
        self,
        public_id: str,
        *,
        artifact_type: str,
        content: str | None = None,
        content_hash: str | None = None,
    ) -> MockArtifact:
        with self._connect() as conn:
            job_row = conn.execute(
                "select id, public_id from public.monthly_report_jobs where public_id = %s",
                (public_id,),
            ).fetchone()
            if job_row is None:
                raise KeyError(public_id)
            row = conn.execute(
                """
                insert into public.monthly_report_artifacts
                    (public_id, job_id, artifact_type, content, content_hash)
                values (%s, %s, %s, %s, %s)
                returning public_id, artifact_type, content, content_hash
                """,
                (
                    self._id_factory(PUBLIC_ID_PREFIXES.artifact),
                    job_row["id"],
                    artifact_type,
                    content,
                    content_hash,
                ),
            ).fetchone()
            assert row is not None
            return MockArtifact(
                public_id=row["public_id"],
                job_id=job_row["public_id"],
                artifact_type=row["artifact_type"],
                content=row["content"],
                content_hash=row["content_hash"],
            )

    def list_artifacts(self, public_id: str) -> list[MockArtifact]:
        with self._connect() as conn:
            job_row = conn.execute(
                "select id, public_id from public.monthly_report_jobs where public_id = %s",
                (public_id,),
            ).fetchone()
            if job_row is None:
                raise KeyError(public_id)
            rows = conn.execute(
                """
                select public_id, artifact_type, content, content_hash
                from public.monthly_report_artifacts
                where job_id = %s and deleted_at is null
                order by created_at, public_id
                """,
                (job_row["id"],),
            ).fetchall()
            return [
                MockArtifact(
                    public_id=row["public_id"],
                    job_id=job_row["public_id"],
                    artifact_type=row["artifact_type"],
                    content=row["content"],
                    content_hash=row["content_hash"],
                )
                for row in rows
            ]

    def record_validation(
        self,
        public_id: str,
        *,
        rule_id: str,
        severity: str,
        message: str,
        path: str | None = None,
    ) -> MockValidation:
        with self._connect() as conn:
            job_row = conn.execute(
                "select id, public_id from public.monthly_report_jobs where public_id = %s",
                (public_id,),
            ).fetchone()
            if job_row is None:
                raise KeyError(public_id)
            row = conn.execute(
                """
                insert into public.monthly_report_validations
                    (public_id, job_id, rule_id, severity, message, path)
                values (%s, %s, %s, %s, %s, %s)
                returning public_id, rule_id, severity, message, path
                """,
                (
                    self._id_factory(PUBLIC_ID_PREFIXES.validation),
                    job_row["id"],
                    rule_id,
                    severity,
                    message,
                    path,
                ),
            ).fetchone()
            assert row is not None
            return MockValidation(
                public_id=row["public_id"],
                job_id=job_row["public_id"],
                rule_id=row["rule_id"],
                severity=row["severity"],
                message=row["message"],
                path=row["path"],
            )

    def list_validations(self, public_id: str) -> list[MockValidation]:
        with self._connect() as conn:
            job_row = conn.execute(
                "select id, public_id from public.monthly_report_jobs where public_id = %s",
                (public_id,),
            ).fetchone()
            if job_row is None:
                raise KeyError(public_id)
            rows = conn.execute(
                """
                select public_id, rule_id, severity, message, path
                from public.monthly_report_validations
                where job_id = %s
                order by created_at, public_id
                """,
                (job_row["id"],),
            ).fetchall()
            return [
                MockValidation(
                    public_id=row["public_id"],
                    job_id=job_row["public_id"],
                    rule_id=row["rule_id"],
                    severity=row["severity"],
                    message=row["message"],
                    path=row["path"],
                )
                for row in rows
            ]

    def record_llm_call(
        self,
        public_id: str,
        *,
        prompt_kind: str,
        provider: str,
        requested_model: str | None = None,
        resolved_model: str | None = None,
        prompt_version: str | None = None,
        request_hash: str | None = None,
        response_hash: str | None = None,
        latency_ms: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        finish_reason: str | None = None,
        error_type: str | None = None,
    ) -> MockLLMCall:
        with self._connect() as conn:
            job_row = conn.execute(
                "select id, public_id from public.monthly_report_jobs where public_id = %s",
                (public_id,),
            ).fetchone()
            if job_row is None:
                raise KeyError(public_id)
            row = conn.execute(
                """
                insert into public.llm_call_logs
                    (
                        public_id,
                        job_id,
                        prompt_kind,
                        provider,
                        requested_model,
                        resolved_model,
                        prompt_version,
                        request_hash,
                        response_hash,
                        latency_ms,
                        input_tokens,
                        output_tokens,
                        finish_reason,
                        error_type
                    )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                returning *
                """,
                (
                    self._id_factory(PUBLIC_ID_PREFIXES.llm_call),
                    job_row["id"],
                    prompt_kind,
                    provider,
                    requested_model,
                    resolved_model,
                    prompt_version,
                    request_hash,
                    response_hash,
                    latency_ms,
                    input_tokens,
                    output_tokens,
                    finish_reason,
                    error_type,
                ),
            ).fetchone()
            assert row is not None
            return self._row_to_llm_call(job_row["public_id"], row)

    def list_llm_calls(self, public_id: str) -> list[MockLLMCall]:
        with self._connect() as conn:
            job_row = conn.execute(
                "select id, public_id from public.monthly_report_jobs where public_id = %s",
                (public_id,),
            ).fetchone()
            if job_row is None:
                raise KeyError(public_id)
            rows = conn.execute(
                """
                select *
                from public.llm_call_logs
                where job_id = %s
                order by created_at, public_id
                """,
                (job_row["id"],),
            ).fetchall()
            return [self._row_to_llm_call(job_row["public_id"], row) for row in rows]

    def _row_to_llm_call(self, job_public_id: str, row: dict[str, Any]) -> MockLLMCall:
        return MockLLMCall(
            public_id=row["public_id"],
            job_id=job_public_id,
            prompt_kind=row["prompt_kind"],
            provider=row["provider"],
            requested_model=row["requested_model"],
            resolved_model=row["resolved_model"],
            prompt_version=row["prompt_version"],
            request_hash=row["request_hash"],
            response_hash=row["response_hash"],
            latency_ms=row["latency_ms"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            finish_reason=row["finish_reason"],
            error_type=row["error_type"],
        )

    def rerun_job(self, public_id: str) -> MockJob:
        source = self.get(public_id)
        return self.create_job(
            target_month=source.target_month,
            household_key=source.household_key,
            owner_user_id=source.owner_user_id,
            template_key=source.template_key,
            prompt_version=source.prompt_version,
            template_hash=source.template_hash,
            model_report=source.model_report,
            model_light=source.model_light,
            resolved_model_report=source.resolved_model_report,
            source_bundle_hash=source.source_bundle_hash,
            app_version=source.app_version,
            prompt_scope_notes=source.prompt_scope_notes,
        )

    def start_next(self, public_id: str) -> MockJob:
        job = self.get(public_id)
        if job.status != JobStatus.QUEUED:
            raise StatusTransitionError(f"cannot start job from {job.status}")
        with self._connect() as conn:
            row = conn.execute(
                """
                update public.monthly_report_jobs
                set status = %s, current_stage = %s, updated_at = now()
                where public_id = %s
                returning *
                """,
                (JobStatus.RUNNING, PIPELINE_STAGES[0], public_id),
            ).fetchone()
            assert row is not None
            return self._row_to_job(conn, row)

    def complete_current_stage(self, public_id: str) -> MockJob:
        job = self.get(public_id)
        if job.status not in {JobStatus.RUNNING, JobStatus.CANCEL_REQUESTED}:
            raise StatusTransitionError(f"cannot complete stage from {job.status}")
        if job.current_stage is None:
            raise StatusTransitionError("job has no current stage")

        if job.status == JobStatus.CANCEL_REQUESTED:
            next_status = JobStatus.CANCELLED
            next_stage = None
        else:
            next_index = PIPELINE_STAGES.index(job.current_stage) + 1
            if next_index >= len(PIPELINE_STAGES):
                next_status = JobStatus.SUCCEEDED
                next_stage = None
            else:
                next_status = JobStatus.RUNNING
                next_stage = PIPELINE_STAGES[next_index]

        with self._connect() as conn:
            row = conn.execute(
                """
                update public.monthly_report_jobs
                set status = %s, current_stage = %s, updated_at = now()
                where public_id = %s
                returning *
                """,
                (next_status, next_stage, public_id),
            ).fetchone()
            assert row is not None
            return self._row_to_job(conn, row)

    def fail_current_job(
        self,
        public_id: str,
        *,
        error_type: str,
        error_message: str,
    ) -> MockJob:
        job = self.get(public_id)
        if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}:
            raise StatusTransitionError(f"cannot fail job from {job.status}")

        with self._connect() as conn:
            row = conn.execute(
                """
                update public.monthly_report_jobs
                set status = %s,
                    error_type = %s,
                    error_message = %s,
                    updated_at = now()
                where public_id = %s
                returning *
                """,
                (JobStatus.FAILED, error_type, error_message, public_id),
            ).fetchone()
            assert row is not None
            conn.execute(
                """
                insert into public.audit_logs
                    (public_id, actor_id, action, target_type, target_id, metadata)
                values (%s, %s, %s, %s, %s, %s)
                """,
                (
                    self._id_factory("aud"),
                    row["created_by"],
                    "monthly_report_job_failed",
                    "monthly_report_job",
                    row["public_id"],
                    Jsonb(
                        {
                            "stage": row["current_stage"],
                            "error_type": error_type,
                            "error_message": error_message,
                        }
                    ),
                ),
            )
            return self._row_to_job(conn, row)

    def request_cancel(self, public_id: str) -> MockJob:
        job = self.get(public_id)
        if job.status == JobStatus.QUEUED:
            next_status = JobStatus.CANCELLED
            next_stage = None
        elif job.status == JobStatus.RUNNING:
            next_status = JobStatus.CANCEL_REQUESTED
            next_stage = job.current_stage
        else:
            return job

        with self._connect() as conn:
            row = conn.execute(
                """
                update public.monthly_report_jobs
                set status = %s, current_stage = %s, updated_at = now()
                where public_id = %s
                returning *
                """,
                (next_status, next_stage, public_id),
            ).fetchone()
            assert row is not None
            return self._row_to_job(conn, row)
