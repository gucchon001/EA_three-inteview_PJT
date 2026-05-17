from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import logging
from pathlib import Path
import re
from time import perf_counter
from typing import Protocol

import httpx

from eb_app.monthly_reports.jobs import MockJob, MockJobStore
from eb_app.monthly_reports.llm_messages import Message, build_monthly_report_messages
from eb_app.monthly_reports.observability import emit_cloud_logging_event
from eb_app.monthly_reports.postgres_store import PostgresJobStore


JobStore = MockJobStore | PostgresJobStore
FORBIDDEN_DISTRIBUTION_TERMS = ("担当CA", "教師 MTG", "NotebookLM")
PROMPT_INJECTION_PHRASES = (
    "以前の指示を無視",
    "これまでの指示を無視",
    "上記の指示を無視",
    "ignore previous instructions",
    "ignore all previous instructions",
)
INTERNAL_MEMO_EXPOSURE_TERMS = (
    "内部メモ",
    "管理者メモ",
    "社内メモ",
    "送付禁止",
    "family-facingではない",
    "admin only",
    "internal memo",
)
# 決定論的サニタイズ: テンプレート注記がLLM出力に混入した場合の安全置換。
# 意味を保ちながら家庭向け表現へ変換できるもののみ定義する。
FORBIDDEN_TERM_SAFE_REPLACEMENTS: dict[str, str] = {
    "担当CA": "担当",
    "教師 MTG": "授業計画の確認",
    "NotebookLM": "",
    "Gemini メモ": "面談メモ",
    "Geminiメモ": "面談メモ",
    "Google Meetメモ": "面談メモ",
    "Google Meet メモ": "面談メモ",
    "Google Meet のメモ": "面談メモ",
    "Google Meetのメモ": "面談メモ",
    "Google Meet の文字起こし": "面談メモ",
    "Google Meetの文字起こし": "面談メモ",
    "Gemini が作成したメモ": "面談メモ",
    "Geminiが作成したメモ": "面談メモ",
    "Google 生成メモ": "面談メモ",
    "Google生成メモ": "面談メモ",
}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMCompletion:
    content: str
    resolved_model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None


class MonthlyReportProvider(Protocol):
    def complete(
        self,
        *,
        messages: list[Message],
        model: str | None = None,
    ) -> LLMCompletion:
        pass


class ProviderCallError(RuntimeError):
    pass


@dataclass
class StaticMonthlyReportProvider:
    content: str
    resolved_model: str | None = "mock/report-model"
    last_messages: list[Message] = field(default_factory=list)
    last_model: str | None = None

    def complete(
        self,
        *,
        messages: list[Message],
        model: str | None = None,
    ) -> LLMCompletion:
        self.last_messages = messages
        self.last_model = model
        return LLMCompletion(content=self.content, resolved_model=self.resolved_model)


class OpenRouterMonthlyReportProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        client: httpx.Client | None = None,
        timeout: float = 120.0,
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=timeout)
        self._temperature = temperature
        self._max_tokens = max_tokens

    def complete(
        self,
        *,
        messages: list[Message],
        model: str | None = None,
    ) -> LLMCompletion:
        requested_model = model or self._model
        try:
            payload = {
                "model": requested_model,
                "messages": messages,
                "temperature": self._temperature,
            }
            if self._max_tokens is not None:
                payload["max_tokens"] = self._max_tokens
            response = self._client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            response = getattr(exc, "response", None)
            status = response.status_code if response is not None else "unknown"
            raise ProviderCallError(f"OpenRouter call failed with status {status}") from exc

        body = response.json()
        choices = body.get("choices") or []
        content = ""
        if choices:
            first_choice = choices[0]
            content = ((first_choice.get("message") or {}).get("content") or "").strip()
            finish_reason = first_choice.get("finish_reason")
        else:
            finish_reason = None
        usage = body.get("usage") or {}
        return LLMCompletion(
            content=content,
            resolved_model=body.get("model"),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            finish_reason=finish_reason,
        )


def run_monthly_report_job(
    store: JobStore,
    job_id: str,
    *,
    provider: MonthlyReportProvider,
    template_path: Path,
    rules_excerpt_path: Path | None = None,
    artifact: str = "md",
    prompt_version: str | None = None,
    model_report: str | None = None,
    app_version: str | None = None,
) -> MockJob:
    job = store.start_next(job_id)
    return _run_started_monthly_report_job(
        store,
        job,
        provider=provider,
        template_path=template_path,
        rules_excerpt_path=rules_excerpt_path,
        artifact=artifact,
        prompt_version=prompt_version,
        model_report=model_report,
        app_version=app_version,
    )


def run_claimed_monthly_report_job(
    store: JobStore,
    job_id: str,
    *,
    provider: MonthlyReportProvider,
    template_path: Path,
    rules_excerpt_path: Path | None = None,
    artifact: str = "md",
    prompt_version: str | None = None,
    model_report: str | None = None,
    app_version: str | None = None,
) -> MockJob:
    job = store.get(job_id)
    if job.status != "running" or job.current_stage != "fetch_sources":
        raise ProviderCallError("claimed job must be running at fetch_sources")
    return _run_started_monthly_report_job(
        store,
        job,
        provider=provider,
        template_path=template_path,
        rules_excerpt_path=rules_excerpt_path,
        artifact=artifact,
        prompt_version=prompt_version,
        model_report=model_report,
        app_version=app_version,
    )


def _run_started_monthly_report_job(
    store: JobStore,
    job: MockJob,
    *,
    provider: MonthlyReportProvider,
    template_path: Path,
    rules_excerpt_path: Path | None = None,
    artifact: str = "md",
    prompt_version: str | None = None,
    model_report: str | None = None,
    app_version: str | None = None,
) -> MockJob:
    job = store.update_reproducibility_meta(
        job.public_id,
        prompt_version=job.prompt_version or prompt_version,
        model_report=job.model_report or model_report,
        app_version=job.app_version or app_version,
    )
    sources = store.list_sources(job.public_id)
    bundle = _bundle_sources(sources)
    template_hash = _hash_template(template_path)
    source_bundle_hash = _hash_text(bundle)
    job = store.update_reproducibility_meta(
        job.public_id,
        template_hash=template_hash,
        source_bundle_hash=source_bundle_hash,
    )
    job = store.complete_current_stage(job.public_id)
    job = store.complete_current_stage(job.public_id)

    messages = build_monthly_report_messages(
        artifact=artifact,
        template_path=template_path,
        rules_excerpt_path=rules_excerpt_path,
        bundle=bundle,
        ideal_plain="",
        structure_html="",
        prompt_scope_notes=job.prompt_scope_notes,
    )
    job = store.complete_current_stage(job.public_id)

    requested_model = job.model_report
    request_hash = _hash_messages(messages)
    started_at = perf_counter()
    try:
        completion = provider.complete(messages=messages, model=job.model_report)
    except ProviderCallError as exc:
        latency_ms = int((perf_counter() - started_at) * 1000)
        store.record_llm_call(
            job.public_id,
            prompt_kind="report",
            provider="openrouter",
            requested_model=requested_model,
            resolved_model=None,
            prompt_version=job.prompt_version,
            request_hash=request_hash,
            response_hash=None,
            latency_ms=latency_ms,
            input_tokens=None,
            output_tokens=None,
            finish_reason=None,
            error_type="provider_call_failed",
        )
        emit_cloud_logging_event(
            logger,
            event="monthly_report.provider_failed",
            severity="ERROR",
            job_id=job.public_id,
            stage="call_llm",
            error_type="provider_call_failed",
            prompt_kind="report",
            provider="openrouter",
            requested_model=requested_model,
            prompt_version=job.prompt_version,
            request_hash=request_hash,
            latency_ms=latency_ms,
        )
        return store.fail_current_job(
            job.public_id,
            error_type="provider_call_failed",
            error_message=str(exc),
        )
    latency_ms = int((perf_counter() - started_at) * 1000)
    if completion.resolved_model is not None:
        job = store.update_reproducibility_meta(
            job.public_id,
            resolved_model_report=completion.resolved_model,
        )
    store.record_llm_call(
        job.public_id,
        prompt_kind="report",
        provider="openrouter",
        requested_model=requested_model,
        resolved_model=completion.resolved_model,
        prompt_version=job.prompt_version,
        request_hash=request_hash,
        response_hash=_hash_text(completion.content),
        latency_ms=latency_ms,
        input_tokens=completion.input_tokens,
        output_tokens=completion.output_tokens,
        finish_reason=completion.finish_reason,
        error_type=None,
    )
    emit_cloud_logging_event(
        logger,
        event="monthly_report.provider_succeeded",
        severity="INFO",
        job_id=job.public_id,
        stage="call_llm",
        prompt_kind="report",
        provider="openrouter",
        requested_model=requested_model,
        resolved_model=completion.resolved_model,
        prompt_version=job.prompt_version,
        request_hash=request_hash,
        response_hash=_hash_text(completion.content),
        latency_ms=latency_ms,
        input_tokens=completion.input_tokens,
        output_tokens=completion.output_tokens,
        finish_reason=completion.finish_reason,
    )
    job = store.complete_current_stage(job.public_id)

    draft = completion.content.strip()
    if not draft:
        store.record_validation(
            job.public_id,
            rule_id="non_empty_markdown",
            severity="error",
            message="draft markdown is empty",
            path="artifact.markdown",
        )
        _emit_validation_failed_log(
            job_id=job.public_id,
            rule_id="non_empty_markdown",
        )
        return store.fail_current_job(
            job.public_id,
            error_type="validation_failed",
            error_message="draft markdown is empty",
        )

    excluded_scope = _find_excluded_scope_mention(draft, job.prompt_scope_notes)
    if excluded_scope:
        message = f"draft mentions excluded scope: {excluded_scope}"
        store.record_validation(
            job.public_id,
            rule_id="multistudent_scope_exclusion",
            severity="error",
            message=message,
            path="artifact.markdown",
        )
        _emit_validation_failed_log(
            job_id=job.public_id,
            rule_id="multistudent_scope_exclusion",
        )
        return store.fail_current_job(
            job.public_id,
            error_type="validation_failed",
            error_message=message,
        )

    if _find_prompt_injection_phrases(draft):
        message = "draft contains prompt-injection phrase"
        store.record_validation(
            job.public_id,
            rule_id="prompt_injection_phrase",
            severity="error",
            message=message,
            path="artifact.markdown",
        )
        _emit_validation_failed_log(
            job_id=job.public_id,
            rule_id="prompt_injection_phrase",
        )
        return store.fail_current_job(
            job.public_id,
            error_type="validation_failed",
            error_message=message,
        )

    if _find_internal_memo_exposure_terms(draft):
        message = "draft exposes internal/admin memo"
        store.record_validation(
            job.public_id,
            rule_id="internal_memo_exposure",
            severity="error",
            message=message,
            path="artifact.markdown",
        )
        _emit_validation_failed_log(
            job_id=job.public_id,
            rule_id="internal_memo_exposure",
        )
        return store.fail_current_job(
            job.public_id,
            error_type="validation_failed",
            error_message=message,
        )

    missing_headings = _find_missing_required_headings(draft, template_path)
    if missing_headings:
        missing_text = ", ".join(missing_headings)
        message = f"draft is missing required headings: {missing_text}"
        store.record_validation(
            job.public_id,
            rule_id="required_headings",
            severity="error",
            message=message,
            path="artifact.markdown",
        )
        _emit_validation_failed_log(
            job_id=job.public_id,
            rule_id="required_headings",
        )
        return store.fail_current_job(
            job.public_id,
            error_type="validation_failed",
            error_message=message,
        )

    draft, sanitized = _sanitize_draft(draft)
    if sanitized:
        store.record_validation(
            job.public_id,
            rule_id="forbidden_terms_sanitized",
            severity="info",
            message=f"forbidden terms auto-replaced before validation: {', '.join(sanitized)}",
            path="artifact.markdown",
        )

    forbidden_terms = _find_forbidden_terms(draft)
    if forbidden_terms:
        message = f"draft contains forbidden terms: {', '.join(forbidden_terms)}"
        store.record_validation(
            job.public_id,
            rule_id="forbidden_terms",
            severity="error",
            message=message,
            path="artifact.markdown",
        )
        _emit_validation_failed_log(
            job_id=job.public_id,
            rule_id="forbidden_terms",
        )
        return store.fail_current_job(
            job.public_id,
            error_type="validation_failed",
            error_message=message,
        )

    store.record_validation(
        job.public_id,
        rule_id="non_empty_markdown",
        severity="info",
        message="draft markdown is not empty",
        path="artifact.markdown",
    )
    job = store.complete_current_stage(job.public_id)

    store.record_artifact(
        job.public_id,
        artifact_type="draft_markdown" if artifact == "md" else "draft_html",
        content=draft,
        content_hash=f"sha256:{sha256(draft.encode('utf-8')).hexdigest()}",
    )
    return store.complete_current_stage(job.public_id)


def _emit_validation_failed_log(
    *,
    job_id: str,
    rule_id: str,
) -> None:
    emit_cloud_logging_event(
        logger,
        event="monthly_report.validation_failed",
        severity="WARNING",
        job_id=job_id,
        stage="validate",
        rule_id=rule_id,
        error_type="validation_failed",
    )


def _bundle_sources(sources: object) -> str:
    chunks: list[str] = []
    for source in sources:
        name = source.display_name or source.source_type
        text = (source.snapshot_text or "").strip()
        if text:
            chunks.append(f"## {name}\n{text}")
    return "\n\n".join(chunks)


def _hash_messages(messages: list[Message]) -> str:
    serialized = "\n".join(f"{message['role']}\n{message['content']}" for message in messages)
    return _hash_text(serialized)


def _hash_text(text: str) -> str:
    return f"sha256:{sha256(text.encode('utf-8')).hexdigest()}"


def _hash_template(template_path: Path) -> str:
    return _hash_text(template_path.read_text(encoding="utf-8"))


def _find_excluded_scope_mention(draft: str, prompt_scope_notes: str | None) -> str | None:
    notes = (prompt_scope_notes or "").strip()
    if not notes:
        return None
    excluded_tokens = re.findall(r"対象外[^\s、。．,.\n]{1,40}?様", notes)
    for token in excluded_tokens:
        if token in draft:
            return token
    return None


def _find_prompt_injection_phrases(draft: str) -> list[str]:
    normalized = draft.lower()
    return [phrase for phrase in PROMPT_INJECTION_PHRASES if phrase.lower() in normalized]


def _find_internal_memo_exposure_terms(draft: str) -> list[str]:
    normalized = draft.lower()
    return [term for term in INTERNAL_MEMO_EXPOSURE_TERMS if term.lower() in normalized]


def _find_missing_required_headings(draft: str, template_path: Path) -> list[str]:
    template = template_path.read_text(encoding="utf-8", errors="replace")
    required = re.findall(r"^##\s+(\d{2}\s+[^\n]+)", template, flags=re.MULTILINE)
    if not required:
        return []
    draft_headings = set(
        re.findall(r"^##\s+(\d{2}\s+[^\n]+)", draft, flags=re.MULTILINE)
    )
    return [f"## {heading}" for heading in required if heading not in draft_headings]


def _sanitize_draft(draft: str) -> tuple[str, list[str]]:
    """Apply deterministic safe replacements for forbidden distribution terms.

    Returns (sanitized_draft, list_of_replaced_terms). Records which terms were
    replaced so the caller can log an info-level validation entry.
    """
    replaced: list[str] = []
    for term, replacement in FORBIDDEN_TERM_SAFE_REPLACEMENTS.items():
        if term in draft:
            draft = draft.replace(term, replacement)
            replaced.append(term)
    return draft, replaced


def _find_forbidden_terms(draft: str) -> list[str]:
    return [term for term in FORBIDDEN_DISTRIBUTION_TERMS if term in draft]
