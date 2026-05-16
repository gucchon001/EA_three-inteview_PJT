from __future__ import annotations

import io
import json
import logging
from pathlib import Path

from eb_app.monthly_reports.jobs import MockJobStore
from eb_app.monthly_reports.observability import (
    build_cloud_logging_payload,
    emit_cloud_logging_event,
)
from eb_app.monthly_reports.workflow import (
    ProviderCallError,
    StaticMonthlyReportProvider,
    run_monthly_report_job,
)


def test_cloud_logging_payload_uses_allowlist_and_excludes_pii_and_secrets():
    payload = build_cloud_logging_payload(
        event="monthly_report.provider_failed",
        severity="ERROR",
        job_id="mrj_demo",
        stage="call_llm",
        error_type="provider_call_failed",
        request_hash="sha256:request",
        response_hash="sha256:response",
        latency_ms=1234,
        prompt_text="生徒Aの電話番号 090-0000-0000",
        source_text="面談本文に個人情報",
        access_token="ya29.secret",
        refresh_token="1//secret",
        api_key="sk-secret",
        client_secret="google-client-secret",
        error_message="provider echoed 生徒A and sk-secret",
        google_response_body="raw body includes 090-1111-2222",
    )

    encoded = json.dumps(payload, ensure_ascii=False)

    assert payload == {
        "event": "monthly_report.provider_failed",
        "severity": "ERROR",
        "component": "monthly_report_workshop",
        "job_id": "mrj_demo",
        "stage": "call_llm",
        "error_type": "provider_call_failed",
        "request_hash": "sha256:request",
        "response_hash": "sha256:response",
        "latency_ms": 1234,
    }
    assert "090-" not in encoded
    assert "生徒A" not in encoded
    assert "sk-secret" not in encoded
    assert "ya29.secret" not in encoded
    assert "1//secret" not in encoded
    assert "google-client-secret" not in encoded
    assert "raw body" not in encoded


def test_cloud_logging_actual_emitted_json_excludes_pii_and_secrets():
    stream = io.StringIO()
    logger = logging.getLogger("tests.monthly_report_cloud_logging")
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

    emit_cloud_logging_event(
        logger,
        event="monthly_report.validation_failed",
        severity="WARNING",
        job_id="mrj_demo",
        stage="validate",
        rule_id="required_headings",
        error_type="validation_failed",
        prompt_version="monthly-report-poc-v1",
        content_hash="sha256:draft",
        draft_markdown="生徒A 090-2222-3333",
        source_snapshot="家庭向けに出してはいけない本文",
        error_message="draft includes 生徒A 090-2222-3333",
    )

    log_line = stream.getvalue().strip()
    emitted = json.loads(log_line)

    assert emitted["event"] == "monthly_report.validation_failed"
    assert emitted["severity"] == "WARNING"
    assert emitted["job_id"] == "mrj_demo"
    assert emitted["rule_id"] == "required_headings"
    assert emitted["content_hash"] == "sha256:draft"
    assert "draft_markdown" not in emitted
    assert "source_snapshot" not in emitted
    assert "error_message" not in emitted
    assert "生徒A" not in log_line
    assert "090-2222-3333" not in log_line


def test_workflow_provider_failure_emits_safe_cloud_logging_json(caplog):
    class FailingProvider:
        def complete(self, *, messages, model=None):
            raise ProviderCallError("upstream echoed 生徒A 090-4444-5555 sk-secret")

    store = MockJobStore()
    job = store.create_job(
        target_month="2026-04",
        household_key="household-log",
        owner_user_id="mock-user@tomonokai-corp.com",
        model_report="mock/report-model",
    )
    store.record_source(
        job.public_id,
        source_type="doc",
        display_name="面談メモ",
        snapshot_text="生徒A 090-4444-5555",
    )

    with caplog.at_level(logging.ERROR, logger="eb_app.monthly_reports.workflow"):
        failed = run_monthly_report_job(
            store,
            job.public_id,
            provider=FailingProvider(),
            template_path=Path("docs/samples/monthly-reports/monthly_pattern_b_content.template.md"),
        )

    assert failed.error_type == "provider_call_failed"
    log_output = "\n".join(record.getMessage() for record in caplog.records)
    assert "monthly_report.provider_failed" in log_output
    assert "request_hash" in log_output
    assert "生徒A" not in log_output
    assert "090-4444-5555" not in log_output
    assert "sk-secret" not in log_output


def test_workflow_validation_failure_emits_safe_cloud_logging_json(caplog):
    store = MockJobStore()
    job = store.create_job(
        target_month="2026-04",
        household_key="household-log-validation",
        owner_user_id="mock-user@tomonokai-corp.com",
    )
    pii_draft = "生徒A 090-6666-7777。本文はあるが必須見出しはない。"

    with caplog.at_level(logging.WARNING, logger="eb_app.monthly_reports.workflow"):
        failed = run_monthly_report_job(
            store,
            job.public_id,
            provider=StaticMonthlyReportProvider(content=pii_draft),
            template_path=Path("docs/samples/monthly-reports/monthly_pattern_b_content.template.md"),
        )

    assert failed.error_type == "validation_failed"
    log_output = "\n".join(record.getMessage() for record in caplog.records)
    assert "monthly_report.validation_failed" in log_output
    assert "required_headings" in log_output
    assert "生徒A" not in log_output
    assert "090-6666-7777" not in log_output
