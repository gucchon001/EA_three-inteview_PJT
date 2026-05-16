from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from eb_app.auth.dependencies import CurrentUser, get_current_user
from eb_app.config import get_settings
from eb_app.monthly_reports.jobs import (
    DEFAULT_MOCK_OWNER_USER_ID,
    JobLimitExceeded,
    MAX_ACTIVE_JOBS_PER_USER,
    MockJob,
    MockJobStore,
    MockArtifact,
    MockSource,
    MockValidation,
    MockLLMCall,
    StatusTransitionError,
)
from eb_app.monthly_reports.google_workspace import (
    GoogleWorkspaceClient,
    GoogleWorkspaceFetchError,
    fetch_google_workspace_sources_for_job,
)
from eb_app.monthly_reports.oauth_credentials import (
    FernetTokenCipher,
    GoogleOAuthTokenRefreshError,
    GoogleOAuthTokenRefresher,
    PostgresGoogleOAuthCredentialStore,
    resolve_google_access_token,
)
from eb_app.monthly_reports.postgres_store import PostgresJobStore
from eb_app.monthly_reports.workflow import (
    OpenRouterMonthlyReportProvider,
    StaticMonthlyReportProvider,
    run_monthly_report_job,
)

router = APIRouter()

_store = MockJobStore()
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_MONTHLY_REPORT_TEMPLATE = (
    _PROJECT_ROOT
    / "docs"
    / "samples"
    / "monthly-reports"
    / "monthly_pattern_b_content.template.md"
)


class CreateMonthlyReportJobRequest(BaseModel):
    target_month: str = Field(min_length=7, max_length=7)
    household_key: str = Field(min_length=1)
    owner_user_id: str = Field(DEFAULT_MOCK_OWNER_USER_ID, min_length=1)
    spreadsheet_id: str | None = None
    doc_ids: list[str] = Field(default_factory=list)
    template_key: str | None = None
    notes: str | None = None
    prompt_version: str | None = None
    template_hash: str | None = None
    model_report: str | None = None
    model_light: str | None = None
    resolved_model_report: str | None = None
    source_bundle_hash: str | None = None
    app_version: str | None = None
    prompt_scope_notes: str | None = None


class CreateMonthlyReportFeedbackRequest(BaseModel):
    category: str = Field(min_length=1)
    comment: str = Field(min_length=1)


class FailMonthlyReportJobRequest(BaseModel):
    error_type: str = Field(min_length=1)
    error_message: str | None = None
    message: str | None = None


class CreateMonthlyReportSourceRequest(BaseModel):
    source_type: str = Field(min_length=1)
    display_name: str | None = None
    snapshot_text: str | None = None
    content_hash: str | None = None


class GoogleSheetRangeRequest(BaseModel):
    spreadsheet_id: str = Field(min_length=1)
    range_name: str = Field(min_length=1)
    display_name: str | None = None


class FetchGoogleWorkspaceSourcesRequest(BaseModel):
    doc_ids: list[str] = Field(default_factory=list)
    sheet_ranges: list[GoogleSheetRangeRequest] = Field(default_factory=list)


class CreateMonthlyReportArtifactRequest(BaseModel):
    artifact_type: str = Field(min_length=1)
    content: str | None = None
    content_hash: str | None = None


class CreateMonthlyReportValidationRequest(BaseModel):
    rule_id: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    message: str = Field(min_length=1)
    path: str | None = None


class RunMonthlyReportMockRequest(BaseModel):
    content: str = Field(min_length=1)


def _job_response(job: MockJob) -> dict[str, Any]:
    return {
        "job_id": job.public_id,
        "status": job.status,
        "target_month": job.target_month,
        "household_key": job.household_key,
        "owner_user_id": job.owner_user_id,
        "current_stage": job.current_stage,
        "completed_stages": job.completed_stages,
        "feedback_count": len(job.feedback),
        "error_type": job.error_type,
        "error_message": job.error_message,
        "template_key": job.template_key,
        "prompt_version": job.prompt_version,
        "template_hash": job.template_hash,
        "model_report": job.model_report,
        "model_light": job.model_light,
        "resolved_model_report": job.resolved_model_report,
        "source_bundle_hash": job.source_bundle_hash,
        "app_version": job.app_version,
        "prompt_scope_notes": job.prompt_scope_notes,
    }


def _source_response(source: MockSource) -> dict[str, Any]:
    return {
        "source_id": source.public_id,
        "job_id": source.job_id,
        "source_type": source.source_type,
        "display_name": source.display_name,
        "snapshot_text": source.snapshot_text,
        "content_hash": source.content_hash,
    }


def _artifact_response(artifact: MockArtifact) -> dict[str, Any]:
    return {
        "artifact_id": artifact.public_id,
        "job_id": artifact.job_id,
        "artifact_type": artifact.artifact_type,
        "content": artifact.content,
        "content_hash": artifact.content_hash,
    }


def _validation_response(validation: MockValidation) -> dict[str, Any]:
    return {
        "validation_id": validation.public_id,
        "job_id": validation.job_id,
        "rule_id": validation.rule_id,
        "severity": validation.severity,
        "message": validation.message,
        "path": validation.path,
    }


def _llm_call_response(call: MockLLMCall) -> dict[str, Any]:
    return {
        "llm_call_id": call.public_id,
        "job_id": call.job_id,
        "prompt_kind": call.prompt_kind,
        "provider": call.provider,
        "requested_model": call.requested_model,
        "resolved_model": call.resolved_model,
        "prompt_version": call.prompt_version,
        "request_hash": call.request_hash,
        "response_hash": call.response_hash,
        "latency_ms": call.latency_ms,
        "input_tokens": call.input_tokens,
        "output_tokens": call.output_tokens,
        "finish_reason": call.finish_reason,
        "error_type": call.error_type,
    }


def _get_job_or_404(job_id: str) -> MockJob:
    try:
        return _get_store().get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="monthly report job not found") from exc


def _get_authorized_job_or_404(job_id: str, current_user: CurrentUser) -> MockJob:
    job = _get_job_or_404(job_id)
    if not _can_access_job(job, current_user):
        raise HTTPException(status_code=404, detail="monthly report job not found")
    return job


def _can_access_job(job: MockJob, current_user: CurrentUser) -> bool:
    if get_settings().auth_mode == "mock":
        return True
    if current_user.role == "admin":
        return True
    return job.owner_user_id == current_user.user_id


def _get_store() -> MockJobStore | PostgresJobStore:
    database_url = get_settings().monthly_report_database_url
    if database_url:
        return PostgresJobStore(database_url)
    return _store


def _run_transition(operation: Any) -> dict[str, Any]:
    try:
        return _job_response(operation())
    except StatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/jobs")
def create_job(
    payload: CreateMonthlyReportJobRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    store = _get_store()
    owner_user_id = (
        payload.owner_user_id
        if get_settings().auth_mode == "mock"
        else current_user.user_id
    )
    try:
        job = store.create_job_with_active_limit(
            target_month=payload.target_month,
            household_key=payload.household_key,
            owner_user_id=owner_user_id,
            max_active_jobs=MAX_ACTIVE_JOBS_PER_USER,
            template_key=payload.template_key,
            prompt_version=payload.prompt_version,
            template_hash=payload.template_hash,
            model_report=payload.model_report,
            model_light=payload.model_light,
            resolved_model_report=payload.resolved_model_report,
            source_bundle_hash=payload.source_bundle_hash,
            app_version=payload.app_version,
            prompt_scope_notes=payload.prompt_scope_notes,
        )
    except JobLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return _job_response(job)


@router.get("/jobs")
def list_jobs(current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "jobs": [
            _job_response(job)
            for job in _get_store().list_jobs()
            if _can_access_job(job, current_user)
        ]
    }


@router.get("/jobs/{job_id}")
def get_job(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    return _job_response(_get_authorized_job_or_404(job_id, current_user))


@router.post("/jobs/{job_id}/rerun")
def rerun_job(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    source = _get_authorized_job_or_404(job_id, current_user)
    store = _get_store()
    if store.count_active_jobs(source.owner_user_id) >= MAX_ACTIVE_JOBS_PER_USER:
        raise HTTPException(
            status_code=429,
            detail="user already has 3 active generation jobs",
        )
    return _job_response(store.rerun_job(source.public_id))


@router.post("/jobs/{job_id}/feedback")
def record_feedback(
    job_id: str,
    payload: CreateMonthlyReportFeedbackRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    feedback = _get_store().record_feedback(
        _get_authorized_job_or_404(job_id, current_user).public_id,
        category=payload.category,
        comment=payload.comment,
    )
    return {
        "feedback_id": feedback.public_id,
        "job_id": feedback.job_id,
        "category": feedback.category,
        "comment": feedback.comment,
    }


@router.post("/jobs/{job_id}/sources")
def record_source(
    job_id: str,
    payload: CreateMonthlyReportSourceRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    source = _get_store().record_source(
        _get_authorized_job_or_404(job_id, current_user).public_id,
        source_type=payload.source_type,
        display_name=payload.display_name,
        snapshot_text=payload.snapshot_text,
        content_hash=payload.content_hash,
    )
    return _source_response(source)


@router.get("/jobs/{job_id}/sources")
def list_sources(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "sources": [
            _source_response(source)
            for source in _get_store().list_sources(
                _get_authorized_job_or_404(job_id, current_user).public_id
            )
        ]
    }


@router.post("/jobs/{job_id}/fetch-google-sources")
def fetch_google_sources(
    job_id: str,
    payload: FetchGoogleWorkspaceSourcesRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        access_token = _resolve_google_workspace_access_token(current_user)
    except GoogleOAuthTokenRefreshError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not access_token:
        raise HTTPException(
            status_code=503,
            detail="Google Workspace access token is not configured",
        )

    job = _get_authorized_job_or_404(job_id, current_user)
    store = _get_store()
    try:
        sources = fetch_google_workspace_sources_for_job(
            store,
            job.public_id,
            client=GoogleWorkspaceClient(
                access_token=access_token
            ),
            doc_ids=payload.doc_ids,
            sheet_ranges=[
                sheet_range.model_dump(exclude_none=True)
                for sheet_range in payload.sheet_ranges
            ],
        )
    except GoogleWorkspaceFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"sources": [_source_response(source) for source in sources]}


def _resolve_google_workspace_access_token(current_user: CurrentUser) -> str | None:
    settings = get_settings()
    if settings.google_workspace_access_token:
        return settings.google_workspace_access_token
    if not (
        settings.monthly_report_database_url
        and settings.google_oauth_client_id
        and settings.google_oauth_client_secret
        and settings.google_token_encryption_key
    ):
        return None
    return resolve_google_access_token(
        user_id=current_user.user_id,
        configured_access_token=None,
        credential_store=PostgresGoogleOAuthCredentialStore(
            settings.monthly_report_database_url,
            cipher=FernetTokenCipher(key=settings.google_token_encryption_key),
            encryption_key_version=settings.google_token_encryption_key_version,
        ),
        refresher=GoogleOAuthTokenRefresher(
            client_id=settings.google_oauth_client_id,
            client_secret=settings.google_oauth_client_secret,
        ),
    )


@router.post("/jobs/{job_id}/artifacts")
def record_artifact(
    job_id: str,
    payload: CreateMonthlyReportArtifactRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    artifact = _get_store().record_artifact(
        _get_authorized_job_or_404(job_id, current_user).public_id,
        artifact_type=payload.artifact_type,
        content=payload.content,
        content_hash=payload.content_hash,
    )
    return _artifact_response(artifact)


@router.get("/jobs/{job_id}/artifacts")
def list_artifacts(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "artifacts": [
            _artifact_response(artifact)
            for artifact in _get_store().list_artifacts(
                _get_authorized_job_or_404(job_id, current_user).public_id
            )
        ]
    }


@router.post("/jobs/{job_id}/validations")
def record_validation(
    job_id: str,
    payload: CreateMonthlyReportValidationRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    validation = _get_store().record_validation(
        _get_authorized_job_or_404(job_id, current_user).public_id,
        rule_id=payload.rule_id,
        severity=payload.severity,
        message=payload.message,
        path=payload.path,
    )
    return _validation_response(validation)


@router.get("/jobs/{job_id}/validations")
def list_validations(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "validations": [
            _validation_response(validation)
            for validation in _get_store().list_validations(
                _get_authorized_job_or_404(job_id, current_user).public_id
            )
        ]
    }


@router.get("/jobs/{job_id}/llm-calls")
def list_llm_calls(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "llm_calls": [
            _llm_call_response(call)
            for call in _get_store().list_llm_calls(
                _get_authorized_job_or_404(job_id, current_user).public_id
            )
        ]
    }


@router.post("/jobs/{job_id}/start")
def start_job(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    job = _get_authorized_job_or_404(job_id, current_user)
    store = _get_store()
    return _run_transition(lambda: store.start_next(job.public_id))


@router.post("/jobs/{job_id}/complete-stage")
def complete_current_stage(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    job = _get_authorized_job_or_404(job_id, current_user)
    store = _get_store()
    return _run_transition(lambda: store.complete_current_stage(job.public_id))


@router.post("/jobs/{job_id}/fail")
def fail_job(
    job_id: str,
    payload: FailMonthlyReportJobRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    error_message = payload.error_message or payload.message
    if not error_message:
        raise HTTPException(status_code=422, detail="error_message is required")
    job = _get_authorized_job_or_404(job_id, current_user)
    store = _get_store()
    return _run_transition(
        lambda: store.fail_current_job(
            job.public_id,
            error_type=payload.error_type,
            error_message=error_message,
        )
    )


@router.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    return _job_response(
        _get_store().request_cancel(
            _get_authorized_job_or_404(job_id, current_user).public_id
        )
    )


@router.post("/jobs/{job_id}/run-mock")
def run_job_with_mock_provider(
    job_id: str,
    payload: RunMonthlyReportMockRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    job = _get_authorized_job_or_404(job_id, current_user)
    store = _get_store()
    try:
        return _job_response(
            run_monthly_report_job(
                store,
                job.public_id,
                provider=StaticMonthlyReportProvider(payload.content),
                template_path=_DEFAULT_MONTHLY_REPORT_TEMPLATE,
            )
        )
    except StatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/run-openrouter")
def run_job_with_openrouter(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENROUTER_API_KEY is not configured",
        )

    job = _get_authorized_job_or_404(job_id, current_user)
    store = _get_store()
    try:
        return _job_response(
            run_monthly_report_job(
                store,
                job.public_id,
                provider=OpenRouterMonthlyReportProvider(
                    api_key=settings.openrouter_api_key,
                    model=settings.openrouter_model_report,
                    timeout=settings.openrouter_timeout_seconds,
                    max_tokens=settings.openrouter_max_tokens,
                ),
                template_path=_DEFAULT_MONTHLY_REPORT_TEMPLATE,
            )
        )
    except StatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
