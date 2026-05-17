from __future__ import annotations

import os
from uuid import uuid4

import pytest

psycopg = pytest.importorskip("psycopg")

from eb_app.monthly_reports.jobs import JobStatus
from eb_app.monthly_reports.postgres_store import PostgresJobStore
from eb_app.monthly_reports.worker import (
    WorkerRunStatus,
    run_next_queued_monthly_report_job,
    run_next_queued_monthly_report_job_result,
)
from eb_app.monthly_reports.workflow import ProviderCallError, StaticMonthlyReportProvider


DATABASE_URL = os.environ.get("EB_MONTHLY_REPORT_DATABASE_URL")


pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="EB_MONTHLY_REPORT_DATABASE_URL is not set",
)


@pytest.fixture()
def store():
    assert DATABASE_URL is not None
    owner_prefix = f"pytest-postgres-{uuid4().hex}"
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(
            "delete from public.monthly_report_jobs where created_by like %s",
            (f"{owner_prefix}%",),
        )
    return PostgresJobStore(DATABASE_URL), owner_prefix


def test_postgres_job_store_creates_lists_gets_and_cancels_job(store):
    job_store, owner_prefix = store
    owner = f"{owner_prefix}-owner"

    job = job_store.create_job(
        target_month="2026-04",
        household_key="demo_postgres",
        owner_user_id=owner,
        template_key="pattern_b",
        prompt_version="monthly-report-v20260514.1",
        template_hash="sha256:template-demo",
        model_report="anthropic/claude-sonnet-4.6",
        model_light="openai/gpt-4.1-mini",
        resolved_model_report="anthropic/claude-sonnet-4.6",
        source_bundle_hash="sha256:bundle-demo",
        app_version="test-sha",
        prompt_scope_notes="対象は平林様 Economics のみ",
    )

    assert job.public_id.startswith("mrj_")
    assert job.status == JobStatus.QUEUED
    assert job.owner_user_id == owner

    listed = job_store.list_jobs()
    assert any(j.public_id == job.public_id for j in listed)

    fetched = job_store.get(job.public_id)
    assert fetched.target_month == "2026-04"
    assert fetched.household_key == "demo_postgres"
    assert fetched.template_key == "pattern_b"
    assert fetched.prompt_version == "monthly-report-v20260514.1"
    assert fetched.template_hash == "sha256:template-demo"
    assert fetched.model_report == "anthropic/claude-sonnet-4.6"
    assert fetched.model_light == "openai/gpt-4.1-mini"
    assert fetched.resolved_model_report == "anthropic/claude-sonnet-4.6"
    assert fetched.source_bundle_hash == "sha256:bundle-demo"
    assert fetched.app_version == "test-sha"
    assert fetched.prompt_scope_notes == "対象は平林様 Economics のみ"

    cancelled = job_store.request_cancel(job.public_id)
    assert cancelled.status == JobStatus.CANCELLED
    assert job_store.count_active_jobs(owner) == 0


def test_postgres_job_store_persists_idempotent_job_lookup(store):
    job_store, owner_prefix = store
    owner = f"{owner_prefix}-idempotent-owner"
    job = job_store.create_job(
        target_month="2026-04",
        household_key="demo_postgres_idempotent",
        owner_user_id=owner,
    )

    assert job_store.get_idempotent_job("create_job", owner, "idem-key") is None

    job_store.remember_idempotent_job("create_job", owner, "idem-key", job.public_id)
    remembered = job_store.get_idempotent_job("create_job", owner, "idem-key")
    other_owner = job_store.get_idempotent_job("create_job", f"{owner}-other", "idem-key")

    assert remembered is not None
    assert remembered.public_id == job.public_id
    assert other_owner is None


def test_postgres_job_store_persists_idempotent_response_lookup(store):
    job_store, owner_prefix = store
    owner = f"{owner_prefix}-idempotent-response-owner"
    response = {
        "job_id": "mrj_response",
        "status": "succeeded",
        "nested": {"ok": True},
    }

    assert job_store.get_idempotent_response("run-mock:mrj_response", owner, "idem-key") is None

    job_store.remember_idempotent_response(
        "run-mock:mrj_response",
        owner,
        "idem-key",
        response,
    )
    remembered = job_store.get_idempotent_response(
        "run-mock:mrj_response",
        owner,
        "idem-key",
    )

    assert remembered == response


def test_postgres_job_store_records_feedback_and_reruns_job(store):
    job_store, owner_prefix = store
    owner = f"{owner_prefix}-owner"
    job = job_store.create_job(
        target_month="2026-04",
        household_key="demo_postgres_feedback",
        owner_user_id=owner,
        template_key="pattern_b",
        prompt_version="monthly-report-v20260514.1",
        template_hash="sha256:template-demo",
        model_report="anthropic/claude-sonnet-4.6",
        model_light="openai/gpt-4.1-mini",
        resolved_model_report="anthropic/claude-sonnet-4.6",
        source_bundle_hash="sha256:bundle-demo",
        app_version="test-sha",
        prompt_scope_notes="対象は平林様 Economics のみ",
    )

    feedback = job_store.record_feedback(
        job.public_id,
        category="tone",
        comment="保護者向けにやや硬い",
    )

    assert feedback.public_id.startswith("mrf_")
    assert feedback.job_id == job.public_id
    assert job_store.get(job.public_id).feedback == [feedback]

    rerun = job_store.rerun_job(job.public_id)

    assert rerun.public_id != job.public_id
    assert rerun.status == JobStatus.QUEUED
    assert rerun.target_month == job.target_month
    assert rerun.household_key == job.household_key
    assert rerun.owner_user_id == owner
    assert rerun.template_key == job.template_key
    assert rerun.prompt_version == job.prompt_version
    assert rerun.template_hash == job.template_hash
    assert rerun.model_report == job.model_report
    assert rerun.model_light == job.model_light
    assert rerun.resolved_model_report == job.resolved_model_report
    assert rerun.source_bundle_hash == job.source_bundle_hash
    assert rerun.app_version == job.app_version
    assert rerun.prompt_scope_notes == job.prompt_scope_notes


def test_postgres_job_store_records_source_snapshot_and_artifact(store):
    job_store, owner_prefix = store
    owner = f"{owner_prefix}-owner"
    job = job_store.create_job(
        target_month="2026-04",
        household_key="demo_postgres_persistence",
        owner_user_id=owner,
    )

    source = job_store.record_source(
        job.public_id,
        source_type="doc",
        display_name="面談メモ",
        snapshot_text="4月の学習記録",
        content_hash="sha256:source-demo",
    )

    assert source.public_id.startswith("mrs_")
    assert source.job_id == job.public_id
    assert source.display_name == "面談メモ"
    assert job_store.list_sources(job.public_id) == [source]

    artifact = job_store.record_artifact(
        job.public_id,
        artifact_type="draft_markdown",
        content="# 4月度 月次レポート",
        content_hash="sha256:artifact-demo",
    )

    assert artifact.public_id.startswith("mra_")
    assert artifact.job_id == job.public_id
    assert artifact.artifact_type == "draft_markdown"
    assert job_store.list_artifacts(job.public_id) == [artifact]


def test_postgres_job_store_records_validation_result(store):
    job_store, owner_prefix = store
    owner = f"{owner_prefix}-owner"
    job = job_store.create_job(
        target_month="2026-04",
        household_key="demo_postgres_validation",
        owner_user_id=owner,
    )

    validation = job_store.record_validation(
        job.public_id,
        rule_id="required-heading",
        severity="error",
        message="学習の進捗セクションがありません",
        path="sections.learning_progress",
    )

    assert validation.public_id.startswith("mrv_")
    assert validation.job_id == job.public_id
    assert validation.rule_id == "required-heading"
    assert validation.severity == "error"
    assert job_store.list_validations(job.public_id) == [validation]


def test_postgres_job_store_records_llm_call_log(store):
    job_store, owner_prefix = store
    owner = f"{owner_prefix}-owner"
    job = job_store.create_job(
        target_month="2026-04",
        household_key="demo_postgres_llm",
        owner_user_id=owner,
        prompt_version="monthly-report-v20260514.1",
    )

    call = job_store.record_llm_call(
        job.public_id,
        prompt_kind="report",
        provider="openrouter",
        requested_model="openrouter/auto",
        resolved_model="anthropic/claude-sonnet-4.6",
        prompt_version=job.prompt_version,
        request_hash="sha256:req",
        response_hash="sha256:res",
        latency_ms=1234,
        input_tokens=111,
        output_tokens=222,
        finish_reason="stop",
        error_type=None,
    )

    assert call.public_id.startswith("llm_")
    assert call.job_id == job.public_id
    assert call.requested_model == "openrouter/auto"
    assert call.resolved_model == "anthropic/claude-sonnet-4.6"
    assert call.prompt_version == "monthly-report-v20260514.1"
    assert call.request_hash == "sha256:req"
    assert call.response_hash == "sha256:res"
    assert call.latency_ms == 1234
    assert call.input_tokens == 111
    assert call.output_tokens == 222
    assert call.finish_reason == "stop"
    assert call.error_type is None
    assert job_store.list_llm_calls(job.public_id) == [call]


def test_postgres_job_store_advances_and_fails_jobs(store):
    job_store, owner_prefix = store
    owner = f"{owner_prefix}-owner"

    advancing_job = job_store.create_job(
        target_month="2026-04",
        household_key="demo_postgres_pipeline",
        owner_user_id=owner,
    )

    started = job_store.start_next(advancing_job.public_id)
    assert started.status == JobStatus.RUNNING
    assert started.current_stage == "fetch_sources"

    completed = job_store.complete_current_stage(advancing_job.public_id)
    assert completed.status == JobStatus.RUNNING
    assert completed.current_stage == "bundle"

    failing_job = job_store.create_job(
        target_month="2026-04",
        household_key="demo_postgres_fail",
        owner_user_id=owner,
    )
    job_store.start_next(failing_job.public_id)

    failed = job_store.fail_current_job(
        failing_job.public_id,
        error_type="provider_timeout",
        error_message="OpenRouter timed out",
    )

    assert failed.status == JobStatus.FAILED
    assert failed.current_stage == "fetch_sources"
    assert failed.error_type == "provider_timeout"
    assert failed.error_message == "OpenRouter timed out"

    fetched = job_store.get(failing_job.public_id)
    assert fetched.status == JobStatus.FAILED
    assert fetched.current_stage == "fetch_sources"
    assert fetched.error_type == "provider_timeout"
    assert fetched.error_message == "OpenRouter timed out"

    with psycopg.connect(DATABASE_URL) as conn:
        row = conn.execute(
            """
            select error_type, error_message
            from public.monthly_report_jobs
            where public_id = %s
            """,
            (failing_job.public_id,),
        ).fetchone()

    assert row == ("provider_timeout", "OpenRouter timed out")


def test_postgres_job_store_claims_next_queued_job_once(store):
    job_store, owner_prefix = store
    owner = f"{owner_prefix}-owner"
    first = job_store.create_job(
        target_month="2026-04",
        household_key="demo_postgres_claim_first",
        owner_user_id=owner,
    )
    second = job_store.create_job(
        target_month="2026-04",
        household_key="demo_postgres_claim_second",
        owner_user_id=owner,
    )

    claimed = job_store.claim_next_queued_job(owner_user_id=owner)
    claimed_again = job_store.claim_next_queued_job(owner_user_id=owner)

    assert claimed is not None
    assert claimed.public_id == first.public_id
    assert claimed.status == JobStatus.RUNNING
    assert claimed.current_stage == "fetch_sources"
    assert claimed_again is not None
    assert claimed_again.public_id == second.public_id
    assert claimed_again.status == JobStatus.RUNNING
    assert job_store.claim_next_queued_job(owner_user_id=owner) is None


def test_postgres_worker_fills_missing_reproducibility_meta(store, tmp_path):
    job_store, owner_prefix = store
    owner = f"{owner_prefix}-worker-meta-owner"
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    job = job_store.create_job(
        target_month="2026-04",
        household_key="demo_postgres_worker_meta",
        owner_user_id=owner,
    )
    job_store.record_source(
        job.public_id,
        source_type="doc",
        display_name="面談メモ",
        snapshot_text="4月の学習記録",
        content_hash="sha256:source-demo",
    )
    provider = StaticMonthlyReportProvider(
        "# 4月度 月次レポート\n\n本文です。",
        resolved_model="postgres/resolved-model",
    )

    result = run_next_queued_monthly_report_job(
        job_store,
        provider=provider,
        template_path=template,
        owner_user_id=owner,
        prompt_version="monthly-report-vpostgres-worker.1",
        model_report="postgres/report-model",
        app_version="postgres-worker-app",
    )

    assert result is not None
    assert result.public_id == job.public_id
    assert result.status == JobStatus.SUCCEEDED
    assert result.prompt_version == "monthly-report-vpostgres-worker.1"
    assert result.template_hash is not None and result.template_hash.startswith("sha256:")
    assert result.model_report == "postgres/report-model"
    assert result.resolved_model_report == "postgres/resolved-model"
    assert result.source_bundle_hash is not None and result.source_bundle_hash.startswith(
        "sha256:"
    )
    assert result.app_version == "postgres-worker-app"
    assert provider.last_model == "postgres/report-model"

    fetched = job_store.get(job.public_id)
    assert fetched.prompt_version == result.prompt_version
    assert fetched.template_hash == result.template_hash
    assert fetched.model_report == result.model_report
    assert fetched.resolved_model_report == result.resolved_model_report
    assert fetched.source_bundle_hash == result.source_bundle_hash
    assert fetched.app_version == result.app_version


class FailingProvider:
    def complete(self, *, messages, model=None):
        raise ProviderCallError("temporary provider failure")


def test_postgres_job_store_claims_stale_fetch_sources_job_with_retry_attempt(store):
    job_store, owner_prefix = store
    owner = f"{owner_prefix}-lease-owner"
    job = job_store.create_job(
        target_month="2026-04",
        household_key="demo_postgres_lease",
        owner_user_id=owner,
    )

    first = job_store.claim_next_runnable_job(owner_user_id=owner)
    assert first is not None
    assert first.public_id == job.public_id
    assert first.worker_attempts == 1

    assert job_store.claim_next_runnable_job(
        owner_user_id=owner,
        lease_timeout_seconds=60,
    ) is None

    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(
            """
            update public.monthly_report_jobs
            set updated_at = now() - interval '2 minutes'
            where public_id = %s
            """,
            (job.public_id,),
        )

    reclaimed = job_store.claim_next_runnable_job(
        owner_user_id=owner,
        lease_timeout_seconds=60,
    )

    assert reclaimed is not None
    assert reclaimed.public_id == job.public_id
    assert reclaimed.status == JobStatus.RUNNING
    assert reclaimed.current_stage == "fetch_sources"
    assert reclaimed.worker_attempts == 2


def test_postgres_job_store_touch_worker_job_prevents_fetch_sources_reclaim(store):
    job_store, owner_prefix = store
    owner = f"{owner_prefix}-heartbeat-owner"
    job = job_store.create_job(
        target_month="2026-04",
        household_key="demo_postgres_heartbeat",
        owner_user_id=owner,
    )

    claimed = job_store.claim_next_runnable_job(owner_user_id=owner)
    assert claimed is not None
    assert claimed.public_id == job.public_id

    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(
            """
            update public.monthly_report_jobs
            set updated_at = now() - interval '2 minutes',
                worker_last_claimed_at = now() - interval '2 minutes'
            where public_id = %s
            """,
            (job.public_id,),
        )

    touched = job_store.touch_worker_job(job.public_id)

    assert touched.status == JobStatus.RUNNING
    assert touched.current_stage == "fetch_sources"
    assert touched.worker_attempts == 1
    assert touched.worker_last_claimed_at is not None
    assert (
        job_store.claim_next_runnable_job(
            owner_user_id=owner,
            lease_timeout_seconds=60,
        )
        is None
    )


def test_postgres_worker_requeues_provider_failure_until_retry_limit(store, tmp_path):
    job_store, owner_prefix = store
    owner = f"{owner_prefix}-retry-owner"
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    job = job_store.create_job(
        target_month="2026-04",
        household_key="demo_postgres_retry",
        owner_user_id=owner,
        max_worker_attempts=2,
    )
    provider = FailingProvider()

    first = run_next_queued_monthly_report_job_result(
        job_store,
        provider=provider,
        template_path=template,
        owner_user_id=owner,
    )
    second = run_next_queued_monthly_report_job_result(
        job_store,
        provider=provider,
        template_path=template,
        owner_user_id=owner,
    )

    assert first.status == WorkerRunStatus.RETRY_SCHEDULED
    assert first.job is not None
    assert first.job.public_id == job.public_id
    assert first.job.status == JobStatus.QUEUED
    assert first.job.worker_attempts == 1
    assert second.status == WorkerRunStatus.FAILED
    assert second.job is not None
    assert second.job.status == JobStatus.FAILED
    assert second.job.worker_attempts == 2
