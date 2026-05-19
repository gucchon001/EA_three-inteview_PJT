from __future__ import annotations

from typing import Any

from eb_app.monthly_reports.ids import new_public_id
from eb_app.monthly_reports.jobs import (
    MockArtifact,
    MockFeedback,
    MockJob,
    MockLLMCall,
    MockSource,
    MockValidation,
)


class SupabaseMonthlyReportReadStore:
    """Read monthly report rows through a user-JWT Supabase client so RLS applies."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def list_jobs(self) -> list[MockJob]:
        rows = self._execute(
            self._client.table("monthly_report_jobs")
            .select("*")
            .is_("deleted_at", "null")
            .order("created_at", desc=True)
            .order("public_id", desc=True)
        )
        return [self._row_to_job(row) for row in rows]

    def get(self, public_id: str) -> MockJob:
        row = self._get_job_row(public_id)
        return self._row_to_job(row)

    def list_sources(self, public_id: str) -> list[MockSource]:
        job_row = self._get_job_row(public_id)
        rows = self._execute(
            self._client.table("monthly_report_sources")
            .select("public_id,source_type,display_name,snapshot_text,content_hash,created_at")
            .eq("job_id", job_row["id"])
            .is_("deleted_at", "null")
            .order("created_at")
            .order("public_id")
        )
        return [
            MockSource(
                public_id=row["public_id"],
                job_id=job_row["public_id"],
                source_type=row["source_type"],
                display_name=row.get("display_name"),
                snapshot_text=row.get("snapshot_text"),
                content_hash=row.get("content_hash"),
                created_at=row.get("created_at"),
            )
            for row in rows
        ]

    def record_source(
        self,
        public_id: str,
        *,
        source_type: str,
        display_name: str | None = None,
        snapshot_text: str | None = None,
        content_hash: str | None = None,
    ) -> MockSource:
        job_row = self._get_job_row(public_id)
        source_public_id = new_public_id("mrs")
        rows = self._execute(
            self._client.table("monthly_report_sources")
            .insert(
                {
                    "public_id": source_public_id,
                    "job_id": job_row["id"],
                    "source_type": source_type,
                    "display_name": display_name,
                    "snapshot_text": snapshot_text,
                    "content_hash": content_hash,
                }
            )
            .select(
                "public_id,source_type,display_name,snapshot_text,content_hash,created_at"
            )
        )
        if not rows:
            raise KeyError(public_id)
        row = rows[0]
        return MockSource(
            public_id=row["public_id"],
            job_id=job_row["public_id"],
            source_type=row.get("source_type") or "",
            display_name=row.get("display_name"),
            snapshot_text=row.get("snapshot_text"),
            content_hash=row.get("content_hash"),
            created_at=row.get("created_at"),
        )

    def list_artifacts(self, public_id: str) -> list[MockArtifact]:
        job_row = self._get_job_row(public_id)
        rows = self._execute(
            self._client.table("monthly_report_artifacts")
            .select("public_id,artifact_type,content,content_hash,created_at")
            .eq("job_id", job_row["id"])
            .is_("deleted_at", "null")
            .order("created_at")
            .order("public_id")
        )
        return [
            MockArtifact(
                public_id=row["public_id"],
                job_id=job_row["public_id"],
                artifact_type=row["artifact_type"],
                content=row.get("content"),
                content_hash=row.get("content_hash"),
                created_at=row.get("created_at"),
            )
            for row in rows
        ]

    def list_validations(self, public_id: str) -> list[MockValidation]:
        job_row = self._get_job_row(public_id)
        rows = self._execute(
            self._client.table("monthly_report_validations")
            .select("public_id,rule_id,severity,message,path,created_at")
            .eq("job_id", job_row["id"])
            .order("created_at")
            .order("public_id")
        )
        return [
            MockValidation(
                public_id=row["public_id"],
                job_id=job_row["public_id"],
                rule_id=row["rule_id"],
                severity=row["severity"],
                message=row["message"],
                path=row.get("path"),
                created_at=row.get("created_at"),
            )
            for row in rows
        ]

    def list_llm_calls(self, public_id: str) -> list[MockLLMCall]:
        job_row = self._get_job_row(public_id)
        rows = self._execute(
            self._client.table("llm_call_logs")
            .select("*")
            .eq("job_id", job_row["id"])
            .order("created_at")
            .order("public_id")
        )
        return [
            MockLLMCall(
                public_id=row["public_id"],
                job_id=job_row["public_id"],
                prompt_kind=row["prompt_kind"],
                provider=row["provider"],
                requested_model=row.get("requested_model"),
                resolved_model=row.get("resolved_model"),
                prompt_version=row.get("prompt_version"),
                request_hash=row.get("request_hash"),
                response_hash=row.get("response_hash"),
                latency_ms=row.get("latency_ms"),
                input_tokens=row.get("input_tokens"),
                output_tokens=row.get("output_tokens"),
                finish_reason=row.get("finish_reason"),
                error_type=row.get("error_type"),
                created_at=row.get("created_at"),
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
        job_row = self._get_job_row(public_id)
        validation_public_id = new_public_id("mrv")
        rows = self._execute(
            self._client.table("monthly_report_validations")
            .insert(
                {
                    "public_id": validation_public_id,
                    "job_id": job_row["id"],
                    "rule_id": rule_id,
                    "severity": severity,
                    "message": message,
                    "path": path,
                }
            )
            .select("public_id,rule_id,severity,message,path,created_at")
        )
        if not rows:
            raise KeyError(public_id)
        row = rows[0]
        return MockValidation(
            public_id=row["public_id"],
            job_id=job_row["public_id"],
            rule_id=row.get("rule_id") or "",
            severity=row.get("severity") or "",
            message=row.get("message") or "",
            path=row.get("path"),
            created_at=row.get("created_at"),
        )

    def record_feedback(
        self,
        public_id: str,
        *,
        category: str,
        comment: str,
    ) -> MockFeedback:
        job_row = self._get_job_row(public_id)
        feedback_public_id = new_public_id("mrf")
        rows = self._execute(
            self._client.table("monthly_report_feedback")
            .insert(
                {
                    "public_id": feedback_public_id,
                    "job_id": job_row["id"],
                    "created_by": job_row["created_by"],
                    "category": category,
                    "comment": comment,
                }
            )
            .select("public_id,category,comment")
        )
        if not rows:
            raise KeyError(public_id)
        row = rows[0]
        return MockFeedback(
            public_id=row["public_id"],
            job_id=job_row["public_id"],
            category=row.get("category") or "",
            comment=row.get("comment") or "",
        )

    def record_artifact(
        self,
        public_id: str,
        *,
        artifact_type: str,
        content: str | None = None,
        content_hash: str | None = None,
    ) -> MockArtifact:
        job_row = self._get_job_row(public_id)
        artifact_public_id = new_public_id("mra")
        rows = self._execute(
            self._client.table("monthly_report_artifacts")
            .insert(
                {
                    "public_id": artifact_public_id,
                    "job_id": job_row["id"],
                    "artifact_type": artifact_type,
                    "content": content,
                    "content_hash": content_hash,
                }
            )
            .select("public_id,artifact_type,content,content_hash,created_at")
        )
        if not rows:
            raise KeyError(public_id)
        row = rows[0]
        return MockArtifact(
            public_id=row["public_id"],
            job_id=job_row["public_id"],
            artifact_type=row.get("artifact_type") or "",
            content=row.get("content"),
            content_hash=row.get("content_hash"),
            created_at=row.get("created_at"),
        )

    def _get_job_row(self, public_id: str) -> dict[str, Any]:
        rows = self._execute(
            self._client.table("monthly_report_jobs")
            .select("*")
            .eq("public_id", public_id)
            .is_("deleted_at", "null")
            .limit(1)
        )
        if not rows:
            raise KeyError(public_id)
        return rows[0]

    def _row_to_job(self, row: dict[str, Any]) -> MockJob:
        return MockJob(
            public_id=row["public_id"],
            target_month=row["target_month"],
            household_key=row["household_key"],
            owner_user_id=row["created_by"],
            status=row["status"],
            current_stage=row.get("current_stage"),
            completed_stages=[],
            feedback=self._feedback_for_job(row),
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
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at") or row.get("created_at"),
        )

    def _feedback_for_job(self, row: dict[str, Any]) -> list[MockFeedback]:
        rows = self._execute(
            self._client.table("monthly_report_feedback")
            .select("public_id,category,comment")
            .eq("job_id", row["id"])
            .order("created_at")
            .order("public_id")
        )
        return [
            MockFeedback(
                public_id=feedback["public_id"],
                job_id=row["public_id"],
                category=feedback.get("category") or "",
                comment=feedback.get("comment") or "",
            )
            for feedback in rows
        ]

    def _execute(self, query: Any) -> list[dict[str, Any]]:
        data = query.execute().data
        return list(data or [])
