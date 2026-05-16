from __future__ import annotations

import json
import logging
from typing import Any


_ALLOWED_EXTRA_FIELDS = frozenset(
    {
        "app_version",
        "content_hash",
        "duration_ms",
        "error_type",
        "finish_reason",
        "input_tokens",
        "job_id",
        "latency_ms",
        "output_tokens",
        "prompt_kind",
        "prompt_version",
        "provider",
        "request_hash",
        "requested_model",
        "resolved_model",
        "response_hash",
        "rule_id",
        "size_bytes",
        "stage",
        "status",
    }
)


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
