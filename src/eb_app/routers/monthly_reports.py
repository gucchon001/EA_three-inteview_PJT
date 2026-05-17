from __future__ import annotations

import hmac
from hashlib import sha256
import secrets
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment
from pydantic import BaseModel, Field

from eb_app.auth.dependencies import CurrentUser, get_current_user
from eb_app.auth.supabase_client import create_supabase_user_client
from eb_app.config import get_settings
from eb_app.monthly_reports.jobs import (
    DEFAULT_MOCK_OWNER_USER_ID,
    JobLimitExceeded,
    JobStatus,
    MAX_ACTIVE_JOBS_PER_USER,
    PIPELINE_STAGES,
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
from eb_app.monthly_reports.supabase_read_store import SupabaseMonthlyReportReadStore
from eb_app.monthly_reports.workflow import (
    OpenRouterMonthlyReportProvider,
    StaticMonthlyReportProvider,
    run_monthly_report_job,
)

router = APIRouter()
html_router = APIRouter()

_store = MockJobStore()
_idempotency_lock = threading.Lock()
_idempotency_job_ids: dict[tuple[str, str, str], str] = {}
_idempotency_responses: dict[tuple[str, str, str], dict[str, Any]] = {}
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_MONTHLY_REPORT_TEMPLATE = (
    _PROJECT_ROOT
    / "docs"
    / "samples"
    / "monthly-reports"
    / "monthly_pattern_b_content.template.md"
)
_PIPELINE_STAGE_LABELS = {
    "fetch_sources": "ソース取得",
    "bundle": "バンドル",
    "build_messages": "プロンプト構築",
    "call_llm": "LLM本文生成",
    "validate": "規約検証",
    "persist": "成果物保存",
}
_CSRF_COOKIE_NAME = "eb_monthly_report_csrf"
_IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"


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


def _normalize_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 200:
        raise HTTPException(status_code=422, detail="Idempotency-Key is too long")
    return normalized


def _idempotency_key_from_request(request: Request) -> str | None:
    return _normalize_idempotency_key(request.headers.get(_IDEMPOTENCY_KEY_HEADER))


def _idempotency_key_from_form(form: Any, request: Request) -> str | None:
    return _normalize_idempotency_key(
        str(form.get("idempotency_key") or "")
        or request.headers.get(_IDEMPOTENCY_KEY_HEADER)
    )


def _idempotency_scope(operation: str, owner_user_id: str, key: str) -> tuple[str, str, str]:
    return operation, owner_user_id, key


def _get_idempotent_job(
    operation: str,
    owner_user_id: str,
    key: str | None,
    store: MockJobStore | PostgresJobStore,
) -> MockJob | None:
    if key is None:
        return None
    persistent_lookup = getattr(store, "get_idempotent_job", None)
    if persistent_lookup is not None:
        existing = persistent_lookup(operation, owner_user_id, key)
        if existing is not None:
            return existing
    scope = _idempotency_scope(operation, owner_user_id, key)
    with _idempotency_lock:
        job_id = _idempotency_job_ids.get(scope)
    if job_id is None:
        return None
    try:
        return store.get(job_id)
    except KeyError:
        with _idempotency_lock:
            _idempotency_job_ids.pop(scope, None)
        return None


def _remember_idempotent_job(
    operation: str,
    owner_user_id: str,
    key: str | None,
    job: MockJob,
    store: MockJobStore | PostgresJobStore | None = None,
) -> None:
    if key is None:
        return
    persistent_remember = getattr(store, "remember_idempotent_job", None)
    if persistent_remember is not None:
        persistent_remember(operation, owner_user_id, key, job.public_id)
    scope = _idempotency_scope(operation, owner_user_id, key)
    with _idempotency_lock:
        _idempotency_job_ids[scope] = job.public_id


def _get_idempotent_response(
    operation: str,
    owner_user_id: str,
    key: str | None,
    store: MockJobStore | PostgresJobStore | None = None,
) -> dict[str, Any] | None:
    if key is None:
        return None
    persistent_lookup = getattr(store, "get_idempotent_response", None)
    if persistent_lookup is not None:
        response = persistent_lookup(operation, owner_user_id, key)
        if response is not None:
            return response
    scope = _idempotency_scope(operation, owner_user_id, key)
    with _idempotency_lock:
        response = _idempotency_responses.get(scope)
    if response is None:
        return None
    return dict(response)


def _remember_idempotent_response(
    operation: str,
    owner_user_id: str,
    key: str | None,
    response: dict[str, Any],
    store: MockJobStore | PostgresJobStore | None = None,
) -> None:
    if key is None:
        return
    persistent_remember = getattr(store, "remember_idempotent_response", None)
    if persistent_remember is not None:
        persistent_remember(operation, owner_user_id, key, response)
    scope = _idempotency_scope(operation, owner_user_id, key)
    with _idempotency_lock:
        _idempotency_responses[scope] = dict(response)


def _get_read_authorized_job_or_404(job_id: str, current_user: CurrentUser) -> MockJob:
    store = _get_read_store(current_user)
    try:
        job = store.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="monthly report job not found") from exc
    if not _can_access_job(job, current_user):
        raise HTTPException(status_code=404, detail="monthly report job not found")
    return job


def _get_write_preflight_authorized_job_or_404(
    job_id: str,
    current_user: CurrentUser,
) -> MockJob:
    rls_read_store = _get_rls_read_store(current_user)
    if rls_read_store is None:
        return _get_authorized_job_or_404(job_id, current_user)
    try:
        job = rls_read_store.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="monthly report job not found") from exc
    if not _can_access_job(job, current_user):
        raise HTTPException(status_code=404, detail="monthly report job not found")
    return _get_job_or_404(job.public_id)


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


def _get_read_store(
    current_user: CurrentUser,
) -> MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore:
    return _get_rls_read_store(current_user) or _get_store()


def _get_rls_read_store(current_user: CurrentUser) -> SupabaseMonthlyReportReadStore | None:
    settings = get_settings()
    if settings.auth_mode == "mock" or current_user.role == "admin":
        return None
    if not (settings.supabase_url and settings.supabase_anon_key and current_user.access_token):
        return None
    return SupabaseMonthlyReportReadStore(
        create_supabase_user_client(settings, current_user)
    )


def _templates(request: Request) -> Environment:
    return request.app.state.jinja_env


def _render_html(
    templates: Environment,
    template_name: str,
    context: dict[str, Any],
    *,
    status_code: int = 200,
) -> HTMLResponse:
    return HTMLResponse(
        templates.get_template(template_name).render(**context),
        status_code=status_code,
    )


def _set_csrf_cookie(response: HTMLResponse, request: Request, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        _CSRF_COOKIE_NAME,
        token,
        httponly=True,
        secure=request.url.scheme == "https" or settings.env not in {"local", "dev", "test"},
        samesite="lax",
        path="/monthly-reports",
    )


def _new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _new_idempotency_key() -> str:
    return secrets.token_urlsafe(32)


def _csrf_token_for_request(request: Request) -> str:
    return request.cookies.get(_CSRF_COOKIE_NAME) or _new_csrf_token()


def _verify_csrf_token(form: Any, request: Request) -> None:
    form_token = str(form.get("csrf_token") or "")
    cookie_token = request.cookies.get(_CSRF_COOKIE_NAME) or ""
    if not (
        form_token
        and cookie_token
        and hmac.compare_digest(form_token, cookie_token)
    ):
        raise HTTPException(status_code=403, detail="CSRF token is invalid")


def _job_view(job: MockJob) -> dict[str, Any]:
    return {
        **_job_response(job),
        "public_id": job.public_id,
        "display_household": job.household_key,
        "model": job.resolved_model_report or job.model_report or "-",
        "validation": "未検証",
        "detail_href": f"/monthly-reports/jobs/{job.public_id}",
        "edit_href": f"/monthly-reports/jobs/{job.public_id}/edit",
        "status_fragment_href": (
            f"/monthly-reports/jobs/{job.public_id}/fragments/status"
        ),
        "stages": _stage_views(job),
        "feedback": [
            {"feedback_id": item.public_id, "category": item.category, "comment": item.comment}
            for item in job.feedback
        ],
    }


def _artifact_view(artifact: MockArtifact) -> dict[str, Any]:
    return {
        "artifact_id": artifact.public_id,
        "artifact_type": artifact.artifact_type,
        "content": artifact.content or "",
        "content_hash": artifact.content_hash or "-",
    }


def _source_view(source: MockSource) -> dict[str, Any]:
    return {
        "source_id": source.public_id,
        "source_type": source.source_type,
        "display_name": source.display_name or source.source_type,
        "snapshot_text": source.snapshot_text or "",
        "content_hash": source.content_hash or "-",
    }


def _validation_view(validation: MockValidation) -> dict[str, Any]:
    return {
        "validation_id": validation.public_id,
        "rule_id": validation.rule_id,
        "severity": validation.severity,
        "message": validation.message,
        "path": validation.path or "-",
    }


def _latest_preview_artifact(
    job: MockJob,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> dict[str, Any] | None:
    read_store = store or _get_store()
    artifacts = [
        artifact
        for artifact in read_store.list_artifacts(job.public_id)
        if artifact.artifact_type in {"draft_markdown", "final_markdown", "html"}
    ]
    if not artifacts:
        return None
    return _artifact_view(artifacts[-1])


def _hash_text(text: str) -> str:
    return f"sha256:{sha256(text.encode('utf-8')).hexdigest()}"


def _source_views(
    job: MockJob,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> list[dict[str, Any]]:
    read_store = store or _get_store()
    return [
        _source_view(source)
        for source in read_store.list_sources(job.public_id)
    ]


def _validation_views(
    job: MockJob,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> list[dict[str, Any]]:
    read_store = store or _get_store()
    return [
        _validation_view(validation)
        for validation in read_store.list_validations(job.public_id)
    ]


def _nonempty_lines(value: str | None) -> list[str]:
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


def _stage_views(job: MockJob) -> list[dict[str, str]]:
    current = job.current_stage
    completed = set(job.completed_stages)
    stages: list[dict[str, str]] = []
    for stage in PIPELINE_STAGES:
        if stage in completed:
            state = "done"
        elif stage == current:
            state = "running"
        elif job.status == JobStatus.SUCCEEDED:
            state = "done"
        elif job.status in {JobStatus.FAILED, JobStatus.CANCELLED}:
            state = "stopped"
        else:
            state = "pending"
        stages.append(
            {
                "id": stage,
                "label": _PIPELINE_STAGE_LABELS[stage],
                "state": state,
                "duration": "-",
            }
        )
    return stages


def _visible_jobs(current_user: CurrentUser) -> list[MockJob]:
    return [
        job
        for job in _get_read_store(current_user).list_jobs()
        if _can_access_job(job, current_user)
    ]


async def _create_job_from_form(
    request: Request,
    current_user: CurrentUser,
) -> MockJob:
    form = await request.form()
    _verify_csrf_token(form, request)
    idempotency_key = _idempotency_key_from_form(form, request)
    payload = CreateMonthlyReportJobRequest(
        target_month=str(form.get("target_month") or ""),
        household_key=str(form.get("household_key") or ""),
        owner_user_id=str(form.get("owner_user_id") or DEFAULT_MOCK_OWNER_USER_ID),
        template_key=str(form.get("template_key") or "") or None,
        prompt_version=str(form.get("prompt_version") or "") or None,
        prompt_scope_notes=str(form.get("prompt_scope_notes") or "") or None,
    )
    owner_user_id = (
        payload.owner_user_id
        if get_settings().auth_mode == "mock"
        else current_user.user_id
    )
    store = _get_store()
    existing = _get_idempotent_job(
        "create_job",
        owner_user_id,
        idempotency_key,
        store,
    )
    if existing is not None:
        return existing
    job = store.create_job_with_active_limit(
        target_month=payload.target_month,
        household_key=payload.household_key,
        owner_user_id=owner_user_id,
        max_active_jobs=MAX_ACTIVE_JOBS_PER_USER,
        template_key=payload.template_key,
        prompt_version=payload.prompt_version,
        prompt_scope_notes=payload.prompt_scope_notes,
    )
    _remember_idempotent_job("create_job", owner_user_id, idempotency_key, job, store)
    return job


def _run_transition(operation: Any) -> dict[str, Any]:
    try:
        return _job_response(operation())
    except StatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@html_router.get("/monthly-reports", response_class=HTMLResponse)
def monthly_report_home(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    jobs = [_job_view(job) for job in _visible_jobs(current_user)]
    return _render_html(
        _templates(request),
        "monthly_report_workshop/jobs.html",
        {
            "page_title": "レポート工房",
            "current_user": current_user,
            "jobs": jobs,
            "metrics": _job_metrics(jobs),
        },
    )


@html_router.get("/monthly-reports/jobs", response_class=HTMLResponse)
def monthly_report_jobs_page(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    jobs = [_job_view(job) for job in _visible_jobs(current_user)]
    return _render_html(
        _templates(request),
        "monthly_report_workshop/jobs.html",
        {
            "page_title": "レポート工房",
            "current_user": current_user,
            "jobs": jobs,
            "metrics": _job_metrics(jobs),
        },
    )


@html_router.get("/monthly-reports/jobs/new", response_class=HTMLResponse)
def monthly_report_new_job_page(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    csrf_token = _csrf_token_for_request(request)
    response = _render_html(
        _templates(request),
        "monthly_report_workshop/new.html",
        {
            "page_title": "新規ジョブ作成",
            "current_user": current_user,
            "target_month": "2026-04",
            "templates": ["pattern_b"],
            "csrf_token": csrf_token,
            "idempotency_key": _new_idempotency_key(),
        },
    )
    _set_csrf_cookie(response, request, csrf_token)
    return response


@html_router.post("/monthly-reports/jobs", response_class=HTMLResponse)
async def monthly_report_create_job_action(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    templates = _templates(request)
    try:
        job = await _create_job_from_form(request, current_user)
    except HTTPException as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc.detail)},
            status_code=exc.status_code,
        )
    except JobLimitExceeded as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc)},
            status_code=429,
        )
    except ValueError as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc)},
            status_code=422,
        )
    return _render_html(
        templates,
        "monthly_report_workshop/fragments/job_created.html",
        {"job": _job_view(job)},
    )


@html_router.get("/monthly-reports/jobs/{job_id}", response_class=HTMLResponse)
def monthly_report_job_detail_page(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    job = _get_read_authorized_job_or_404(job_id, current_user)
    csrf_token = _csrf_token_for_request(request)
    response = _render_html(
        _templates(request),
        "monthly_report_workshop/detail.html",
        {
            "page_title": "ジョブ詳細",
            "current_user": current_user,
            "job": _job_view(job),
            "csrf_token": csrf_token,
            "run_idempotency_key": _new_idempotency_key(),
            "rerun_idempotency_key": _new_idempotency_key(),
            "source_idempotency_key": _new_idempotency_key(),
            "google_sources_idempotency_key": _new_idempotency_key(),
            "edited_markdown_idempotency_key": _new_idempotency_key(),
            "feedback_idempotency_key": _new_idempotency_key(),
        },
    )
    _set_csrf_cookie(response, request, csrf_token)
    return response


@html_router.get("/monthly-reports/jobs/{job_id}/fragments/status", response_class=HTMLResponse)
def monthly_report_status_fragment(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    job = _get_read_authorized_job_or_404(job_id, current_user)
    return _render_html(
        _templates(request),
        "monthly_report_workshop/fragments/status.html",
        {"job": _job_view(job)},
    )


@html_router.get("/monthly-reports/jobs/{job_id}/fragments/preview", response_class=HTMLResponse)
def monthly_report_preview_fragment(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    store = _get_read_store(current_user)
    job = _get_read_authorized_job_or_404(job_id, current_user)
    return _render_html(
        _templates(request),
        "monthly_report_workshop/fragments/preview.html",
        {
            "job": _job_view(job),
            "artifact": _latest_preview_artifact(job, store),
        },
    )


@html_router.get("/monthly-reports/jobs/{job_id}/fragments/sources", response_class=HTMLResponse)
def monthly_report_sources_fragment(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    store = _get_read_store(current_user)
    job = _get_read_authorized_job_or_404(job_id, current_user)
    return _render_html(
        _templates(request),
        "monthly_report_workshop/fragments/sources.html",
        {
            "job": _job_view(job),
            "sources": _source_views(job, store),
            "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
        },
    )


@html_router.get("/monthly-reports/jobs/{job_id}/fragments/validation", response_class=HTMLResponse)
def monthly_report_validation_fragment(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    store = _get_read_store(current_user)
    job = _get_read_authorized_job_or_404(job_id, current_user)
    return _render_html(
        _templates(request),
        "monthly_report_workshop/fragments/validation.html",
        {
            "job": _job_view(job),
            "validations": _validation_views(job, store),
        },
    )


@html_router.post("/monthly-reports/jobs/{job_id}/rerun", response_class=HTMLResponse)
async def monthly_report_rerun_action(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    templates = _templates(request)
    form = await request.form()
    try:
        _verify_csrf_token(form, request)
        source = _get_write_preflight_authorized_job_or_404(job_id, current_user)
        store = _get_store()
        if store.count_active_jobs(source.owner_user_id) >= MAX_ACTIVE_JOBS_PER_USER:
            raise JobLimitExceeded("user already has 3 active generation jobs")
        rerun = store.rerun_job(source.public_id)
    except HTTPException as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc.detail)},
            status_code=exc.status_code,
        )
    except JobLimitExceeded as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc)},
            status_code=429,
        )
    except ValueError as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc)},
            status_code=422,
        )
    return _render_html(
        templates,
        "monthly_report_workshop/fragments/status.html",
        {"job": _job_view(rerun)},
    )


@html_router.post(
    "/monthly-reports/jobs/{job_id}/fragments/edited-markdown",
    response_class=HTMLResponse,
)
async def monthly_report_edited_markdown_fragment(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    templates = _templates(request)
    form = await request.form()
    try:
        _verify_csrf_token(form, request)
        content = str(form.get("edited_markdown") or "").strip()
        if not content:
            raise HTTPException(status_code=422, detail="edited_markdown is required")
        job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
        store = _get_store()
        idempotency_key = _idempotency_key_from_form(form, request)
        operation = f"html-edited-markdown:{job.public_id}"
        existing = _get_idempotent_response(
            operation,
            job.owner_user_id,
            idempotency_key,
            store,
        )
        if existing is not None:
            return _render_html(
                templates,
                "monthly_report_workshop/fragments/preview.html",
                {
                    "job": existing["job"],
                    "artifact": existing["artifact"],
                },
            )
        store.record_artifact(
            job.public_id,
            artifact_type="final_markdown",
            content=content,
            content_hash=_hash_text(content),
        )
        job = _get_authorized_job_or_404(job_id, current_user)
        response_context = {
            "job": _job_view(job),
            "artifact": _latest_preview_artifact(job),
        }
        _remember_idempotent_response(
            operation,
            job.owner_user_id,
            idempotency_key,
            response_context,
            store,
        )
    except HTTPException as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc.detail)},
            status_code=exc.status_code,
        )
    except ValueError as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc)},
            status_code=422,
        )
    return _render_html(
        templates,
        "monthly_report_workshop/fragments/preview.html",
        {
            "job": _job_view(job),
            "artifact": _latest_preview_artifact(job),
        },
    )


@html_router.post(
    "/monthly-reports/jobs/{job_id}/fragments/sources",
    response_class=HTMLResponse,
)
async def monthly_report_source_fragment(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    templates = _templates(request)
    form = await request.form()
    try:
        _verify_csrf_token(form, request)
        job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
        store = _get_store()
        idempotency_key = _idempotency_key_from_form(form, request)
        operation = f"html-source:{job.public_id}"
        existing = _get_idempotent_response(
            operation,
            job.owner_user_id,
            idempotency_key,
            store,
        )
        if existing is not None:
            return _render_html(
                templates,
                "monthly_report_workshop/fragments/sources.html",
                {
                    "job": existing["job"],
                    "sources": existing["sources"],
                    "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
                },
            )
        payload = CreateMonthlyReportSourceRequest(
            source_type=str(form.get("source_type") or ""),
            display_name=str(form.get("display_name") or "") or None,
            snapshot_text=str(form.get("snapshot_text") or "") or None,
            content_hash=str(form.get("content_hash") or "") or None,
        )
        store.record_source(
            job.public_id,
            source_type=payload.source_type,
            display_name=payload.display_name,
            snapshot_text=payload.snapshot_text,
            content_hash=payload.content_hash,
        )
        job = _get_authorized_job_or_404(job_id, current_user)
        response_context = {
            "job": _job_view(job),
            "sources": _source_views(job),
        }
        _remember_idempotent_response(
            operation,
            job.owner_user_id,
            idempotency_key,
            response_context,
            store,
        )
    except HTTPException as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc.detail)},
            status_code=exc.status_code,
        )
    except ValueError as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc)},
            status_code=422,
        )
    return _render_html(
        templates,
        "monthly_report_workshop/fragments/sources.html",
        {
            "job": _job_view(job),
            "sources": _source_views(job),
            "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
        },
    )


@html_router.post(
    "/monthly-reports/jobs/{job_id}/fragments/google-sources",
    response_class=HTMLResponse,
)
async def monthly_report_google_sources_fragment(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    templates = _templates(request)
    form = await request.form()
    try:
        _verify_csrf_token(form, request)
        job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
        store = _get_store()
        idempotency_key = _idempotency_key_from_form(form, request)
        operation = f"html-google-sources:{job.public_id}"
        existing = _get_idempotent_response(
            operation,
            job.owner_user_id,
            idempotency_key,
            store,
        )
        if existing is not None:
            return _render_html(
                templates,
                "monthly_report_workshop/fragments/sources.html",
                {
                    "job": existing["job"],
                    "sources": existing["sources"],
                    "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
                },
            )
        doc_ids = _nonempty_lines(str(form.get("doc_ids") or ""))
        sheet_ranges = []
        spreadsheet_id = str(form.get("spreadsheet_id") or "").strip()
        range_name = str(form.get("range_name") or "").strip()
        if spreadsheet_id or range_name:
            sheet_ranges.append(
                GoogleSheetRangeRequest(
                    spreadsheet_id=spreadsheet_id,
                    range_name=range_name,
                    display_name=str(form.get("sheet_display_name") or "") or None,
                )
            )
        if not doc_ids and not sheet_ranges:
            raise HTTPException(
                status_code=422,
                detail="Google Doc ID or Sheet range is required",
            )
        access_token = _resolve_google_workspace_access_token(current_user)
        if not access_token:
            raise HTTPException(
                status_code=503,
                detail="Google Workspace access token is not configured",
            )
        fetch_google_workspace_sources_for_job(
            store,
            job.public_id,
            client=GoogleWorkspaceClient(access_token=access_token),
            doc_ids=doc_ids,
            sheet_ranges=[
                sheet_range.model_dump(exclude_none=True)
                for sheet_range in sheet_ranges
            ],
        )
        job = _get_authorized_job_or_404(job_id, current_user)
        response_context = {
            "job": _job_view(job),
            "sources": _source_views(job),
        }
        _remember_idempotent_response(
            operation,
            job.owner_user_id,
            idempotency_key,
            response_context,
            store,
        )
    except HTTPException as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc.detail)},
            status_code=exc.status_code,
        )
    except (GoogleOAuthTokenRefreshError, GoogleWorkspaceFetchError):
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": "Google Workspace source fetch failed"},
            status_code=502,
        )
    except ValueError:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": "Google source input is invalid"},
            status_code=422,
        )
    return _render_html(
        templates,
        "monthly_report_workshop/fragments/sources.html",
        {
            "job": _job_view(job),
            "sources": _source_views(job),
            "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
        },
    )


@html_router.post(
    "/monthly-reports/jobs/{job_id}/fragments/feedback",
    response_class=HTMLResponse,
)
async def monthly_report_feedback_fragment(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    templates = _templates(request)
    form = await request.form()
    try:
        _verify_csrf_token(form, request)
        payload = CreateMonthlyReportFeedbackRequest(
            category=str(form.get("category") or ""),
            comment=str(form.get("comment") or ""),
        )
        job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
        store = _get_store()
        idempotency_key = _idempotency_key_from_form(form, request)
        operation = f"html-feedback:{job.public_id}"
        existing = _get_idempotent_response(
            operation,
            job.owner_user_id,
            idempotency_key,
            store,
        )
        if existing is not None:
            return _render_html(
                templates,
                "monthly_report_workshop/fragments/feedback.html",
                {
                    "job": existing["job"],
                    "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
                },
            )
        store.record_feedback(
            job.public_id,
            category=payload.category,
            comment=payload.comment,
        )
        job = _get_authorized_job_or_404(job_id, current_user)
        response_context = {"job": _job_view(job)}
        _remember_idempotent_response(
            operation,
            job.owner_user_id,
            idempotency_key,
            response_context,
            store,
        )
    except HTTPException as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc.detail)},
            status_code=exc.status_code,
        )
    except ValueError as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc)},
            status_code=422,
        )
    return _render_html(
        templates,
        "monthly_report_workshop/fragments/feedback.html",
        {"job": _job_view(job), "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME)},
    )


@html_router.post("/monthly-reports/jobs/{job_id}/run", response_class=HTMLResponse)
async def monthly_report_run_action(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    templates = _templates(request)
    form = await request.form()
    try:
        _verify_csrf_token(form, request)
        job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
        store = _get_store()
        run_mode = str(form.get("run_mode") or "") or "stage"
        idempotency_key = _idempotency_key_from_form(form, request)
        operation = f"html-run:{job.public_id}:{run_mode}"
        existing = _get_idempotent_job(
            operation,
            job.owner_user_id,
            idempotency_key,
            store,
        )
        if existing is not None:
            started = existing
        elif run_mode == "mock":
            started = run_monthly_report_job(
                store,
                job.public_id,
                provider=StaticMonthlyReportProvider(_default_html_mock_draft(job)),
                template_path=_DEFAULT_MONTHLY_REPORT_TEMPLATE,
                prompt_version=get_settings().monthly_report_prompt_version,
                model_report="mock/html-ui-model",
                app_version=get_settings().app_version,
            )
            _remember_idempotent_job(operation, job.owner_user_id, idempotency_key, started, store)
        elif run_mode == "openrouter":
            settings = get_settings()
            if not settings.openrouter_api_key:
                raise HTTPException(
                    status_code=503,
                    detail="OPENROUTER_API_KEY is not configured",
                )
            started = run_monthly_report_job(
                store,
                job.public_id,
                provider=OpenRouterMonthlyReportProvider(
                    api_key=settings.openrouter_api_key,
                    model=settings.openrouter_model_report,
                    timeout=settings.openrouter_timeout_seconds,
                    max_tokens=settings.openrouter_max_tokens,
                ),
                template_path=_DEFAULT_MONTHLY_REPORT_TEMPLATE,
                prompt_version=settings.monthly_report_prompt_version,
                model_report=settings.openrouter_model_report,
                app_version=settings.app_version,
            )
            _remember_idempotent_job(operation, job.owner_user_id, idempotency_key, started, store)
        else:
            started = store.start_next(job.public_id)
            _remember_idempotent_job(operation, job.owner_user_id, idempotency_key, started, store)
    except HTTPException as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc.detail)},
            status_code=exc.status_code,
        )
    except StatusTransitionError as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc)},
            status_code=409,
        )
    return _render_html(
        templates,
        "monthly_report_workshop/fragments/status.html",
        {"job": _job_view(started)},
    )


def _default_html_mock_draft(job: MockJob) -> str:
    return "\n\n".join(
        [
            "## 01 基本情報\n"
            f"- 対象月: {job.target_month}\n"
            f"- 対象家庭: {job.household_key}",
            "## 02 塾での様子\n集中して授業に取り組めています。",
            "## 03 授業内容\n今月は既習内容の確認と応用問題に取り組みました。",
            "## 04 課題とアドバイス\n次回までに復習時間を短く区切って継続しましょう。",
            "## 05 学習の進捗\n基礎の定着が進み、説明の精度も上がっています。",
            "## 07 今後の授業計画\n次回は演習量を増やし、解答根拠を言語化します。",
        ]
    )


def _job_metrics(jobs: list[dict[str, Any]]) -> list[dict[str, str]]:
    running = sum(1 for job in jobs if job["status"] == JobStatus.RUNNING)
    queued = sum(1 for job in jobs if job["status"] == JobStatus.QUEUED)
    failed = sum(1 for job in jobs if job["status"] == JobStatus.FAILED)
    return [
        {"label": "実行中", "value": str(running), "tone": "warning"},
        {"label": "待機中", "value": str(queued), "tone": "normal"},
        {"label": "失敗", "value": str(failed), "tone": "error"},
        {"label": "ジョブ", "value": str(len(jobs)), "tone": "normal"},
    ]


@router.post("/jobs")
def create_job(
    request: Request,
    payload: CreateMonthlyReportJobRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    store = _get_store()
    owner_user_id = (
        payload.owner_user_id
        if get_settings().auth_mode == "mock"
        else current_user.user_id
    )
    idempotency_key = _idempotency_key_from_request(request)
    existing = _get_idempotent_job(
        "create_job",
        owner_user_id,
        idempotency_key,
        store,
    )
    if existing is not None:
        return _job_response(existing)
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
    _remember_idempotent_job("create_job", owner_user_id, idempotency_key, job, store)
    return _job_response(job)


@router.get("/jobs")
def list_jobs(current_user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "jobs": [
            _job_response(job)
            for job in _get_read_store(current_user).list_jobs()
            if _can_access_job(job, current_user)
        ]
    }


@router.get("/jobs/{job_id}")
def get_job(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    return _job_response(_get_read_authorized_job_or_404(job_id, current_user))


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
    request: Request,
    payload: CreateMonthlyReportFeedbackRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    store = _get_store()
    job = _get_authorized_job_or_404(job_id, current_user)
    idempotency_key = _idempotency_key_from_request(request)
    operation = f"api-feedback:{job.public_id}"
    existing = _get_idempotent_response(
        operation,
        job.owner_user_id,
        idempotency_key,
        store,
    )
    if existing is not None:
        return existing
    feedback = store.record_feedback(
        job.public_id,
        category=payload.category,
        comment=payload.comment,
    )
    response = {
        "feedback_id": feedback.public_id,
        "job_id": feedback.job_id,
        "category": feedback.category,
        "comment": feedback.comment,
    }
    _remember_idempotent_response(
        operation,
        job.owner_user_id,
        idempotency_key,
        response,
        store,
    )
    return response


@router.post("/jobs/{job_id}/sources")
def record_source(
    job_id: str,
    request: Request,
    payload: CreateMonthlyReportSourceRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    store = _get_store()
    job = _get_authorized_job_or_404(job_id, current_user)
    idempotency_key = _idempotency_key_from_request(request)
    operation = f"api-source:{job.public_id}"
    existing = _get_idempotent_response(
        operation,
        job.owner_user_id,
        idempotency_key,
        store,
    )
    if existing is not None:
        return existing
    response = _source_response(
        store.record_source(
            job.public_id,
            source_type=payload.source_type,
            display_name=payload.display_name,
            snapshot_text=payload.snapshot_text,
            content_hash=payload.content_hash,
        )
    )
    _remember_idempotent_response(
        operation,
        job.owner_user_id,
        idempotency_key,
        response,
        store,
    )
    return response


@router.get("/jobs/{job_id}/sources")
def list_sources(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    job = _get_read_authorized_job_or_404(job_id, current_user)
    store = _get_read_store(current_user)
    return {
        "sources": [
            _source_response(source)
            for source in store.list_sources(job.public_id)
        ]
    }


@router.post("/jobs/{job_id}/fetch-google-sources")
def fetch_google_sources(
    job_id: str,
    request: Request,
    payload: FetchGoogleWorkspaceSourcesRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    job = _get_authorized_job_or_404(job_id, current_user)
    store = _get_store()
    idempotency_key = _idempotency_key_from_request(request)
    operation = f"api-fetch-google-sources:{job.public_id}"
    existing = _get_idempotent_response(
        operation,
        job.owner_user_id,
        idempotency_key,
        store,
    )
    if existing is not None:
        return existing
    try:
        access_token = _resolve_google_workspace_access_token(current_user)
    except GoogleOAuthTokenRefreshError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not access_token:
        raise HTTPException(
            status_code=503,
            detail="Google Workspace access token is not configured",
        )

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
    response = {"sources": [_source_response(source) for source in sources]}
    _remember_idempotent_response(
        operation,
        job.owner_user_id,
        idempotency_key,
        response,
        store,
    )
    return response


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
    request: Request,
    payload: CreateMonthlyReportArtifactRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    store = _get_store()
    job = _get_authorized_job_or_404(job_id, current_user)
    idempotency_key = _idempotency_key_from_request(request)
    operation = f"api-artifact:{job.public_id}"
    existing = _get_idempotent_response(
        operation,
        job.owner_user_id,
        idempotency_key,
        store,
    )
    if existing is not None:
        return existing
    response = _artifact_response(
        store.record_artifact(
            job.public_id,
            artifact_type=payload.artifact_type,
            content=payload.content,
            content_hash=payload.content_hash,
        )
    )
    _remember_idempotent_response(
        operation,
        job.owner_user_id,
        idempotency_key,
        response,
        store,
    )
    return response


@router.get("/jobs/{job_id}/artifacts")
def list_artifacts(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    job = _get_read_authorized_job_or_404(job_id, current_user)
    store = _get_read_store(current_user)
    return {
        "artifacts": [
            _artifact_response(artifact)
            for artifact in store.list_artifacts(job.public_id)
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
    job = _get_read_authorized_job_or_404(job_id, current_user)
    store = _get_read_store(current_user)
    return {
        "validations": [
            _validation_response(validation)
            for validation in store.list_validations(job.public_id)
        ]
    }


@router.get("/jobs/{job_id}/llm-calls")
def list_llm_calls(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    job = _get_read_authorized_job_or_404(job_id, current_user)
    store = _get_read_store(current_user)
    return {
        "llm_calls": [
            _llm_call_response(call)
            for call in store.list_llm_calls(job.public_id)
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
    request: Request,
    payload: RunMonthlyReportMockRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    job = _get_authorized_job_or_404(job_id, current_user)
    store = _get_store()
    idempotency_key = _idempotency_key_from_request(request)
    operation = f"run-mock:{job.public_id}"
    existing = _get_idempotent_response(
        operation,
        job.owner_user_id,
        idempotency_key,
        store,
    )
    if existing is not None:
        return existing
    settings = get_settings()
    job = store.update_reproducibility_meta(
        job.public_id,
        prompt_version=job.prompt_version or settings.monthly_report_prompt_version,
        model_report=job.model_report or settings.openrouter_model_report,
        app_version=job.app_version or settings.app_version,
    )
    try:
        response = _job_response(
            run_monthly_report_job(
                store,
                job.public_id,
                provider=StaticMonthlyReportProvider(payload.content),
                template_path=_DEFAULT_MONTHLY_REPORT_TEMPLATE,
                prompt_version=settings.monthly_report_prompt_version,
                model_report=settings.openrouter_model_report,
                app_version=settings.app_version,
            )
        )
        _remember_idempotent_response(
            operation,
            job.owner_user_id,
            idempotency_key,
            response,
            store,
        )
        return response
    except StatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/run-openrouter")
def run_job_with_openrouter(
    job_id: str,
    request: Request,
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
    idempotency_key = _idempotency_key_from_request(request)
    operation = f"run-openrouter:{job.public_id}"
    existing = _get_idempotent_response(
        operation,
        job.owner_user_id,
        idempotency_key,
        store,
    )
    if existing is not None:
        return existing
    job = store.update_reproducibility_meta(
        job.public_id,
        prompt_version=job.prompt_version or settings.monthly_report_prompt_version,
        model_report=job.model_report or settings.openrouter_model_report,
        app_version=job.app_version or settings.app_version,
    )
    try:
        response = _job_response(
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
                prompt_version=settings.monthly_report_prompt_version,
                model_report=settings.openrouter_model_report,
                app_version=settings.app_version,
            )
        )
        _remember_idempotent_response(
            operation,
            job.owner_user_id,
            idempotency_key,
            response,
            store,
        )
        return response
    except StatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
