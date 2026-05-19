from __future__ import annotations

import base64
from html import escape
import hmac
from hashlib import sha256
import json
import re
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from jinja2 import Environment
from pydantic import BaseModel, Field

from eb_app.auth.dependencies import CurrentUser, get_current_user
from eb_app.auth.supabase_client import create_supabase_user_client
from eb_app.config import get_settings
from eb_app.monthly_reports.diffing import diff_markdown_lines
from eb_app.monthly_reports.jobs import (
    DEFAULT_MOCK_OWNER_USER_ID,
    JobLimitExceeded,
    JobStatus,
    MAX_ACTIVE_JOBS_PER_USER,
    PIPELINE_STAGES,
    MockJob,
    MockJobStore,
    MockArtifact,
    MockFeedback,
    MockSource,
    MockValidation,
    MockLLMCall,
    StatusTransitionError,
)
from eb_app.monthly_reports.cloud_run_jobs import (
    CloudRunJobExecutor,
    CloudRunJobTriggerError,
    MetadataServerAccessTokenProvider,
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
    ProviderCallError,
    StaticMonthlyReportProvider,
    run_monthly_report_job,
)

router = APIRouter()
html_router = APIRouter()

_store = MockJobStore()
_idempotency_lock = threading.Lock()
_idempotency_job_ids: dict[tuple[str, str, str], str] = {}
_idempotency_responses: dict[tuple[str, str, str], dict[str, Any]] = {}
_idempotency_operation_locks: dict[tuple[str, str, str], threading.Lock] = {}
_RUNNING_STALE_WARNING_SECONDS = 30 * 60
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_MONTHLY_REPORT_TEMPLATE = (
    _PROJECT_ROOT
    / "docs"
    / "samples"
    / "monthly-reports"
    / "monthly_pattern_b_content.template.md"
)
_LEGACY_MONTHLY_REPORT_FULL_EDITOR = (
    _PROJECT_ROOT
    / "docs"
    / "samples"
    / "monthly-reports"
    / "tools"
    / "monthly_report_full_editor.html"
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
_CALLER_INTENT_HEADER = "X-EB-Caller-Intent"
_STATE_MUTATION_CALLER_INTENTS = frozenset({"admin", "e2e"})
_DEFAULT_MONTHLY_REPORT_SHEET_RANGES = (
    {
        "sheet_name": "student",
        "display_name": "基本情報 student",
    },
    {
        "sheet_name": "lesson plan",
        "display_name": "学習計画表 lesson plan",
    },
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


class ManualRecoveryFailJobRequest(BaseModel):
    error_message: str | None = None
    note: str | None = None


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


def _caller_intent_from_request(request: Request) -> str | None:
    value = request.headers.get(_CALLER_INTENT_HEADER)
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _require_state_mutation_caller_intent(
    request: Request,
    current_user: CurrentUser,
    *,
    route_label: str,
) -> str:
    if get_settings().auth_mode == "mock":
        return "mock"
    caller_intent = _caller_intent_from_request(request)
    if caller_intent not in _STATE_MUTATION_CALLER_INTENTS:
        allowed = ", ".join(sorted(_STATE_MUTATION_CALLER_INTENTS))
        raise HTTPException(
            status_code=403,
            detail=f"{route_label} requires {_CALLER_INTENT_HEADER}: {allowed}",
        )
    if caller_intent == "admin" and current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="admin caller intent requires admin role",
        )
    return caller_intent


def _require_admin_state_mutation_caller_intent(
    request: Request,
    current_user: CurrentUser,
    *,
    route_label: str,
) -> None:
    caller_intent = _require_state_mutation_caller_intent(
        request,
        current_user,
        route_label=route_label,
    )
    if caller_intent != "admin":
        raise HTTPException(
            status_code=403,
            detail=f"{route_label} requires {_CALLER_INTENT_HEADER}: admin",
        )


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


def _idempotency_operation_lock(
    operation: str,
    owner_user_id: str,
    key: str,
) -> threading.Lock:
    scope = _idempotency_scope(operation, owner_user_id, key)
    with _idempotency_lock:
        lock = _idempotency_operation_locks.get(scope)
        if lock is None:
            lock = threading.Lock()
            _idempotency_operation_locks[scope] = lock
        return lock


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


def _can_tune_monthly_report(current_user: CurrentUser) -> bool:
    return current_user.role == "admin"


def _can_use_service_owned_html_workflow(current_user: CurrentUser) -> bool:
    return get_settings().auth_mode == "mock" or current_user.role == "admin"


def _service_owned_html_workflow_reason(current_user: CurrentUser) -> str:
    if _can_use_service_owned_html_workflow(current_user):
        return ""
    return (
        "通常UIの即時生成（モック生成 / OpenRouter生成）は mock/admin の補助導線です。"
        "通常ユーザーは「生成開始」「取得してレポート生成」で worker へ依頼してください。"
    )


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


def _get_feedback_write_store(
    current_user: CurrentUser,
) -> MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore:
    return _get_rls_read_store(current_user) or _get_store()


def _get_artifact_write_store(
    current_user: CurrentUser,
) -> MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore:
    return _get_rls_read_store(current_user) or _get_store()


def _get_source_write_store(
    current_user: CurrentUser,
) -> MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore:
    return _get_rls_read_store(current_user) or _get_store()


def _get_validation_write_store(
    current_user: CurrentUser,
) -> MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore:
    return _get_rls_read_store(current_user) or _get_store()


def _record_job_audit_log(
    *,
    actor_id: str,
    action: str,
    job: MockJob,
    metadata: dict[str, Any],
) -> None:
    audit_store = _get_store()
    record = getattr(audit_store, "record_audit_log", None)
    if record is None:
        return
    record(
        actor_id=actor_id,
        action=action,
        target_type="monthly_report_job",
        target_id=job.public_id,
        metadata=metadata,
    )


def _list_direct_audit_logs(job_id: str) -> list[Any]:
    audit_store = _get_store()
    list_logs = getattr(audit_store, "list_audit_logs", None)
    if not callable(list_logs):
        return []
    try:
        return list_logs(job_id)
    except KeyError:
        return []


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


def _format_operation_time(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return "-"
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    return str(value)


def _operation_status(label: str, tone: str = "pending") -> dict[str, str]:
    return {"label": label, "tone": tone}


def _operation_log_context(
    job: MockJob,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> dict[str, Any]:
    read_store = store or _get_store()
    audit_logs = _list_direct_audit_logs(job.public_id)
    sources = read_store.list_sources(job.public_id)
    artifacts = read_store.list_artifacts(job.public_id)
    validations = read_store.list_validations(job.public_id)
    llm_calls = read_store.list_llm_calls(job.public_id)
    markdown_artifacts = [
        artifact
        for artifact in artifacts
        if artifact.artifact_type in {"draft_markdown", "final_markdown"}
    ]
    source_summary = [
        artifact for artifact in artifacts if artifact.artifact_type == "source_summary_markdown"
    ]
    worker_request_logs = [
        audit_log
        for audit_log in audit_logs
        if audit_log.action == "monthly_report_worker_owned_workflow_requested"
    ]
    latest_worker_request_at = max(
        (audit_log.created_at for audit_log in worker_request_logs),
        default=None,
    )
    queued_for_worker = (
        job.status == JobStatus.QUEUED and latest_worker_request_at is not None
    )
    latest_source_at = max((source.created_at for source in sources), default=None)
    latest_markdown_at = max((artifact.created_at for artifact in markdown_artifacts), default=None)
    latest_validation_at = max((validation.created_at for validation in validations), default=None)
    latest_llm_at = max((call.created_at for call in llm_calls), default=None)
    steps = [
        {
            "name": "ジョブ作成",
            "state": _operation_status("完了", "done"),
            "time": _format_operation_time(job.created_at),
            "detail": "レポート生成の箱を作成しました。まだソース取得や生成は実行していません。",
        },
        {
            "name": "データソース取得",
            "state": _operation_status("完了", "done")
            if sources
            else _operation_status("未実行", "pending"),
            "time": _format_operation_time(latest_source_at),
            "detail": f"{len(sources)}件のソースを保存済み。"
            if sources
            else "Google Docs / Sheets URL投入、または手入力ソース保存がまだです。",
        },
        {
            "name": "取得内容要約",
            "state": _operation_status("完了", "done")
            if source_summary
            else _operation_status("任意/未実行", "pending"),
            "time": _format_operation_time(source_summary[-1].created_at if source_summary else None),
            "detail": "source_summary_markdown を保存済み。"
            if source_summary
            else "対象・期間・科目のズレ確認用です。生成前に実行できます。",
        },
        {
            "name": "レポート生成",
            "state": (
                _operation_status("完了", "done")
                if markdown_artifacts
                else _operation_status("worker待ち", "running")
                if queued_for_worker
                else _operation_status("処理中", "running")
                if job.status == JobStatus.RUNNING
                else _operation_status("失敗", "error")
                if job.status == JobStatus.FAILED
                else _operation_status("未実行", "pending")
            ),
            "time": _format_operation_time(latest_markdown_at or latest_llm_at or latest_worker_request_at),
            "detail": f"{markdown_artifacts[-1].artifact_type} をレポートビューへ反映済み。"
            if markdown_artifacts
            else "worker が queued job を処理するまで待機中です。進捗パネルを更新してください。"
            if queued_for_worker
            else "OpenRouter生成または「取得してレポート生成」がまだです。",
        },
        {
            "name": "検証",
            "state": _operation_status("完了", "done")
            if validations
            else _operation_status("未実行", "pending"),
            "time": _format_operation_time(latest_validation_at),
            "detail": f"{len(validations)}件の検証結果があります。"
            if validations
            else "レポート生成後に検証結果が表示されます。",
        },
    ]
    events: list[dict[str, str]] = [
        {
            "time": _format_operation_time(job.created_at),
            "kind": "job",
            "label": "ジョブ作成",
            "detail": job.public_id,
        }
    ]
    for source in sources:
        events.append(
            {
                "time": _format_operation_time(source.created_at),
                "kind": "source",
                "label": source.display_name or source.source_type,
                "detail": source.content_hash or "-",
            }
        )
    for artifact in artifacts:
        events.append(
            {
                "time": _format_operation_time(artifact.created_at),
                "kind": "artifact",
                "label": artifact.artifact_type,
                "detail": artifact.content_hash or "-",
            }
        )
    for validation in validations:
        events.append(
            {
                "time": _format_operation_time(validation.created_at),
                "kind": f"validation:{validation.severity}",
                "label": validation.rule_id,
                "detail": validation.message,
            }
        )
    for call in llm_calls:
        token_text = ""
        if call.input_tokens is not None or call.output_tokens is not None:
            token_text = f" input={call.input_tokens or 0} output={call.output_tokens or 0}"
        events.append(
            {
                "time": _format_operation_time(call.created_at),
                "kind": "llm",
                "label": call.prompt_kind,
                "detail": f"{call.provider} {call.resolved_model or call.requested_model or '-'}{token_text}",
            }
        )
    for audit_log in audit_logs:
        if audit_log.action == "monthly_report_worker_owned_workflow_requested":
            mode = str(audit_log.metadata.get("mode") or "stage")
            trigger = str(audit_log.metadata.get("trigger") or "html")
            events.append(
                {
                    "time": _format_operation_time(audit_log.created_at),
                    "kind": "audit",
                    "label": "worker依頼",
                    "detail": f"{trigger} {mode} boundary=worker_owned_workflow",
                }
            )
        elif audit_log.action == "monthly_report_service_owned_workflow_executed":
            mode = str(audit_log.metadata.get("mode") or "stage")
            trigger = str(audit_log.metadata.get("trigger") or "html")
            events.append(
                {
                    "time": _format_operation_time(audit_log.created_at),
                    "kind": "audit",
                    "label": "service workflow",
                    "detail": f"{trigger} {mode} boundary=service_owned_workflow",
                }
            )
        elif audit_log.action == "monthly_report_worker_job_triggered":
            trigger = str(audit_log.metadata.get("trigger") or "html")
            operation_name = str(audit_log.metadata.get("operation_name") or "-")
            events.append(
                {
                    "time": _format_operation_time(audit_log.created_at),
                    "kind": "audit",
                    "label": "worker trigger",
                    "detail": f"{trigger} {operation_name}",
                }
            )
    events.sort(key=lambda event: event["time"])
    return {"job": _job_view(job, read_store), "steps": steps, "events": events}


def _job_view(
    job: MockJob,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> dict[str, Any]:
    read_store = store or _get_store()
    audit_logs = _list_direct_audit_logs(job.public_id)
    can_cancel = job.status in {JobStatus.QUEUED, JobStatus.RUNNING}
    sources = read_store.list_sources(job.public_id)
    artifacts = read_store.list_artifacts(job.public_id)
    validations = read_store.list_validations(job.public_id)
    latest_artifact = _latest_preview_artifact(job, read_store)
    distribution_artifact = _latest_distribution_artifact(job, read_store)
    approval = _latest_approval_artifact(job, read_store)
    export_artifact = _latest_export_artifact(job, read_store)
    validation_error_count = sum(
        1 for validation in validations if validation.severity == "error"
    )
    latest_worker_request_at = max(
        (
            audit_log.created_at
            for audit_log in audit_logs
            if audit_log.action == "monthly_report_worker_owned_workflow_requested"
        ),
        default=None,
    )
    latest_service_execution_at = max(
        (
            audit_log.created_at
            for audit_log in audit_logs
            if audit_log.action == "monthly_report_service_owned_workflow_executed"
        ),
        default=None,
    )
    queued_for_worker = (
        job.status == JobStatus.QUEUED
        and latest_worker_request_at is not None
        and (
            latest_service_execution_at is None
            or latest_worker_request_at >= latest_service_execution_at
        )
    )
    can_run = job.status == JobStatus.QUEUED and not queued_for_worker
    if queued_for_worker:
        next_action_label = "worker進捗を確認"
        next_action_anchor = "#status-panel"
    elif job.status == JobStatus.QUEUED:
        next_action_label = "ソース確認後、生成開始"
        next_action_anchor = "#sources-panel"
    elif job.status == JobStatus.RUNNING:
        next_action_label = "進捗を確認"
        next_action_anchor = "#status-panel"
    elif job.status == JobStatus.FAILED:
        next_action_label = "エラー確認・再生成"
        next_action_anchor = "#status-panel"
    elif job.status == JobStatus.SUCCEEDED and validation_error_count:
        next_action_label = "検証エラーを修正"
        next_action_anchor = "#validation-panel"
    elif job.status == JobStatus.SUCCEEDED and distribution_artifact is None:
        next_action_label = "生成物を確認"
        next_action_anchor = "#preview-panel"
    elif job.status == JobStatus.SUCCEEDED and not _is_current_approval(
        approval, distribution_artifact
    ):
        next_action_label = "プレビュー確認後に承認"
        next_action_anchor = "#approval-panel"
    elif job.status == JobStatus.SUCCEEDED and export_artifact is None:
        next_action_label = "HTMLエクスポート"
        next_action_anchor = "#export-panel"
    elif job.status == JobStatus.SUCCEEDED:
        next_action_label = "完了"
        next_action_anchor = "#export-panel"
    else:
        next_action_label = "再生成"
        next_action_anchor = "#status-panel"
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
        "next_action_label": next_action_label,
        "next_action_anchor": next_action_anchor,
        "source_count": len(sources),
        "artifact_count": len(artifacts),
        "validation_count": len(validations),
        "validation_error_count": validation_error_count,
        "latest_artifact_type": latest_artifact["artifact_type"] if latest_artifact else None,
        "latest_artifact_hash": latest_artifact["content_hash"] if latest_artifact else None,
        "distribution_artifact_type": (
            distribution_artifact["artifact_type"] if distribution_artifact else None
        ),
        "distribution_artifact_hash": (
            distribution_artifact["content_hash"] if distribution_artifact else None
        ),
        "approval_current": _is_current_approval(approval, distribution_artifact),
        "has_export": export_artifact is not None,
        "can_run": can_run,
        "queued_for_worker": queued_for_worker,
        "queued_for_worker_message": (
            "worker へ生成を依頼済みです。queued job を worker が claim するまでお待ちください。"
            if queued_for_worker
            else ""
        ),
        "run_disabled_reason": (
            ""
            if can_run
            else (
                "worker へ生成を依頼済みです。処理開始までは再送せず、進捗を確認してください。"
                if queued_for_worker
                else "queued のジョブだけ生成開始できます"
            )
        ),
        "can_cancel": can_cancel,
        "cancel_disabled_reason": (
            "" if can_cancel else "queued / running のジョブだけキャンセルできます"
        ),
        "stages": _stage_views(job),
        **_running_recovery_context(job),
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
    for artifact_type in ("final_markdown", "draft_markdown", "html"):
        typed_artifacts = [
            artifact for artifact in artifacts if artifact.artifact_type == artifact_type
        ]
        if typed_artifacts:
            return _artifact_view(typed_artifacts[-1])
    return None


def _latest_markdown_artifact(
    job: MockJob,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> dict[str, Any] | None:
    read_store = store or _get_store()
    artifacts = [
        artifact
        for artifact in read_store.list_artifacts(job.public_id)
        if artifact.artifact_type in {"draft_markdown", "final_markdown"}
    ]
    if not artifacts:
        return None
    for artifact_type in ("final_markdown", "draft_markdown"):
        typed_artifacts = [
            artifact for artifact in artifacts if artifact.artifact_type == artifact_type
        ]
        if typed_artifacts:
            return _artifact_view(typed_artifacts[-1])
    return None


def _latest_artifact_by_type(
    job: MockJob,
    artifact_type: str,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> dict[str, Any] | None:
    read_store = store or _get_store()
    artifacts = [
        artifact
        for artifact in read_store.list_artifacts(job.public_id)
        if artifact.artifact_type == artifact_type
    ]
    if not artifacts:
        return None
    return _artifact_view(artifacts[-1])


def _diff_context(
    job: MockJob,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> dict[str, Any]:
    read_store = store or _get_store()
    draft = _latest_artifact_by_type(job, "draft_markdown", read_store)
    final = _latest_artifact_by_type(job, "final_markdown", read_store)
    rows = []
    if draft and final:
        rows = diff_markdown_lines(draft["content"], final["content"])
    return {
        "job": _job_view(job, read_store),
        "draft_artifact": draft,
        "final_artifact": final,
        "diff_rows": rows,
        "added_count": sum(1 for row in rows if row.kind == "added"),
        "removed_count": sum(1 for row in rows if row.kind == "removed"),
    }


def _rerun_diff_context(
    base_job: MockJob,
    compare_job: MockJob | None,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> dict[str, Any]:
    read_store = store or _get_store()
    base_artifact = _latest_markdown_artifact(base_job, read_store)
    compare_artifact = (
        _latest_markdown_artifact(compare_job, read_store) if compare_job else None
    )
    rows = []
    if base_artifact and compare_artifact:
        rows = diff_markdown_lines(base_artifact["content"], compare_artifact["content"])
    return {
        "base_job": _job_view(base_job, read_store),
        "compare_job": _job_view(compare_job, read_store) if compare_job else None,
        "base_artifact": base_artifact,
        "compare_artifact": compare_artifact,
        "diff_rows": rows,
        "added_count": sum(1 for row in rows if row.kind == "added"),
        "removed_count": sum(1 for row in rows if row.kind == "removed"),
        "compare_candidates": _rerun_compare_candidates(base_job, read_store),
    }


def _rerun_comparison_rows(base_job: MockJob, compare_job: MockJob | None) -> list[dict[str, str]]:
    fields = (
        ("prompt_version", base_job.prompt_version, compare_job.prompt_version if compare_job else None),
        ("template_key", base_job.template_key, compare_job.template_key if compare_job else None),
        ("template_hash", base_job.template_hash, compare_job.template_hash if compare_job else None),
        ("model_report", base_job.model_report, compare_job.model_report if compare_job else None),
        ("model_light", base_job.model_light, compare_job.model_light if compare_job else None),
        (
            "resolved_model_report",
            base_job.resolved_model_report,
            compare_job.resolved_model_report if compare_job else None,
        ),
        (
            "source_bundle_hash",
            base_job.source_bundle_hash,
            compare_job.source_bundle_hash if compare_job else None,
        ),
        ("app_version", base_job.app_version, compare_job.app_version if compare_job else None),
        (
            "prompt_scope_notes",
            base_job.prompt_scope_notes,
            compare_job.prompt_scope_notes if compare_job else None,
        ),
    )
    return [
        {
            "field": field,
            "base": base or "-",
            "compare": compare or "-",
            "state": "same" if (base or "") == (compare or "") else "changed",
        }
        for field, base, compare in fields
    ]


def _rerun_compare_candidates(
    base_job: MockJob,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> list[dict[str, str]]:
    read_store = store or _get_store()
    candidates = [
        job
        for job in read_store.list_jobs()
        if job.public_id != base_job.public_id
        and job.owner_user_id == base_job.owner_user_id
        and job.household_key == base_job.household_key
    ]
    return [
        {
            "job_id": job.public_id,
            "label": " / ".join(
                part
                for part in (
                    job.public_id,
                    job.status.value if isinstance(job.status, JobStatus) else str(job.status),
                    job.prompt_version,
                    job.model_report,
                )
                if part
            ),
        }
        for job in candidates[:10]
    ]


def _ensure_rerun_compare_job(base_job: MockJob, compare_job: MockJob) -> None:
    if compare_job.public_id == base_job.public_id:
        raise HTTPException(status_code=422, detail="比較先には別ジョブを指定してください")
    if (
        compare_job.owner_user_id != base_job.owner_user_id
        or compare_job.household_key != base_job.household_key
    ):
        raise HTTPException(
            status_code=422,
            detail="同一ユーザー・同一世帯のジョブだけ比較できます",
        )


def _running_recovery_context(job: MockJob) -> dict[str, str | bool]:
    if job.status != JobStatus.RUNNING:
        return {
            "show_running_recovery": False,
            "running_recovery_tone": "info",
            "running_recovery_message": "",
            "running_recovery_detail": "",
        }
    claimed_at = job.worker_last_claimed_at
    is_stale = False
    if claimed_at is not None:
        if claimed_at.tzinfo is None:
            claimed_at = claimed_at.replace(tzinfo=timezone.utc)
        is_stale = (
            datetime.now(timezone.utc) - claimed_at
        ).total_seconds() >= _RUNNING_STALE_WARNING_SECONDS
    if is_stale and job.current_stage not in {"fetch_sources", None}:
        return {
            "show_running_recovery": True,
            "running_recovery_tone": "warning",
            "running_recovery_message": "長時間更新がありません",
            "running_recovery_detail": (
                "ページ再読み込み後も状態は復元されます。後段stageの自動再claimは抑止しているため、"
                "worker runbookで手動回復対象か確認してください。"
            ),
        }
    return {
        "show_running_recovery": True,
        "running_recovery_tone": "info",
        "running_recovery_message": "処理中です",
        "running_recovery_detail": (
            "ページを閉じても処理は継続します。この進捗パネルは自動更新され、再読み込み後も現在状態を復元します。"
        ),
    }


def _latest_distribution_artifact(
    job: MockJob,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> dict[str, Any] | None:
    read_store = store or _get_store()
    artifacts = [
        artifact
        for artifact in read_store.list_artifacts(job.public_id)
        if artifact.artifact_type in {"draft_markdown", "final_markdown"}
    ]
    if not artifacts:
        return None
    final_artifacts = [
        artifact for artifact in artifacts if artifact.artifact_type == "final_markdown"
    ]
    return _artifact_view((final_artifacts or artifacts)[-1])


def _latest_export_artifact(
    job: MockJob,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> dict[str, Any] | None:
    read_store = store or _get_store()
    artifacts = [
        artifact
        for artifact in read_store.list_artifacts(job.public_id)
        if artifact.artifact_type == "export_html"
    ]
    if not artifacts:
        return None
    return _artifact_view(artifacts[-1])


def _latest_distribution_package_artifact(
    job: MockJob,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> dict[str, Any] | None:
    read_store = store or _get_store()
    artifacts = [
        artifact
        for artifact in read_store.list_artifacts(job.public_id)
        if artifact.artifact_type == "distribution_package"
    ]
    if not artifacts:
        return None
    package = _artifact_view(artifacts[-1])
    try:
        payload = json.loads(package["content"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    package["export_artifact_hash"] = payload.get("export_artifact_hash")
    package["distribution_status"] = payload.get("status")
    return package


def _latest_approval_artifact(
    job: MockJob,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> dict[str, Any] | None:
    read_store = store or _get_store()
    artifacts = [
        artifact
        for artifact in read_store.list_artifacts(job.public_id)
        if artifact.artifact_type == "approval"
    ]
    if not artifacts:
        return None
    approval = _artifact_view(artifacts[-1])
    try:
        payload = json.loads(approval["content"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    approval["approved_artifact_hash"] = payload.get("artifact_hash")
    approval["approval_comment"] = payload.get("comment") or ""
    return approval


def _is_current_approval(
    approval: dict[str, Any] | None,
    artifact: dict[str, Any] | None,
) -> bool:
    if approval is None or artifact is None:
        return False
    return approval.get("approved_artifact_hash") == artifact.get("content_hash")


def _approval_context(
    job: MockJob,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> dict[str, Any]:
    read_store = store or _get_store()
    artifact = _latest_distribution_artifact(job, read_store)
    approval = _latest_approval_artifact(job, read_store)
    validations = _validation_views(job, read_store)
    error_validations = [
        validation for validation in validations if validation["severity"] == "error"
    ]
    blockers: list[str] = []
    if job.status != JobStatus.SUCCEEDED:
        blockers.append("生成が完了していません")
    if artifact is None:
        blockers.append("配布面artifactがありません")
    if error_validations:
        blockers.append("validation errorが残っています")
    return {
        "job": _job_view(job),
        "artifact": artifact,
        "validations": validations,
        "blockers": blockers,
        "can_approve": not blockers,
        "approval": approval,
        "approval_current": _is_current_approval(approval, artifact),
    }


def _export_context(
    job: MockJob,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> dict[str, Any]:
    read_store = store or _get_store()
    approval = _approval_context(job, read_store)
    blockers = list(approval["blockers"])
    if approval["approval"] is not None and not approval["approval_current"]:
        blockers.append("承認後に配布面artifactが更新されています")
    elif not approval["approval_current"]:
        blockers.append("人間承認がまだありません")
    return {
        **approval,
        "export_artifact": _latest_export_artifact(job, read_store),
        "export_blockers": blockers,
        "can_export": not blockers,
    }


def _html_source_context(
    job: MockJob,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> dict[str, Any]:
    export_artifact = _latest_export_artifact(job, store)
    blockers: list[str] = []
    if export_artifact is None:
        blockers.append("HTML export artifactがまだありません")
    return {
        "job": _job_view(job),
        "export_artifact": export_artifact,
        "html_source_blockers": blockers,
        "can_edit_html_source": not blockers,
    }


def _distribution_context(
    job: MockJob,
    store: MockJobStore | PostgresJobStore | SupabaseMonthlyReportReadStore | None = None,
) -> dict[str, Any]:
    read_store = store or _get_store()
    export = _export_context(job, read_store)
    export_artifact = export["export_artifact"]
    blockers = list(export["export_blockers"])
    if export_artifact is None:
        blockers.append("HTML export artifactがまだありません")
    return {
        **export,
        "distribution_package": _latest_distribution_package_artifact(job, read_store),
        "distribution_blockers": blockers,
        "can_prepare_distribution": not blockers,
    }


def _export_download_filename(job: MockJob) -> str:
    month = re.sub(r"[^0-9A-Za-z_-]+", "-", job.target_month).strip("-") or "monthly"
    return f"monthly-report-{month}-{job.public_id}.html"


def _hash_text(text: str) -> str:
    return f"sha256:{sha256(text.encode('utf-8')).hexdigest()}"


def _markdown_to_export_html(markdown: str) -> str:
    lines = markdown.splitlines()
    body: list[str] = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                body.append("</ul>")
                in_list = False
            continue
        if stripped.startswith("## "):
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append(f"<h2>{escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append(f"<h1>{escape(stripped[2:])}</h1>")
        elif stripped.startswith("- "):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{escape(stripped[2:])}</li>")
        else:
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append(f"<p>{escape(stripped)}</p>")
    if in_list:
        body.append("</ul>")
    return "<article class=\"monthly-report-export\">\n" + "\n".join(body) + "\n</article>"


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


def _source_summary_messages(sources: list[MockSource]) -> list[dict[str, str]]:
    source_blocks = []
    for index, source in enumerate(sources, start=1):
        snapshot = (source.snapshot_text or "").strip()
        if len(snapshot) > 5000:
            snapshot = snapshot[:5000] + "\n...[truncated]"
        source_blocks.append(
            "\n".join(
                [
                    f"### source {index}: {source.display_name or source.source_type}",
                    f"- type: {source.source_type}",
                    f"- hash: {source.content_hash or '-'}",
                    "```text",
                    snapshot,
                    "```",
                ]
            )
        )
    return [
        {
            "role": "system",
            "content": (
                "あなたは月次レポート工房のソース確認アシスタントです。"
                "Google Docsの文字起こし、Google Sheetsのstudent/lesson planなどの取得内容を、"
                "生成前に人間が取り違えを見つけられるように短く要約します。"
                "本文にない事実は補わず、対象生徒・科目・期間・不足/ズレの可能性を明示してください。"
            ),
        },
        {
            "role": "user",
            "content": (
                "以下の取得ソースを確認し、Markdownで出力してください。\n"
                "必須見出し:\n"
                "## 取得内容サマリー\n"
                "## 対象・期間・科目の確認\n"
                "## ズレ/不足の可能性\n\n"
                + "\n\n".join(source_blocks)
            ),
        },
    ]


def _nonempty_lines(value: str | None) -> list[str]:
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


def _quote_google_sheet_name(sheet_name: str) -> str:
    stripped = sheet_name.strip()
    if not stripped:
        raise HTTPException(status_code=422, detail="Google Sheet name is required")
    if stripped.startswith("'") and stripped.endswith("'"):
        return stripped
    if re.fullmatch(r"[A-Za-z0-9_]+", stripped):
        return stripped
    return "'" + stripped.replace("'", "''") + "'"


def _default_monthly_report_sheet_ranges(
    spreadsheet_id: str,
    *,
    student_sheet_name: str | None = None,
    lesson_plan_sheet_name: str | None = None,
) -> list[GoogleSheetRangeRequest]:
    sheet_names = [
        student_sheet_name or _DEFAULT_MONTHLY_REPORT_SHEET_RANGES[0]["sheet_name"],
        lesson_plan_sheet_name or _DEFAULT_MONTHLY_REPORT_SHEET_RANGES[1]["sheet_name"],
    ]
    display_prefixes = ["基本情報", "学習計画表"]
    return [
        GoogleSheetRangeRequest(
            spreadsheet_id=spreadsheet_id,
            range_name=_quote_google_sheet_name(sheet_name),
            display_name=f"{display_prefix} {sheet_name}",
        )
        for display_prefix, sheet_name in zip(display_prefixes, sheet_names)
    ]


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
    can_tune = _can_tune_monthly_report(current_user)
    payload = CreateMonthlyReportJobRequest(
        target_month=str(form.get("target_month") or ""),
        household_key=str(form.get("household_key") or ""),
        owner_user_id=str(form.get("owner_user_id") or DEFAULT_MOCK_OWNER_USER_ID),
        template_key=str(form.get("template_key") or "") or None,
        prompt_version=(str(form.get("prompt_version") or "") or None) if can_tune else None,
        model_report=(str(form.get("model_report") or "") or None) if can_tune else None,
        model_light=(str(form.get("model_light") or "") or None) if can_tune else None,
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
        model_report=payload.model_report,
        model_light=payload.model_light,
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
    filtered_jobs, filters = _filter_job_views(jobs, request)
    return _render_html(
        _templates(request),
        "monthly_report_workshop/jobs.html",
        {
            "page_title": "レポート工房",
            "current_user": current_user,
            "jobs": filtered_jobs,
            "metrics": _job_metrics(jobs),
            "filters": filters,
        },
    )


@html_router.get("/monthly-reports/jobs", response_class=HTMLResponse)
def monthly_report_jobs_page(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    read_store = _get_read_store(current_user)
    jobs = [
        _job_view(job, read_store)
        for job in read_store.list_jobs()
        if _can_access_job(job, current_user)
    ]
    filtered_jobs, filters = _filter_job_views(jobs, request)
    return _render_html(
        _templates(request),
        "monthly_report_workshop/jobs.html",
        {
            "page_title": "レポート工房",
            "current_user": current_user,
            "jobs": filtered_jobs,
            "metrics": _job_metrics(jobs),
            "filters": filters,
        },
    )


@html_router.get("/monthly-reports/jobs/new", response_class=HTMLResponse)
def monthly_report_new_job_page(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    csrf_token = _csrf_token_for_request(request)
    settings = get_settings()
    response = _render_html(
        _templates(request),
        "monthly_report_workshop/new.html",
        {
            "page_title": "新規ジョブ作成",
            "current_user": current_user,
            "can_tune": _can_tune_monthly_report(current_user),
            "target_month": "2026-04",
            "templates": ["pattern_b"],
            "default_prompt_version": settings.monthly_report_prompt_version,
            "default_model_report": settings.openrouter_model_report,
            "default_model_light": settings.openrouter_model_light,
            "csrf_token": csrf_token,
            "idempotency_key": _new_idempotency_key(),
        },
    )
    _set_csrf_cookie(response, request, csrf_token)
    return response


@html_router.get("/monthly-reports/legacy-full-editor", response_class=HTMLResponse)
def monthly_report_legacy_full_editor(
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    if not _LEGACY_MONTHLY_REPORT_FULL_EDITOR.exists():
        raise HTTPException(status_code=404, detail="legacy full editor is not available")
    return HTMLResponse(
        _LEGACY_MONTHLY_REPORT_FULL_EDITOR.read_text(encoding="utf-8")
    )


@html_router.get("/monthly-reports/jobs/{job_id}/legacy-full-editor", response_class=HTMLResponse)
def monthly_report_legacy_full_editor_bridge(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    job = _get_read_authorized_job_or_404(job_id, current_user)
    export_artifact = _latest_export_artifact(job)
    if export_artifact is None:
        raise HTTPException(status_code=404, detail="export_html artifact is not available")
    html_b64 = base64.b64encode(str(export_artifact["content"] or "").encode("utf-8")).decode(
        "ascii"
    )
    meta = {
        "job_id": job.public_id,
        "artifact_id": export_artifact["artifact_id"],
        "artifact_hash": export_artifact["content_hash"],
    }
    meta_b64 = base64.b64encode(json.dumps(meta, ensure_ascii=False).encode("utf-8")).decode(
        "ascii"
    )
    return HTMLResponse(
        f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>既存全文エディタへ接続</title>
</head>
<body>
  <p>既存全文エディタへ最新HTML exportを読み込んでいます。</p>
  <script>
    const decoder = new TextDecoder();
    const htmlBytes = Uint8Array.from(atob("{html_b64}"), c => c.charCodeAt(0));
    const metaBytes = Uint8Array.from(atob("{meta_b64}"), c => c.charCodeAt(0));
    localStorage.setItem("ea_monthly_report_full_editor_draft_html_v4", decoder.decode(htmlBytes));
    localStorage.setItem("ea_monthly_report_full_editor_draft_meta_v4", decoder.decode(metaBytes));
    location.replace('/monthly-reports/legacy-full-editor');
  </script>
</body>
</html>"""
    )


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
    read_store = _get_read_store(current_user)
    active_count = 0
    if _get_rls_read_store(current_user) is None:
        active_count = _get_store().count_active_jobs(job.owner_user_id)
    can_rerun = job.status not in {
        JobStatus.QUEUED,
        JobStatus.RUNNING,
        JobStatus.CANCEL_REQUESTED,
    } and active_count < MAX_ACTIVE_JOBS_PER_USER
    csrf_token = _csrf_token_for_request(request)
    response = _render_html(
        _templates(request),
        "monthly_report_workshop/detail.html",
        {
            "page_title": "ジョブ詳細",
            "current_user": current_user,
            "can_tune": _can_tune_monthly_report(current_user),
            "service_owned_workflow_allowed": _can_use_service_owned_html_workflow(current_user),
            "service_owned_workflow_reason": _service_owned_html_workflow_reason(current_user),
            "job": _job_view(job, read_store),
            "latest_preview_artifact": _latest_preview_artifact(job, read_store),
            "csrf_token": csrf_token,
            "can_rerun": can_rerun,
            "rerun_disabled_reason": (
                ""
                if can_rerun
                else (
                    "active job が上限に達しています"
                    if active_count >= MAX_ACTIVE_JOBS_PER_USER
                    else "実行中/待機中のジョブは再生成できません"
                )
            ),
            "run_idempotency_key": _new_idempotency_key(),
            "rerun_idempotency_key": _new_idempotency_key(),
            "cancel_idempotency_key": _new_idempotency_key(),
            "source_idempotency_key": _new_idempotency_key(),
            "source_summary_idempotency_key": _new_idempotency_key(),
            "google_sources_idempotency_key": _new_idempotency_key(),
            "edited_markdown_idempotency_key": _new_idempotency_key(),
            "feedback_idempotency_key": _new_idempotency_key(),
            "approval_idempotency_key": _new_idempotency_key(),
            "export_idempotency_key": _new_idempotency_key(),
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
    store = _get_read_store(current_user)
    job = _get_read_authorized_job_or_404(job_id, current_user)
    return _render_html(
        _templates(request),
        "monthly_report_workshop/fragments/status.html",
        {"job": _job_view(job, store)},
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
            "job": _job_view(job, store),
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
            "job": _job_view(job, store),
            "sources": _source_views(job, store),
            "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
        },
    )


@html_router.post(
    "/monthly-reports/jobs/{job_id}/fragments/source-summary",
    response_class=HTMLResponse,
)
async def monthly_report_source_summary_fragment(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    templates = _templates(request)
    form = await request.form()
    try:
        _verify_csrf_token(form, request)
        job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
        idempotency_key = _idempotency_key_from_form(form, request)
        if idempotency_key is None:
            raise HTTPException(status_code=422, detail="idempotency_key is required")
        operation = f"html-source-summary:{job.public_id}"
        read_store = _get_read_store(current_user)
        artifact_store = _get_artifact_write_store(current_user)
        direct_store = _get_store()
        action_lock = _idempotency_operation_lock(
            operation,
            job.owner_user_id,
            idempotency_key,
        )
        with action_lock:
            existing = _get_idempotent_response(
                operation,
                job.owner_user_id,
                idempotency_key,
                direct_store,
            )
            if existing is not None:
                return _render_html(
                    templates,
                    "monthly_report_workshop/fragments/source_summary.html",
                    existing,
                )
            sources = [
                source
                for source in read_store.list_sources(job.public_id)
                if (source.snapshot_text or "").strip()
            ]
            if not sources:
                raise HTTPException(status_code=422, detail="source is required before summary")
            settings = get_settings()
            if not settings.openrouter_api_key:
                raise HTTPException(
                    status_code=503,
                    detail="OPENROUTER_API_KEY is not configured",
                )
            messages = _source_summary_messages(sources)
            completion = OpenRouterMonthlyReportProvider(
                api_key=settings.openrouter_api_key,
                model=settings.openrouter_model_light,
                timeout=settings.openrouter_timeout_seconds,
                max_tokens=settings.openrouter_max_tokens,
            ).complete(messages=messages, model=settings.openrouter_model_light)
            artifact = artifact_store.record_artifact(
                job.public_id,
                artifact_type="source_summary_markdown",
                content=completion.content,
                content_hash=_hash_text(completion.content),
            )
            direct_store.record_llm_call(
                job.public_id,
                prompt_kind="source_summary",
                provider="openrouter",
                requested_model=settings.openrouter_model_light,
                resolved_model=completion.resolved_model,
                prompt_version=settings.monthly_report_prompt_version,
                request_hash=_hash_text(str(messages)),
                response_hash=_hash_text(completion.content),
                input_tokens=completion.input_tokens,
                output_tokens=completion.output_tokens,
                finish_reason=completion.finish_reason,
            )
            response_context = {
                "job": _job_view(job),
                "artifact": _artifact_view(artifact),
            }
            _remember_idempotent_response(
                operation,
                job.owner_user_id,
                idempotency_key,
                response_context,
                direct_store,
            )
    except HTTPException as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc.detail)},
            status_code=exc.status_code,
        )
    except (ProviderCallError, ValueError):
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": "source summary failed"},
            status_code=502,
        )
    return _render_html(
        templates,
        "monthly_report_workshop/fragments/source_summary.html",
        response_context,
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
            "job": _job_view(job, store),
            "validations": _validation_views(job, store),
        },
    )


@html_router.get("/monthly-reports/jobs/{job_id}/fragments/operation-log", response_class=HTMLResponse)
def monthly_report_operation_log_fragment(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    store = _get_read_store(current_user)
    job = _get_read_authorized_job_or_404(job_id, current_user)
    return _render_html(
        _templates(request),
        "monthly_report_workshop/fragments/operation_log.html",
        _operation_log_context(job, store),
    )


@html_router.get("/monthly-reports/jobs/{job_id}/fragments/diff", response_class=HTMLResponse)
def monthly_report_diff_fragment(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    store = _get_read_store(current_user)
    job = _get_read_authorized_job_or_404(job_id, current_user)
    return _render_html(
        _templates(request),
        "monthly_report_workshop/fragments/diff.html",
        _diff_context(job, store),
    )


@html_router.post("/monthly-reports/jobs/{job_id}/fragments/sheet-selector", response_class=HTMLResponse)
async def monthly_report_sheet_selector_fragment(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    templates = _templates(request)
    form = await request.form()
    try:
        _verify_csrf_token(form, request)
        _get_read_authorized_job_or_404(job_id, current_user)
        spreadsheet_id = str(form.get("spreadsheet_id") or "")
        if not spreadsheet_id.strip():
            raise HTTPException(status_code=422, detail="Google Sheets ID is required")
        access_token = _resolve_google_workspace_access_token(current_user)
        if not access_token:
            raise HTTPException(
                status_code=503,
                detail="Google Workspace access token is not configured",
            )
        sheet_names = GoogleWorkspaceClient(access_token=access_token).fetch_sheet_titles(
            spreadsheet_id=spreadsheet_id,
        )
    except HTTPException as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc.detail)},
            status_code=exc.status_code,
        )
    except (GoogleOAuthTokenRefreshError, GoogleWorkspaceFetchError, ValueError):
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": "Google Sheets names fetch failed"},
            status_code=502,
        )
    return _render_html(
        templates,
        "monthly_report_workshop/fragments/sheet_selector.html",
        {
            "sheet_names": sheet_names,
            "student_default": "student",
            "lesson_plan_default": "lesson plan",
        },
    )


@html_router.get(
    "/monthly-reports/jobs/{job_id}/fragments/rerun-comparison",
    response_class=HTMLResponse,
)
def monthly_report_rerun_comparison_fragment(
    job_id: str,
    request: Request,
    compare_job_id: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    templates = _templates(request)
    read_store = _get_read_store(current_user)
    base_job = _get_read_authorized_job_or_404(job_id, current_user)
    compare_job = None
    if compare_job_id:
        compare_job = _get_read_authorized_job_or_404(compare_job_id, current_user)
        try:
            _ensure_rerun_compare_job(base_job, compare_job)
        except HTTPException as exc:
            return _render_html(
                templates,
                "monthly_report_workshop/fragments/alert.html",
                {"tone": "error", "message": str(exc.detail)},
                status_code=exc.status_code,
            )
    return _render_html(
        templates,
        "monthly_report_workshop/fragments/rerun_comparison.html",
        {
            "base_job": _job_view(base_job),
            "compare_job": _job_view(compare_job) if compare_job else None,
            "compare_job_id": compare_job_id or "",
            "compare_candidates": _rerun_compare_candidates(base_job, read_store),
            "comparison_rows": _rerun_comparison_rows(base_job, compare_job),
        },
    )


@html_router.get(
    "/monthly-reports/jobs/{job_id}/fragments/rerun-diff",
    response_class=HTMLResponse,
)
def monthly_report_rerun_diff_fragment(
    job_id: str,
    request: Request,
    compare_job_id: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    templates = _templates(request)
    read_store = _get_read_store(current_user)
    base_job = _get_read_authorized_job_or_404(job_id, current_user)
    compare_job = None
    if compare_job_id:
        compare_job = _get_read_authorized_job_or_404(compare_job_id, current_user)
        try:
            _ensure_rerun_compare_job(base_job, compare_job)
        except HTTPException as exc:
            return _render_html(
                templates,
                "monthly_report_workshop/fragments/alert.html",
                {"tone": "error", "message": str(exc.detail)},
                status_code=exc.status_code,
            )
    return _render_html(
        templates,
        "monthly_report_workshop/fragments/rerun_diff.html",
        _rerun_diff_context(base_job, compare_job, read_store),
    )


@html_router.get("/monthly-reports/jobs/{job_id}/fragments/approval", response_class=HTMLResponse)
def monthly_report_approval_fragment(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    store = _get_read_store(current_user)
    job = _get_read_authorized_job_or_404(job_id, current_user)
    return _render_html(
        _templates(request),
        "monthly_report_workshop/fragments/approval.html",
        {
            **_approval_context(job, store),
            "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
            "approval_idempotency_key": _new_idempotency_key(),
        },
    )


@html_router.get("/monthly-reports/jobs/{job_id}/fragments/export", response_class=HTMLResponse)
def monthly_report_export_fragment(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    store = _get_read_store(current_user)
    job = _get_read_authorized_job_or_404(job_id, current_user)
    return _render_html(
        _templates(request),
        "monthly_report_workshop/fragments/export.html",
        {
            **_export_context(job, store),
            "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
            "export_idempotency_key": _new_idempotency_key(),
        },
    )


@html_router.get("/monthly-reports/jobs/{job_id}/fragments/html-source", response_class=HTMLResponse)
def monthly_report_html_source_fragment(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    store = _get_read_store(current_user)
    job = _get_read_authorized_job_or_404(job_id, current_user)
    return _render_html(
        _templates(request),
        "monthly_report_workshop/fragments/html_source.html",
        {
            **_html_source_context(job, store),
            "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
            "html_source_idempotency_key": _new_idempotency_key(),
        },
    )


@html_router.get("/monthly-reports/jobs/{job_id}/fragments/distribution", response_class=HTMLResponse)
def monthly_report_distribution_fragment(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    store = _get_read_store(current_user)
    job = _get_read_authorized_job_or_404(job_id, current_user)
    return _render_html(
        _templates(request),
        "monthly_report_workshop/fragments/distribution.html",
        {
            **_distribution_context(job, store),
            "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
            "distribution_idempotency_key": _new_idempotency_key(),
        },
    )


@html_router.get("/monthly-reports/jobs/{job_id}/download/export-html")
def monthly_report_export_html_download(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    store = _get_read_store(current_user)
    job = _get_read_authorized_job_or_404(job_id, current_user)
    export_artifact = _latest_export_artifact(job, store)
    if export_artifact is None:
        raise HTTPException(status_code=404, detail="HTML export artifact not found")
    return Response(
        str(export_artifact["content"] or ""),
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{_export_download_filename(job)}"'
            )
        },
    )


@html_router.post("/monthly-reports/jobs/{job_id}/fragments/approval", response_class=HTMLResponse)
async def monthly_report_approval_action(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    templates = _templates(request)
    form = await request.form()
    try:
        _verify_csrf_token(form, request)
        job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
        store = _get_artifact_write_store(current_user)
        idempotency_key = _idempotency_key_from_form(form, request)
        if idempotency_key is None:
            raise HTTPException(status_code=422, detail="idempotency_key is required")
        operation = f"html-approval:{job.public_id}"
        action_lock = _idempotency_operation_lock(
            operation,
            job.owner_user_id,
            idempotency_key,
        )
        with action_lock:
            existing = _get_idempotent_response(
                operation,
                job.owner_user_id,
                idempotency_key,
                store,
            )
            if existing is not None:
                return _render_html(
                    templates,
                    "monthly_report_workshop/fragments/approval.html",
                    {
                        **existing,
                        "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
                        "approval_idempotency_key": _new_idempotency_key(),
                    },
                )

            context = _approval_context(job, store)
            artifact = context["artifact"]
            if context["blockers"]:
                return _render_html(
                    templates,
                    "monthly_report_workshop/fragments/approval.html",
                    {
                        **context,
                        "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
                        "approval_idempotency_key": _new_idempotency_key(),
                    },
                    status_code=422,
                )
            if str(form.get("confirm_ready") or "") != "yes":
                raise HTTPException(status_code=422, detail="confirm_ready is required")
            submitted_hash = str(form.get("artifact_hash") or "")
            latest_hash = str(artifact["content_hash"] if artifact else "")
            if not submitted_hash or not hmac.compare_digest(submitted_hash, latest_hash):
                raise HTTPException(
                    status_code=409,
                    detail="latest distribution artifact hash does not match",
                )

            approval_payload = {
                "approved": True,
                "artifact_id": artifact["artifact_id"],
                "artifact_type": artifact["artifact_type"],
                "artifact_hash": latest_hash,
                "comment": str(form.get("approval_comment") or "").strip(),
            }
            approval_content = json.dumps(approval_payload, ensure_ascii=False, sort_keys=True)
            approval_artifact = store.record_artifact(
                job.public_id,
                artifact_type="approval",
                content=approval_content,
                content_hash=_hash_text(approval_content),
            )
            _record_job_audit_log(
                actor_id=current_user.user_id,
                action="monthly_report_approval_saved",
                job=job,
                metadata={
                    "approval_artifact_id": approval_artifact.public_id,
                    "approval_artifact_hash": approval_artifact.content_hash,
                    "approved_artifact_id": artifact["artifact_id"],
                    "approved_artifact_type": artifact["artifact_type"],
                    "approved_artifact_hash": latest_hash,
                    "comment_present": bool(approval_payload["comment"]),
                    "comment_length": len(approval_payload["comment"]),
                },
            )
            job = store.get(job.public_id)
            response_context = _approval_context(job, store)
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
        "monthly_report_workshop/fragments/approval.html",
        {
            **response_context,
            "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
            "approval_idempotency_key": _new_idempotency_key(),
        },
    )


@html_router.post("/monthly-reports/jobs/{job_id}/fragments/export", response_class=HTMLResponse)
async def monthly_report_export_action(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    templates = _templates(request)
    form = await request.form()
    try:
        _verify_csrf_token(form, request)
        job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
        store = _get_artifact_write_store(current_user)
        idempotency_key = _idempotency_key_from_form(form, request)
        if idempotency_key is None:
            raise HTTPException(status_code=422, detail="idempotency_key is required")
        operation = f"html-export:{job.public_id}"
        action_lock = _idempotency_operation_lock(
            operation,
            job.owner_user_id,
            idempotency_key,
        )
        with action_lock:
            existing = _get_idempotent_response(
                operation,
                job.owner_user_id,
                idempotency_key,
                store,
            )
            if existing is not None:
                return _render_html(
                    templates,
                    "monthly_report_workshop/fragments/export.html",
                    {
                        **existing,
                        "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
                        "export_idempotency_key": _new_idempotency_key(),
                    },
                )

            context = _export_context(job, store)
            artifact = context["artifact"]
            submitted_hash = str(form.get("artifact_hash") or "")
            latest_hash = str(artifact["content_hash"] if artifact else "")
            if context["export_blockers"]:
                return _render_html(
                    templates,
                    "monthly_report_workshop/fragments/export.html",
                    {
                        **context,
                        "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
                        "export_idempotency_key": _new_idempotency_key(),
                    },
                    status_code=422,
                )
            if not submitted_hash or not hmac.compare_digest(submitted_hash, latest_hash):
                raise HTTPException(
                    status_code=409,
                    detail="latest distribution artifact hash does not match",
                )

            export_content = _markdown_to_export_html(str(artifact["content"] or ""))
            export_artifact = store.record_artifact(
                job.public_id,
                artifact_type="export_html",
                content=export_content,
                content_hash=_hash_text(export_content),
            )
            _record_job_audit_log(
                actor_id=current_user.user_id,
                action="monthly_report_export_html_saved",
                job=job,
                metadata={
                    "export_artifact_id": export_artifact.public_id,
                    "export_artifact_hash": export_artifact.content_hash,
                    "source_artifact_id": artifact["artifact_id"],
                    "source_artifact_type": artifact["artifact_type"],
                    "source_artifact_hash": latest_hash,
                },
            )
            job = store.get(job.public_id)
            response_context = _export_context(job, store)
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
        "monthly_report_workshop/fragments/export.html",
        {
            **response_context,
            "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
            "export_idempotency_key": _new_idempotency_key(),
        },
    )


@html_router.post("/monthly-reports/jobs/{job_id}/fragments/html-source", response_class=HTMLResponse)
async def monthly_report_html_source_action(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    templates = _templates(request)
    form = await request.form()
    try:
        _verify_csrf_token(form, request)
        job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
        store = _get_artifact_write_store(current_user)
        idempotency_key = _idempotency_key_from_form(form, request)
        if idempotency_key is None:
            raise HTTPException(status_code=422, detail="idempotency_key is required")
        operation = f"html-source-edit:{job.public_id}"
        action_lock = _idempotency_operation_lock(
            operation,
            job.owner_user_id,
            idempotency_key,
        )
        with action_lock:
            existing = _get_idempotent_response(
                operation,
                job.owner_user_id,
                idempotency_key,
                store,
            )
            if existing is not None:
                return _render_html(
                    templates,
                    "monthly_report_workshop/fragments/html_source.html",
                    {
                        **existing,
                        "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
                        "html_source_idempotency_key": _new_idempotency_key(),
                    },
                )

            context = _html_source_context(job, store)
            export_artifact = context["export_artifact"]
            if context["html_source_blockers"]:
                return _render_html(
                    templates,
                    "monthly_report_workshop/fragments/html_source.html",
                    {
                        **context,
                        "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
                        "html_source_idempotency_key": _new_idempotency_key(),
                    },
                    status_code=422,
                )
            edited_html = str(form.get("html_source") or "")
            if not edited_html.strip():
                raise HTTPException(status_code=422, detail="html_source is required")
            submitted_hash = str(form.get("base_export_hash") or "")
            latest_hash = str(export_artifact["content_hash"] if export_artifact else "")
            if not submitted_hash or not hmac.compare_digest(submitted_hash, latest_hash):
                raise HTTPException(
                    status_code=409,
                    detail="latest export artifact hash does not match",
                )

            export_artifact = store.record_artifact(
                job.public_id,
                artifact_type="export_html",
                content=edited_html,
                content_hash=_hash_text(edited_html),
            )
            _record_job_audit_log(
                actor_id=current_user.user_id,
                action="monthly_report_export_html_edited",
                job=job,
                metadata={
                    "export_artifact_id": export_artifact.public_id,
                    "export_artifact_hash": export_artifact.content_hash,
                    "base_export_hash": latest_hash,
                    "html_length": len(edited_html),
                },
            )
            job = store.get(job.public_id)
            response_context = {
                **_html_source_context(job, store),
                "html_source_message": "HTMLソースを保存しました",
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
        "monthly_report_workshop/fragments/html_source.html",
        {
            **response_context,
            "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
            "html_source_idempotency_key": _new_idempotency_key(),
        },
    )


@html_router.post("/monthly-reports/jobs/{job_id}/fragments/distribution", response_class=HTMLResponse)
async def monthly_report_distribution_action(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    templates = _templates(request)
    form = await request.form()
    try:
        _verify_csrf_token(form, request)
        job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
        store = _get_artifact_write_store(current_user)
        idempotency_key = _idempotency_key_from_form(form, request)
        if idempotency_key is None:
            raise HTTPException(status_code=422, detail="idempotency_key is required")
        operation = f"html-distribution:{job.public_id}"
        action_lock = _idempotency_operation_lock(
            operation,
            job.owner_user_id,
            idempotency_key,
        )
        with action_lock:
            existing = _get_idempotent_response(
                operation,
                job.owner_user_id,
                idempotency_key,
                store,
            )
            if existing is not None:
                return _render_html(
                    templates,
                    "monthly_report_workshop/fragments/distribution.html",
                    {
                        **existing,
                        "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
                        "distribution_idempotency_key": _new_idempotency_key(),
                    },
                )

            context = _distribution_context(job, store)
            export_artifact = context["export_artifact"]
            if context["distribution_blockers"]:
                return _render_html(
                    templates,
                    "monthly_report_workshop/fragments/distribution.html",
                    {
                        **context,
                        "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
                        "distribution_idempotency_key": _new_idempotency_key(),
                    },
                    status_code=422,
                )
            submitted_hash = str(form.get("export_hash") or "")
            latest_hash = str(export_artifact["content_hash"] if export_artifact else "")
            if not submitted_hash or not hmac.compare_digest(submitted_hash, latest_hash):
                raise HTTPException(
                    status_code=409,
                    detail="latest export artifact hash does not match",
                )
            payload = {
                "status": "ready_for_manual_distribution",
                "export_artifact_id": export_artifact["artifact_id"],
                "export_artifact_hash": latest_hash,
                "approval_artifact_id": (
                    context["approval"]["artifact_id"] if context["approval"] else None
                ),
                "prepared_for": "manual_send",
            }
            content = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            distribution_artifact = store.record_artifact(
                job.public_id,
                artifact_type="distribution_package",
                content=content,
                content_hash=_hash_text(content),
            )
            _record_job_audit_log(
                actor_id=current_user.user_id,
                action="monthly_report_distribution_package_saved",
                job=job,
                metadata={
                    "distribution_artifact_id": distribution_artifact.public_id,
                    "distribution_artifact_hash": distribution_artifact.content_hash,
                    "export_artifact_id": export_artifact["artifact_id"],
                    "export_artifact_hash": latest_hash,
                    "approval_artifact_id": payload["approval_artifact_id"],
                },
            )
            job = store.get(job.public_id)
            response_context = _distribution_context(job, store)
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
    return _render_html(
        templates,
        "monthly_report_workshop/fragments/distribution.html",
        {
            **response_context,
            "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
            "distribution_idempotency_key": _new_idempotency_key(),
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
        idempotency_key = _idempotency_key_from_form(form, request)
        if idempotency_key is None:
            raise HTTPException(status_code=422, detail="idempotency_key is required")
        if source.status in {
            JobStatus.QUEUED,
            JobStatus.RUNNING,
            JobStatus.CANCEL_REQUESTED,
        }:
            raise HTTPException(
                status_code=409,
                detail="実行中/待機中のジョブは再生成できません",
            )
        operation = f"html-rerun:{source.public_id}"
        action_lock = _idempotency_operation_lock(
            operation,
            source.owner_user_id,
            idempotency_key,
        )
        with action_lock:
            existing = _get_idempotent_job(
                operation,
                source.owner_user_id,
                idempotency_key,
                store,
            )
            if existing is not None:
                return _render_html(
                    templates,
                    "monthly_report_workshop/fragments/rerun_created.html",
                    {"job": _job_view(existing)},
                )
            if store.count_active_jobs(source.owner_user_id) >= MAX_ACTIVE_JOBS_PER_USER:
                raise JobLimitExceeded("user already has 3 active generation jobs")
            can_tune = _can_tune_monthly_report(current_user)
            prompt_version = source.prompt_version
            model_report = source.model_report
            model_light = source.model_light
            resolved_model_report = source.resolved_model_report
            if can_tune:
                prompt_version = str(form.get("rerun_prompt_version") or "") or prompt_version
                submitted_model_report = str(form.get("rerun_model_report") or "") or None
                submitted_model_light = str(form.get("rerun_model_light") or "") or None
                if submitted_model_report:
                    model_report = submitted_model_report
                    resolved_model_report = None
                if submitted_model_light:
                    model_light = submitted_model_light
            rerun = store.create_job(
                target_month=source.target_month,
                household_key=source.household_key,
                owner_user_id=source.owner_user_id,
                template_key=source.template_key,
                prompt_version=prompt_version,
                template_hash=source.template_hash,
                model_report=model_report,
                model_light=model_light,
                resolved_model_report=resolved_model_report,
                source_bundle_hash=source.source_bundle_hash,
                app_version=source.app_version,
                prompt_scope_notes=source.prompt_scope_notes,
                max_worker_attempts=source.max_worker_attempts,
            )
            _remember_idempotent_job(operation, source.owner_user_id, idempotency_key, rerun, store)
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
        "monthly_report_workshop/fragments/rerun_created.html",
        {"job": _job_view(rerun)},
    )


@html_router.post("/monthly-reports/jobs/{job_id}/cancel", response_class=HTMLResponse)
async def monthly_report_cancel_action(
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
        if idempotency_key is None:
            raise HTTPException(status_code=422, detail="idempotency_key is required")
        operation = f"html-cancel:{job.public_id}"
        existing = _get_idempotent_response(
            operation,
            job.owner_user_id,
            idempotency_key,
            store,
        )
        if existing is not None:
            return _render_html(
                templates,
                "monthly_report_workshop/fragments/status.html",
                existing,
            )
        if job.status not in {JobStatus.QUEUED, JobStatus.RUNNING}:
            raise HTTPException(
                status_code=409,
                detail="queued / running のジョブだけキャンセルできます",
            )
        cancelled = store.request_cancel(job.public_id)
        response_context = {"job": _job_view(cancelled)}
        _remember_idempotent_response(
            operation,
            cancelled.owner_user_id,
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
    return _render_html(
        templates,
        "monthly_report_workshop/fragments/status.html",
        response_context,
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
        store = _get_artifact_write_store(current_user)
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
        latest_artifact = _latest_preview_artifact(job, store)
        latest_hash = str(latest_artifact["content_hash"] if latest_artifact else "")
        submitted_hash = str(form.get("base_content_hash") or "")
        if latest_hash and submitted_hash and not hmac.compare_digest(submitted_hash, latest_hash):
            raise HTTPException(
                status_code=409,
                detail="base content hash does not match latest preview artifact",
            )
        store.record_artifact(
            job.public_id,
            artifact_type="final_markdown",
            content=content,
            content_hash=_hash_text(content),
        )
        job = store.get(job_id)
        response_context = {
            "job": _job_view(job),
            "artifact": _latest_preview_artifact(job, store),
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
            "artifact": _latest_preview_artifact(job, store),
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
        store = _get_source_write_store(current_user)
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
        if not (payload.snapshot_text or "").strip():
            raise HTTPException(status_code=422, detail="source text is required")
        store.record_source(
            job.public_id,
            source_type=payload.source_type,
            display_name=payload.display_name,
            snapshot_text=payload.snapshot_text,
            content_hash=payload.content_hash,
        )
        job = store.get(job_id)
        response_context = {
            "job": _job_view(job, store),
            "sources": _source_views(job, store),
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
            "job": _job_view(job, store),
            "sources": _source_views(job, store),
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
        source_store = _get_source_write_store(current_user)
        direct_store = _get_store()
        idempotency_key = _idempotency_key_from_form(form, request)
        after_fetch_action = str(form.get("after_fetch_action") or "").strip()
        operation = f"html-google-sources:{job.public_id}:{after_fetch_action or 'fetch'}"
        existing = _get_idempotent_response(
            operation,
            job.owner_user_id,
            idempotency_key,
            direct_store,
        )
        if existing is not None:
            return _render_html(
                templates,
                "monthly_report_workshop/fragments/google_sources_result.html",
                {
                    "job": existing["job"],
                    "sources": existing["sources"],
                    "artifact": existing.get("artifact"),
                    "validations": existing.get("validations", []),
                    "steps": existing.get("steps", []),
                    "events": existing.get("events", []),
                    "generated": bool(existing.get("generated")),
                    "queue_requested": bool(existing.get("queue_requested")),
                    "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME),
                },
            )
        doc_ids = _nonempty_lines(str(form.get("doc_ids") or ""))
        sheet_ranges = []
        spreadsheet_id = str(form.get("spreadsheet_id") or "").strip()
        range_name = str(form.get("range_name") or "").strip()
        if spreadsheet_id and range_name:
            sheet_ranges.append(
                GoogleSheetRangeRequest(
                    spreadsheet_id=spreadsheet_id,
                    range_name=range_name,
                    display_name=str(form.get("sheet_display_name") or "") or None,
                )
            )
        elif spreadsheet_id:
            sheet_ranges.extend(
                _default_monthly_report_sheet_ranges(
                    spreadsheet_id,
                    student_sheet_name=str(form.get("student_sheet_name") or "") or None,
                    lesson_plan_sheet_name=str(form.get("lesson_plan_sheet_name") or "") or None,
                )
            )
        elif range_name:
            raise HTTPException(
                status_code=422,
                detail="Google Sheets ID is required",
            )
        if not doc_ids and not sheet_ranges:
            raise HTTPException(
                status_code=422,
                detail="Google Doc ID or Google Sheets ID is required",
            )
        access_token = _resolve_google_workspace_access_token(current_user)
        if not access_token:
            raise HTTPException(
                status_code=503,
                detail="Google Workspace access token is not configured",
            )
        fetch_google_workspace_sources_for_job(
            source_store,
            job.public_id,
            client=GoogleWorkspaceClient(access_token=access_token),
            doc_ids=doc_ids,
            sheet_ranges=[
                sheet_range.model_dump(exclude_none=True)
                for sheet_range in sheet_ranges
            ],
        )
        job = _get_authorized_job_or_404(job_id, current_user)
        generated = False
        queue_requested = False
        if after_fetch_action == "generate_openrouter":
            if job.status != JobStatus.QUEUED:
                raise HTTPException(
                    status_code=409,
                    detail="queued のジョブだけ生成開始できます",
                )
            if _can_use_service_owned_html_workflow(current_user):
                settings = get_settings()
                if not settings.openrouter_api_key:
                    raise HTTPException(
                        status_code=503,
                        detail="OPENROUTER_API_KEY is not configured",
                    )
                job = _run_service_owned_monthly_report_job(
                    direct_store,
                    job.public_id,
                    provider=OpenRouterMonthlyReportProvider(
                        api_key=settings.openrouter_api_key,
                        model=settings.openrouter_model_report,
                        timeout=settings.openrouter_timeout_seconds,
                        max_tokens=settings.openrouter_max_tokens,
                    ),
                    prompt_version=settings.monthly_report_prompt_version,
                    model_report=settings.openrouter_model_report,
                    app_version=settings.app_version,
                )
                _record_service_owned_workflow_audit(
                    current_user=current_user,
                    job=job,
                    trigger="html_google_sources",
                    mode="openrouter",
                    idempotency_key_present=idempotency_key is not None,
                )
                generated = True
            else:
                _record_worker_owned_workflow_request_audit(
                    current_user=current_user,
                    job=job,
                    trigger="html_google_sources",
                    mode="stage",
                    idempotency_key_present=idempotency_key is not None,
                )
                _trigger_worker_owned_monthly_report_job(
                    current_user=current_user,
                    job=job,
                    trigger="html_google_sources",
                )
                queue_requested = True
        else:
            job = source_store.get(job_id)
        read_store = _get_read_store(current_user)
        response_context = {
            "job": _job_view(job, read_store),
            "sources": _source_views(job, read_store),
            "artifact": _latest_preview_artifact(job, read_store),
            "validations": _validation_views(job, read_store),
            "generated": generated,
            "queue_requested": queue_requested,
            **_operation_log_context(job, read_store),
        }
        _remember_idempotent_response(
            operation,
            job.owner_user_id,
            idempotency_key,
            response_context,
            direct_store,
        )
    except HTTPException as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc.detail)},
            status_code=exc.status_code,
        )
    except CloudRunJobTriggerError as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc)},
            status_code=502,
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
        "monthly_report_workshop/fragments/google_sources_result.html",
        {
            "job": _job_view(job, read_store),
            "sources": _source_views(job, read_store),
            "artifact": _latest_preview_artifact(job, read_store),
            "validations": _validation_views(job, read_store),
            "generated": generated,
            **_operation_log_context(job, read_store),
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
        store = _get_feedback_write_store(current_user)
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
        job = store.get(job_id)
        response_context = {"job": _job_view(job, store)}
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
        {"job": _job_view(job, store), "csrf_token": request.cookies.get(_CSRF_COOKIE_NAME)},
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
        if run_mode in {"mock", "openrouter"} and not _can_use_service_owned_html_workflow(current_user):
            raise HTTPException(
                status_code=403,
                detail=_service_owned_html_workflow_reason(current_user),
            )
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
            started = _run_service_owned_monthly_report_job(
                store,
                job.public_id,
                provider=StaticMonthlyReportProvider(_default_html_mock_draft(job)),
                prompt_version=get_settings().monthly_report_prompt_version,
                model_report="mock/html-ui-model",
                app_version=get_settings().app_version,
            )
            _record_service_owned_workflow_audit(
                current_user=current_user,
                job=started,
                trigger="html_run",
                mode="mock",
                idempotency_key_present=idempotency_key is not None,
            )
            _remember_idempotent_job(operation, job.owner_user_id, idempotency_key, started, store)
        elif run_mode == "openrouter":
            settings = get_settings()
            if not settings.openrouter_api_key:
                raise HTTPException(
                    status_code=503,
                    detail="OPENROUTER_API_KEY is not configured",
                )
            started = _run_service_owned_monthly_report_job(
                store,
                job.public_id,
                provider=OpenRouterMonthlyReportProvider(
                    api_key=settings.openrouter_api_key,
                    model=settings.openrouter_model_report,
                    timeout=settings.openrouter_timeout_seconds,
                    max_tokens=settings.openrouter_max_tokens,
                ),
                prompt_version=settings.monthly_report_prompt_version,
                model_report=settings.openrouter_model_report,
                app_version=settings.app_version,
            )
            _record_service_owned_workflow_audit(
                current_user=current_user,
                job=started,
                trigger="html_run",
                mode="openrouter",
                idempotency_key_present=idempotency_key is not None,
            )
            _remember_idempotent_job(operation, job.owner_user_id, idempotency_key, started, store)
        else:
            if job.status != JobStatus.QUEUED:
                raise HTTPException(
                    status_code=409,
                    detail="queued のジョブだけ生成開始できます",
                )
            if _can_use_service_owned_html_workflow(current_user):
                started = store.start_next(job.public_id)
            else:
                started = store.get(job.public_id)
                _record_worker_owned_workflow_request_audit(
                    current_user=current_user,
                    job=started,
                    trigger="html_run",
                    mode="stage",
                    idempotency_key_present=idempotency_key is not None,
                )
                _trigger_worker_owned_monthly_report_job(
                    current_user=current_user,
                    job=started,
                    trigger="html_run",
                )
            _remember_idempotent_job(operation, job.owner_user_id, idempotency_key, started, store)
    except HTTPException as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc.detail)},
            status_code=exc.status_code,
        )
    except CloudRunJobTriggerError as exc:
        return _render_html(
            templates,
            "monthly_report_workshop/fragments/alert.html",
            {"tone": "error", "message": str(exc)},
            status_code=502,
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


def _run_service_owned_monthly_report_job(
    store: MockJobStore | PostgresJobStore,
    job_id: str,
    *,
    provider: StaticMonthlyReportProvider | OpenRouterMonthlyReportProvider,
    prompt_version: str | None,
    model_report: str | None,
    app_version: str | None,
) -> MockJob:
    """Run generation through the server-owned workflow boundary.

    This path intentionally keeps job state mutation, llm_call_logs, and
    reproducibility metadata on the direct store side even when surrounding
    normal-user content writes already use user-JWT RLS clients.
    """
    return run_monthly_report_job(
        store,
        job_id,
        provider=provider,
        template_path=_DEFAULT_MONTHLY_REPORT_TEMPLATE,
        prompt_version=prompt_version,
        model_report=model_report,
        app_version=app_version,
    )


def _record_service_owned_workflow_audit(
    *,
    current_user: CurrentUser,
    job: MockJob,
    trigger: str,
    mode: str,
    idempotency_key_present: bool,
) -> None:
    _record_job_audit_log(
        actor_id=current_user.user_id,
        action="monthly_report_service_owned_workflow_executed",
        job=job,
        metadata={
            "trigger": trigger,
            "mode": mode,
            "boundary": "service_owned_workflow",
            "idempotency_key_present": idempotency_key_present,
        },
    )


def _record_worker_owned_workflow_request_audit(
    *,
    current_user: CurrentUser,
    job: MockJob,
    trigger: str,
    mode: str,
    idempotency_key_present: bool,
) -> None:
    _record_job_audit_log(
        actor_id=current_user.user_id,
        action="monthly_report_worker_owned_workflow_requested",
        job=job,
        metadata={
            "trigger": trigger,
            "mode": mode,
            "boundary": "worker_owned_workflow",
            "idempotency_key_present": idempotency_key_present,
        },
    )


def _record_worker_trigger_audit(
    *,
    current_user: CurrentUser,
    job: MockJob,
    trigger: str,
    operation_name: str | None,
) -> None:
    _record_job_audit_log(
        actor_id=current_user.user_id,
        action="monthly_report_worker_job_triggered",
        job=job,
        metadata={
            "trigger": trigger,
            "boundary": "worker_owned_workflow",
            "operation_name": operation_name,
        },
    )


def _trigger_worker_owned_monthly_report_job(
    *,
    current_user: CurrentUser,
    job: MockJob,
    trigger: str,
) -> dict[str, Any] | None:
    settings = get_settings()
    if not (
        settings.cloud_run_worker_job_project_id
        and settings.cloud_run_worker_job_region
        and settings.cloud_run_worker_job_name
    ):
        return None
    executor = CloudRunJobExecutor(
        project_id=settings.cloud_run_worker_job_project_id,
        region=settings.cloud_run_worker_job_region,
        job_name=settings.cloud_run_worker_job_name,
        token_provider=MetadataServerAccessTokenProvider(
            env_access_token=settings.cloud_run_worker_trigger_access_token,
            timeout_seconds=settings.cloud_run_worker_trigger_timeout_seconds,
        ),
        timeout_seconds=settings.cloud_run_worker_trigger_timeout_seconds,
    )
    result = executor.run(env_vars={"EB_WORKER_JOB_ID": job.public_id})
    _record_worker_trigger_audit(
        current_user=current_user,
        job=job,
        trigger=trigger,
        operation_name=str(result.get("name") or "") or None,
    )
    return result


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


def _filter_job_views(
    jobs: list[dict[str, Any]],
    request: Request,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    status = request.query_params.get("status", "").strip()
    query = request.query_params.get("q", "").strip()
    query_normalized = query.casefold()
    allowed_statuses = {
        "",
        JobStatus.QUEUED,
        JobStatus.RUNNING,
        JobStatus.SUCCEEDED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    }
    if status not in allowed_statuses:
        status = ""

    filtered = jobs
    if status:
        filtered = [job for job in filtered if job["status"] == status]
    if query_normalized:
        filtered = [
            job
            for job in filtered
            if query_normalized
            in " ".join(
                [
                    str(job.get("public_id") or ""),
                    str(job.get("target_month") or ""),
                    str(job.get("display_household") or ""),
                    str(job.get("prompt_version") or ""),
                    str(job.get("model") or ""),
                ]
            ).casefold()
        ]

    return filtered, {"status": status, "q": query, "filtered_count": len(filtered)}


@router.post("/jobs")
def create_job(
    request: Request,
    payload: CreateMonthlyReportJobRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    store = _get_store()
    # Job creation is intentionally a server-owned command. We derive the
    # effective owner from auth in nonmock mode and keep the insert on the
    # service-owned direct store, rather than treating this like a generic
    # user-JWT append-only write.
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
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    _require_state_mutation_caller_intent(
        request,
        current_user,
        route_label="rerun",
    )
    source = _get_write_preflight_authorized_job_or_404(job_id, current_user)
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
    job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
    store = _get_feedback_write_store(current_user)
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
    store = _get_source_write_store(current_user)
    job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
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
    job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
    source_store = _get_source_write_store(current_user)
    direct_store = _get_store()
    idempotency_key = _idempotency_key_from_request(request)
    operation = f"api-fetch-google-sources:{job.public_id}"
    existing = _get_idempotent_response(
        operation,
        job.owner_user_id,
        idempotency_key,
        direct_store,
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
            source_store,
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
        direct_store,
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
    try:
        UUID(current_user.user_id)
    except ValueError:
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
    store = _get_artifact_write_store(current_user)
    job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
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
    request: Request,
    payload: CreateMonthlyReportValidationRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    _require_state_mutation_caller_intent(
        request,
        current_user,
        route_label="validations",
    )
    job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
    store = _get_validation_write_store(current_user)
    idempotency_store = _get_store()
    idempotency_key = _idempotency_key_from_request(request)
    operation = f"api-validation:{job.public_id}"
    existing = _get_idempotent_response(
        operation,
        job.owner_user_id,
        idempotency_key,
        idempotency_store,
    )
    if existing is not None:
        return existing
    validation = store.record_validation(
        job.public_id,
        rule_id=payload.rule_id,
        severity=payload.severity,
        message=payload.message,
        path=payload.path,
    )
    response = _validation_response(validation)
    _remember_idempotent_response(
        operation,
        job.owner_user_id,
        idempotency_key,
        response,
        idempotency_store,
    )
    return response


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
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    _require_state_mutation_caller_intent(
        request,
        current_user,
        route_label="start",
    )
    job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
    store = _get_store()
    return _run_transition(lambda: store.start_next(job.public_id))


@router.post("/jobs/{job_id}/complete-stage")
def complete_current_stage(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    _require_state_mutation_caller_intent(
        request,
        current_user,
        route_label="complete-stage",
    )
    job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
    store = _get_store()
    return _run_transition(lambda: store.complete_current_stage(job.public_id))


@router.post("/jobs/{job_id}/fail")
def fail_job(
    job_id: str,
    request: Request,
    payload: FailMonthlyReportJobRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    _require_state_mutation_caller_intent(
        request,
        current_user,
        route_label="fail",
    )
    error_message = payload.error_message or payload.message
    if not error_message:
        raise HTTPException(status_code=422, detail="error_message is required")
    job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
    store = _get_store()
    return _run_transition(
        lambda: store.fail_current_job(
            job.public_id,
            error_type=payload.error_type,
            error_message=error_message,
        )
    )


@router.post("/jobs/{job_id}/manual-recovery/fail")
def manual_recovery_fail_job(
    job_id: str,
    request: Request,
    payload: ManualRecoveryFailJobRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    route_label = "manual-recovery/fail"
    _require_admin_state_mutation_caller_intent(
        request,
        current_user,
        route_label=route_label,
    )
    job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
    if job.status != JobStatus.RUNNING:
        raise HTTPException(
            status_code=409,
            detail="manual recovery fail requires running job",
        )
    error_message = payload.error_message or payload.note
    if not error_message:
        error_message = "manual recovery marked the running job as failed"
    previous_stage = job.current_stage
    try:
        failed_job = _get_store().fail_current_job(
            job.public_id,
            error_type="manual_recovery_required",
            error_message=error_message,
        )
    except StatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _record_job_audit_log(
        actor_id=current_user.user_id,
        action="monthly_report_job_manual_recovery_failed",
        job=failed_job,
        metadata={
            "caller_intent": "admin",
            "error_type": "manual_recovery_required",
            "operator_note_present": bool(payload.error_message or payload.note),
            "previous_stage": previous_stage,
        },
    )
    return _job_response(failed_job)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    _require_state_mutation_caller_intent(
        request,
        current_user,
        route_label="cancel",
    )
    return _job_response(
        _get_store().request_cancel(
            _get_write_preflight_authorized_job_or_404(job_id, current_user).public_id
        )
    )


@router.post("/jobs/{job_id}/run-mock")
def run_job_with_mock_provider(
    job_id: str,
    request: Request,
    payload: RunMonthlyReportMockRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    _require_state_mutation_caller_intent(
        request,
        current_user,
        route_label="run-mock",
    )
    job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
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
    _require_state_mutation_caller_intent(
        request,
        current_user,
        route_label="run-openrouter",
    )
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENROUTER_API_KEY is not configured",
        )

    job = _get_write_preflight_authorized_job_or_404(job_id, current_user)
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
