from __future__ import annotations

import json
import logging
from typing import Any


_ALLOWED_EXTRA_FIELDS = frozenset(
    {
        "app_version",
        "content_hash",
        "daily_budget_usd",
        "duration_ms",
        "error_type",
        "estimated_cost_usd",
        "finish_reason",
        "http_status",
        "input_tokens",
        "job_id",
        "latency_ms",
        "method",
        "output_tokens",
        "prompt_kind",
        "prompt_version",
        "provider",
        "quota_service",
        "request_hash",
        "requested_model",
        "resolved_model",
        "response_hash",
        "route",
        "rule_id",
        "size_bytes",
        "stage",
        "status",
        "total_cost_usd",
        "total_tokens",
        "worker_attempts",
    }
)

LOG_BASED_METRIC_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "metric_name": "monthly_report_worker_failed_count",
        "metric_type": "logging.googleapis.com/user/monthly_report_worker_failed_count",
        "value_type": "INT64",
        "metric_kind": "DELTA",
        "labels": ("stage", "error_type", "resolved_model", "prompt_version"),
        "filter": (
            '(resource.type="cloud_run_revision" OR resource.type="cloud_run_job")\n'
            'jsonPayload.component="monthly_report_workshop"\n'
            '(jsonPayload.event="monthly_report.provider_failed" OR '
            'jsonPayload.event="monthly_report.validation_failed")'
        ),
    },
    {
        "metric_name": "monthly_report_llm_token_count",
        "metric_type": "logging.googleapis.com/user/monthly_report_llm_token_count",
        "value_type": "INT64",
        "metric_kind": "DELTA",
        "labels": ("provider", "resolved_model", "prompt_kind", "prompt_version"),
        "filter": (
            '(resource.type="cloud_run_revision" OR resource.type="cloud_run_job")\n'
            'jsonPayload.component="monthly_report_workshop"\n'
            'jsonPayload.event="monthly_report.provider_succeeded"\n'
            'jsonPayload.total_tokens>0'
        ),
    },
    {
        "metric_name": "monthly_report_openrouter_error_count",
        "metric_type": "logging.googleapis.com/user/monthly_report_openrouter_error_count",
        "value_type": "INT64",
        "metric_kind": "DELTA",
        "labels": ("provider", "resolved_model", "error_type", "http_status"),
        "filter": (
            '(resource.type="cloud_run_revision" OR resource.type="cloud_run_job")\n'
            'jsonPayload.component="monthly_report_workshop"\n'
            'jsonPayload.event="monthly_report.provider_failed"'
        ),
    },
    {
        "metric_name": "monthly_report_google_api_error_count",
        "metric_type": "logging.googleapis.com/user/monthly_report_google_api_error_count",
        "value_type": "INT64",
        "metric_kind": "DELTA",
        "labels": ("quota_service", "error_type", "http_status", "stage"),
        "filter": (
            '(resource.type="cloud_run_revision" OR resource.type="cloud_run_job")\n'
            'jsonPayload.component="monthly_report_workshop"\n'
            'jsonPayload.event="monthly_report.google_api_failed"'
        ),
    },
    {
        "metric_name": "monthly_report_auth_guardrail_reject_count",
        "metric_type": "logging.googleapis.com/user/monthly_report_auth_guardrail_reject_count",
        "value_type": "INT64",
        "metric_kind": "DELTA",
        "labels": ("route", "method", "http_status", "error_type"),
        "filter": (
            'resource.type="cloud_run_revision"\n'
            'jsonPayload.component="monthly_report_workshop"\n'
            'jsonPayload.event="monthly_report.auth_guardrail_rejected"\n'
            'jsonPayload.http_status=(403 OR 429)'
        ),
    },
)

DAILY_LLM_COST_SUMMARY_CONTRACT: dict[str, Any] = {
    "event": "monthly_report.llm_cost_daily_summary",
    "required_fields": (
        "summary_date",
        "job_count",
        "llm_call_count",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "estimated_cost_usd",
        "daily_budget_usd",
        "budget_ratio",
        "model_breakdown",
        "prompt_version_breakdown",
        "top_job_ids_by_tokens",
    ),
    "pii_forbidden_fields": (
        "household_key",
        "user_email",
        "source_text",
        "prompt_text",
        "draft_markdown",
        "provider_request_body",
        "provider_response_body",
        "api_key",
        "access_token",
        "refresh_token",
    ),
}


def build_cloud_logging_payload(
    *,
    event: str,
    severity: str = "INFO",
    **fields: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event": event,
        "severity": severity.upper(),
        "component": "monthly_report_workshop",
    }
    for key, value in fields.items():
        if key in _ALLOWED_EXTRA_FIELDS and value is not None:
            payload[key] = value
    return payload


def emit_cloud_logging_event(
    logger: logging.Logger,
    *,
    event: str,
    severity: str = "INFO",
    **fields: Any,
) -> None:
    payload = build_cloud_logging_payload(
        event=event,
        severity=severity,
        **fields,
    )
    logger.log(_severity_to_level(severity), json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _severity_to_level(severity: str) -> int:
    return {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "NOTICE": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }.get(severity.upper(), logging.INFO)
