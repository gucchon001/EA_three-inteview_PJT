from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from eb_app.monthly_reports.ids import PUBLIC_ID_PREFIXES, new_public_id


class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


ACTIVE_JOB_STATUSES = {
    JobStatus.QUEUED,
    JobStatus.RUNNING,
    JobStatus.CANCEL_REQUESTED,
}

DEFAULT_MOCK_OWNER_USER_ID = "mock-user"
MAX_ACTIVE_JOBS_PER_USER = 3

PIPELINE_STAGES = (
    "fetch_sources",
    "bundle",
    "build_messages",
    "call_llm",
    "validate",
    "persist",
)
WORKER_STALE_RECLAIM_STAGES = (PIPELINE_STAGES[0],)


class StatusTransitionError(RuntimeError):
    pass


class JobLimitExceeded(RuntimeError):
    pass


@dataclass
class MockJob:
    public_id: str
    target_month: str
    household_key: str
    owner_user_id: str = DEFAULT_MOCK_OWNER_USER_ID
    status: str = JobStatus.QUEUED
    current_stage: str | None = None
    completed_stages: list[str] = field(default_factory=list)
    feedback: list[MockFeedback] = field(default_factory=list)
    error_type: str | None = None
    error_message: str | None = None
    template_key: str | None = None
    prompt_version: str | None = None
    template_hash: str | None = None
    model_report: str | None = None
    model_light: str | None = None
    resolved_model_report: str | None = None
    source_bundle_hash: str | None = None
    app_version: str | None = None
    prompt_scope_notes: str | None = None
    worker_attempts: int = 0
    max_worker_attempts: int = 3
    worker_last_claimed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MockFeedback:
    public_id: str
    job_id: str
    category: str
    comment: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MockSource:
    public_id: str
    job_id: str
    source_type: str
    display_name: str | None = None
    snapshot_text: str | None = None
    content_hash: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MockArtifact:
    public_id: str
    job_id: str
    artifact_type: str
    content: str | None = None
    content_hash: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MockValidation:
    public_id: str
    job_id: str
    rule_id: str
    severity: str
    message: str
    path: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MockLLMCall:
    public_id: str
    job_id: str
    prompt_kind: str
    provider: str
    requested_model: str | None = None
    resolved_model: str | None = None
    prompt_version: str | None = None
    request_hash: str | None = None
    response_hash: str | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None
    error_type: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MockAuditLog:
    public_id: str
    actor_id: str
    action: str
    target_type: str
    target_id: str
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MockJobStore:
    def __init__(self, id_factory: Callable[[str], str] = new_public_id) -> None:
        self._id_factory = id_factory
        self._jobs: dict[str, MockJob] = {}
        self._sources: dict[str, list[MockSource]] = {}
        self._artifacts: dict[str, list[MockArtifact]] = {}
        self._validations: dict[str, list[MockValidation]] = {}
        self._llm_calls: dict[str, list[MockLLMCall]] = {}
        self._audit_logs: dict[str, list[MockAuditLog]] = {}
        self._feedback_sequence = 0

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
        max_worker_attempts: int = 3,
    ) -> MockJob:
        public_id = self._id_factory(PUBLIC_ID_PREFIXES.job)
        job = MockJob(
            public_id=public_id,
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
            max_worker_attempts=max_worker_attempts,
        )
        self._jobs[public_id] = job
        return job

    def create_job_with_active_limit(
        self,
        *,
        target_month: str,
        household_key: str,
        owner_user_id: str = DEFAULT_MOCK_OWNER_USER_ID,
        max_active_jobs: int = MAX_ACTIVE_JOBS_PER_USER,
        template_key: str | None = None,
        prompt_version: str | None = None,
        template_hash: str | None = None,
        model_report: str | None = None,
        model_light: str | None = None,
        resolved_model_report: str | None = None,
        source_bundle_hash: str | None = None,
        app_version: str | None = None,
        prompt_scope_notes: str | None = None,
        max_worker_attempts: int = 3,
    ) -> MockJob:
        if self.count_active_jobs(owner_user_id) >= max_active_jobs:
            raise JobLimitExceeded("user already has 3 active generation jobs")
        return self.create_job(
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
            max_worker_attempts=max_worker_attempts,
        )

    def get(self, public_id: str) -> MockJob:
        return self._jobs[public_id]

    def update_reproducibility_meta(
        self,
        public_id: str,
        *,
        prompt_version: str | None = None,
        template_hash: str | None = None,
        model_report: str | None = None,
        resolved_model_report: str | None = None,
        source_bundle_hash: str | None = None,
        app_version: str | None = None,
    ) -> MockJob:
        job = self.get(public_id)
        if prompt_version is not None:
            job.prompt_version = prompt_version
        if template_hash is not None:
            job.template_hash = template_hash
        if model_report is not None:
            job.model_report = model_report
        if resolved_model_report is not None:
            job.resolved_model_report = resolved_model_report
        if source_bundle_hash is not None:
            job.source_bundle_hash = source_bundle_hash
        if app_version is not None:
            job.app_version = app_version
        return job

    def list_jobs(self) -> list[MockJob]:
        return list(self._jobs.values())

    def count_active_jobs(self, owner_user_id: str) -> int:
        return sum(
            1
            for job in self._jobs.values()
            if job.owner_user_id == owner_user_id and job.status in ACTIVE_JOB_STATUSES
        )

    def claim_next_queued_job(self, owner_user_id: str | None = None) -> MockJob | None:
        return self.claim_next_runnable_job(owner_user_id=owner_user_id)

    def claim_job_for_worker(
        self,
        public_id: str,
        *,
        lease_timeout_seconds: int | None = None,
    ) -> MockJob | None:
        job = self.get(public_id)
        now = datetime.now(timezone.utc)
        if not _is_runnable_job(job, now, lease_timeout_seconds):
            return None
        job.status = JobStatus.RUNNING
        job.current_stage = PIPELINE_STAGES[0]
        job.worker_attempts += 1
        job.worker_last_claimed_at = now
        job.error_type = None
        job.error_message = None
        return job

    def claim_next_runnable_job(
        self,
        owner_user_id: str | None = None,
        *,
        lease_timeout_seconds: int | None = None,
    ) -> MockJob | None:
        now = datetime.now(timezone.utc)
        for job in self._jobs.values():
            if owner_user_id is not None and job.owner_user_id != owner_user_id:
                continue
            if not _is_runnable_job(job, now, lease_timeout_seconds):
                continue
            job.status = JobStatus.RUNNING
            job.current_stage = PIPELINE_STAGES[0]
            job.worker_attempts += 1
            job.worker_last_claimed_at = now
            job.error_type = None
            job.error_message = None
            return job
        return None

    def retry_current_job(
        self,
        public_id: str,
        *,
        error_type: str,
        error_message: str,
    ) -> MockJob:
        job = self.get(public_id)
        if job.status not in {JobStatus.RUNNING, JobStatus.FAILED}:
            raise StatusTransitionError(f"cannot retry job from {job.status}")
        if job.worker_attempts >= job.max_worker_attempts:
            if job.status == JobStatus.FAILED:
                job.error_type = error_type
                job.error_message = error_message
                return job
            return self.fail_current_job(
                public_id,
                error_type=error_type,
                error_message=error_message,
            )
        job.status = JobStatus.QUEUED
        job.current_stage = None
        job.error_type = error_type
        job.error_message = error_message
        return job

    def touch_worker_job(self, public_id: str) -> MockJob:
        job = self.get(public_id)
        if job.status != JobStatus.RUNNING:
            raise StatusTransitionError(f"cannot touch worker job from {job.status}")
        job.worker_last_claimed_at = datetime.now(timezone.utc)
        return job

    def record_feedback(
        self,
        public_id: str,
        *,
        category: str,
        comment: str,
    ) -> MockFeedback:
        job = self.get(public_id)
        self._feedback_sequence += 1
        feedback = MockFeedback(
            public_id=f"mrf_{self._feedback_sequence}",
            job_id=job.public_id,
            category=category,
            comment=comment,
        )
        job.feedback.append(feedback)
        return feedback

    def record_source(
        self,
        public_id: str,
        *,
        source_type: str,
        display_name: str | None = None,
        snapshot_text: str | None = None,
        content_hash: str | None = None,
    ) -> MockSource:
        job = self.get(public_id)
        source = MockSource(
            public_id=self._id_factory(PUBLIC_ID_PREFIXES.source),
            job_id=job.public_id,
            source_type=source_type,
            display_name=display_name,
            snapshot_text=snapshot_text,
            content_hash=content_hash,
        )
        self._sources.setdefault(job.public_id, []).append(source)
        return source

    def list_sources(self, public_id: str) -> list[MockSource]:
        job = self.get(public_id)
        return list(self._sources.get(job.public_id, []))

    def record_artifact(
        self,
        public_id: str,
        *,
        artifact_type: str,
        content: str | None = None,
        content_hash: str | None = None,
    ) -> MockArtifact:
        job = self.get(public_id)
        artifact = MockArtifact(
            public_id=self._id_factory(PUBLIC_ID_PREFIXES.artifact),
            job_id=job.public_id,
            artifact_type=artifact_type,
            content=content,
            content_hash=content_hash,
        )
        self._artifacts.setdefault(job.public_id, []).append(artifact)
        return artifact

    def list_artifacts(self, public_id: str) -> list[MockArtifact]:
        job = self.get(public_id)
        return list(self._artifacts.get(job.public_id, []))

    def record_validation(
        self,
        public_id: str,
        *,
        rule_id: str,
        severity: str,
        message: str,
        path: str | None = None,
    ) -> MockValidation:
        job = self.get(public_id)
        validation = MockValidation(
            public_id=self._id_factory(PUBLIC_ID_PREFIXES.validation),
            job_id=job.public_id,
            rule_id=rule_id,
            severity=severity,
            message=message,
            path=path,
        )
        self._validations.setdefault(job.public_id, []).append(validation)
        return validation

    def list_validations(self, public_id: str) -> list[MockValidation]:
        job = self.get(public_id)
        return list(self._validations.get(job.public_id, []))

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
        job = self.get(public_id)
        llm_call = MockLLMCall(
            public_id=self._id_factory(PUBLIC_ID_PREFIXES.llm_call),
            job_id=job.public_id,
            prompt_kind=prompt_kind,
            provider=provider,
            requested_model=requested_model,
            resolved_model=resolved_model,
            prompt_version=prompt_version,
            request_hash=request_hash,
            response_hash=response_hash,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=finish_reason,
            error_type=error_type,
        )
        self._llm_calls.setdefault(job.public_id, []).append(llm_call)
        return llm_call

    def list_llm_calls(self, public_id: str) -> list[MockLLMCall]:
        job = self.get(public_id)
        return list(self._llm_calls.get(job.public_id, []))

    def record_audit_log(
        self,
        *,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str,
        metadata: dict[str, object] | None = None,
    ) -> MockAuditLog:
        target_public_id = target_id
        if target_type == "monthly_report_job":
            self.get(target_id)
        audit_log = MockAuditLog(
            public_id=self._id_factory("aud"),
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_public_id,
            metadata=dict(metadata or {}),
        )
        self._audit_logs.setdefault(target_public_id, []).append(audit_log)
        return audit_log

    def list_audit_logs(self, public_id: str) -> list[MockAuditLog]:
        self.get(public_id)
        return list(self._audit_logs.get(public_id, []))

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
            max_worker_attempts=source.max_worker_attempts,
        )

    def start_next(self, public_id: str) -> MockJob:
        job = self.get(public_id)
        if job.status != JobStatus.QUEUED:
            raise StatusTransitionError(f"cannot start job from {job.status}")
        job.status = JobStatus.RUNNING
        job.current_stage = PIPELINE_STAGES[0]
        return job

    def complete_current_stage(self, public_id: str) -> MockJob:
        job = self.get(public_id)
        if job.status not in {JobStatus.RUNNING, JobStatus.CANCEL_REQUESTED}:
            raise StatusTransitionError(f"cannot complete stage from {job.status}")
        if job.current_stage is None:
            raise StatusTransitionError("job has no current stage")

        completed_stage = job.current_stage
        job.completed_stages.append(completed_stage)

        if job.status == JobStatus.CANCEL_REQUESTED:
            job.status = JobStatus.CANCELLED
            job.current_stage = None
            return job

        next_index = PIPELINE_STAGES.index(completed_stage) + 1
        if next_index >= len(PIPELINE_STAGES):
            job.status = JobStatus.SUCCEEDED
            job.current_stage = None
            return job

        job.current_stage = PIPELINE_STAGES[next_index]
        return job

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
        job.status = JobStatus.FAILED
        job.error_type = error_type
        job.error_message = error_message
        return job

    def request_cancel(self, public_id: str) -> MockJob:
        job = self.get(public_id)
        if job.status == JobStatus.QUEUED:
            job.status = JobStatus.CANCELLED
            job.current_stage = None
            return job
        if job.status == JobStatus.RUNNING:
            job.status = JobStatus.CANCEL_REQUESTED
            return job
        return job


def _is_runnable_job(
    job: MockJob,
    now: datetime,
    lease_timeout_seconds: int | None,
) -> bool:
    if job.status == JobStatus.QUEUED:
        return job.worker_attempts < job.max_worker_attempts
    if (
        job.status == JobStatus.RUNNING
        and job.current_stage in WORKER_STALE_RECLAIM_STAGES
        and lease_timeout_seconds is not None
        and job.worker_attempts < job.max_worker_attempts
    ):
        claimed_at = job.worker_last_claimed_at
        if claimed_at is None:
            return True
        if claimed_at.tzinfo is None:
            claimed_at = claimed_at.replace(tzinfo=timezone.utc)
        return claimed_at <= now - timedelta(seconds=lease_timeout_seconds)
    return False
