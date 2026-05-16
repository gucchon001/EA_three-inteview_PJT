import pytest

from eb_app.monthly_reports import ids
from eb_app.monthly_reports.jobs import (
    JobStatus,
    MockJobStore,
    StatusTransitionError,
)


def test_public_id_helpers_apply_expected_prefixes():
    assert ids.new_job_id().startswith("mrj_")
    assert ids.new_source_id().startswith("mrs_")
    assert ids.new_artifact_id().startswith("mra_")
    assert ids.new_validation_id().startswith("mrv_")
    assert ids.new_llm_call_id().startswith("llm_")


def test_public_id_validation_checks_prefix_and_body():
    job_id = ids.new_public_id(ids.PUBLIC_ID_PREFIXES.job)

    assert ids.has_public_id_prefix(job_id, ids.PUBLIC_ID_PREFIXES.job)
    assert not ids.has_public_id_prefix(job_id, ids.PUBLIC_ID_PREFIXES.source)
    assert ids.validate_public_id(job_id, ids.PUBLIC_ID_PREFIXES.job) == job_id

    with pytest.raises(ValueError):
        ids.validate_public_id("mrj_", ids.PUBLIC_ID_PREFIXES.job)

    with pytest.raises(ValueError):
        ids.validate_public_id("mrs_abc", ids.PUBLIC_ID_PREFIXES.job)


def test_job_statuses_include_mvp_cancellation_states():
    assert JobStatus.QUEUED == "queued"
    assert JobStatus.RUNNING == "running"
    assert JobStatus.SUCCEEDED == "succeeded"
    assert JobStatus.FAILED == "failed"
    assert JobStatus.CANCEL_REQUESTED == "cancel_requested"
    assert JobStatus.CANCELLED == "cancelled"


def test_mock_job_store_runs_job_through_stages():
    store = MockJobStore(id_factory=lambda prefix: f"{prefix}_fixed")
    job = store.create_job(target_month="2026-04", household_key="demo")

    assert job.public_id == "mrj_fixed"
    assert job.status == JobStatus.QUEUED

    store.start_next(job.public_id)
    assert store.get(job.public_id).status == JobStatus.RUNNING
    assert store.get(job.public_id).current_stage == "fetch_sources"

    store.complete_current_stage(job.public_id)
    assert store.get(job.public_id).status == JobStatus.RUNNING
    assert store.get(job.public_id).current_stage == "bundle"

    while store.get(job.public_id).status == JobStatus.RUNNING:
        store.complete_current_stage(job.public_id)

    assert store.get(job.public_id).status == JobStatus.SUCCEEDED
    assert store.get(job.public_id).current_stage is None
    assert store.get(job.public_id).completed_stages[-1] == "persist"


def test_mock_job_store_cancels_queued_job_immediately():
    store = MockJobStore(id_factory=lambda prefix: f"{prefix}_queued")
    job = store.create_job(target_month="2026-04", household_key="demo")

    cancelled = store.request_cancel(job.public_id)

    assert cancelled.status == JobStatus.CANCELLED
    assert cancelled.current_stage is None


def test_mock_job_store_uses_cooperative_cancellation_for_running_job():
    store = MockJobStore(id_factory=lambda prefix: f"{prefix}_running")
    job = store.create_job(target_month="2026-04", household_key="demo")
    store.start_next(job.public_id)

    requested = store.request_cancel(job.public_id)

    assert requested.status == JobStatus.CANCEL_REQUESTED
    assert requested.current_stage == "fetch_sources"

    cancelled = store.complete_current_stage(job.public_id)

    assert cancelled.status == JobStatus.CANCELLED
    assert cancelled.current_stage is None
    assert cancelled.completed_stages == ["fetch_sources"]


def test_mock_job_store_rejects_invalid_transitions():
    store = MockJobStore(id_factory=lambda prefix: f"{prefix}_invalid")
    job = store.create_job(target_month="2026-04", household_key="demo")

    with pytest.raises(StatusTransitionError):
        store.complete_current_stage(job.public_id)

    store.request_cancel(job.public_id)

    with pytest.raises(StatusTransitionError):
        store.start_next(job.public_id)


def test_mock_job_store_fails_running_job_with_error_details():
    store = MockJobStore(id_factory=lambda prefix: f"{prefix}_failed")
    job = store.create_job(
        target_month="2026-04",
        household_key="demo",
        owner_user_id="mock-user",
    )
    store.start_next(job.public_id)

    failed = store.fail_current_job(
        job.public_id,
        error_type="provider_timeout",
        error_message="OpenRouter timed out",
    )

    assert failed.status == JobStatus.FAILED
    assert failed.current_stage == "fetch_sources"
    assert failed.error_type == "provider_timeout"
    assert failed.error_message == "OpenRouter timed out"
    assert store.count_active_jobs("mock-user") == 0


def test_mock_job_store_claims_oldest_queued_job_once():
    ids_iter = iter(["mrj_first", "mrj_second"])
    store = MockJobStore(id_factory=lambda _prefix: next(ids_iter))
    first = store.create_job(target_month="2026-04", household_key="first")
    second = store.create_job(target_month="2026-04", household_key="second")

    claimed = store.claim_next_queued_job()
    claimed_again = store.claim_next_queued_job()

    assert claimed is not None
    assert claimed.public_id == first.public_id
    assert claimed.status == JobStatus.RUNNING
    assert claimed.current_stage == "fetch_sources"
    assert claimed_again is not None
    assert claimed_again.public_id == second.public_id
    assert store.claim_next_queued_job() is None


def test_mock_job_store_counts_active_jobs_by_owner_only():
    ids_iter = iter(["mrj_active_1", "mrj_active_2", "mrj_done", "mrj_other"])
    store = MockJobStore(id_factory=lambda _prefix: next(ids_iter))

    first = store.create_job(
        target_month="2026-04",
        household_key="demo",
        owner_user_id="mock-user-a",
    )
    second = store.create_job(
        target_month="2026-04",
        household_key="demo",
        owner_user_id="mock-user-a",
    )
    completed = store.create_job(
        target_month="2026-04",
        household_key="demo",
        owner_user_id="mock-user-a",
    )
    other_owner = store.create_job(
        target_month="2026-04",
        household_key="demo",
        owner_user_id="mock-user-b",
    )

    store.start_next(second.public_id)
    store.start_next(completed.public_id)
    while store.get(completed.public_id).status == JobStatus.RUNNING:
        store.complete_current_stage(completed.public_id)

    assert store.count_active_jobs("mock-user-a") == 2
    assert store.count_active_jobs("mock-user-b") == 1
    assert first.status == JobStatus.QUEUED
    assert other_owner.status == JobStatus.QUEUED


def test_mock_job_store_counts_cancel_requested_as_active_until_cancelled():
    store = MockJobStore(id_factory=lambda prefix: f"{prefix}_cancel_requested")
    job = store.create_job(
        target_month="2026-04",
        household_key="demo",
        owner_user_id="mock-user",
    )
    store.start_next(job.public_id)
    store.request_cancel(job.public_id)

    assert store.count_active_jobs("mock-user") == 1

    store.complete_current_stage(job.public_id)

    assert store.count_active_jobs("mock-user") == 0


def test_mock_job_store_excludes_terminal_statuses_from_active_count():
    ids_iter = iter(["mrj_succeeded", "mrj_failed", "mrj_cancelled"])
    store = MockJobStore(id_factory=lambda _prefix: next(ids_iter))

    succeeded = store.create_job(
        target_month="2026-04",
        household_key="demo",
        owner_user_id="mock-user",
    )
    failed = store.create_job(
        target_month="2026-04",
        household_key="demo",
        owner_user_id="mock-user",
    )
    cancelled = store.create_job(
        target_month="2026-04",
        household_key="demo",
        owner_user_id="mock-user",
    )

    succeeded.status = JobStatus.SUCCEEDED
    failed.status = JobStatus.FAILED
    cancelled.status = JobStatus.CANCELLED

    assert store.count_active_jobs("mock-user") == 0


def test_mock_job_store_records_feedback_for_job():
    store = MockJobStore(id_factory=lambda prefix: f"{prefix}_feedback")
    job = store.create_job(target_month="2026-04", household_key="demo")

    feedback = store.record_feedback(
        job.public_id,
        category="tone",
        comment="保護者向けにやや硬い",
    )

    assert feedback.public_id == "mrf_1"
    assert feedback.job_id == job.public_id
    assert feedback.category == "tone"
    assert feedback.comment == "保護者向けにやや硬い"
    assert store.get(job.public_id).feedback == [feedback]


def test_mock_job_store_reruns_job_from_existing_target_household_and_owner():
    ids_iter = iter(["mrj_original", "mrj_rerun"])
    store = MockJobStore(id_factory=lambda _prefix: next(ids_iter))
    original = store.create_job(
        target_month="2026-04",
        household_key="demo",
        owner_user_id="owner-rerun",
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

    rerun = store.rerun_job(original.public_id)

    assert rerun.public_id == "mrj_rerun"
    assert rerun.status == JobStatus.QUEUED
    assert rerun.target_month == original.target_month
    assert rerun.household_key == original.household_key
    assert rerun.owner_user_id == original.owner_user_id
    assert rerun.template_key == original.template_key
    assert rerun.prompt_version == original.prompt_version
    assert rerun.template_hash == original.template_hash
    assert rerun.model_report == original.model_report
    assert rerun.model_light == original.model_light
    assert rerun.resolved_model_report == original.resolved_model_report
    assert rerun.source_bundle_hash == original.source_bundle_hash
    assert rerun.app_version == original.app_version
    assert rerun.prompt_scope_notes == original.prompt_scope_notes


def test_mock_job_store_records_llm_call_log_for_job():
    ids_iter = iter(["mrj_llm", "llm_call"])
    store = MockJobStore(id_factory=lambda _prefix: next(ids_iter))
    job = store.create_job(
        target_month="2026-04",
        household_key="demo",
        prompt_version="monthly-report-v20260514.1",
    )

    call = store.record_llm_call(
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

    assert call.public_id == "llm_call"
    assert call.job_id == job.public_id
    assert call.prompt_kind == "report"
    assert call.provider == "openrouter"
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
    assert store.list_llm_calls(job.public_id) == [call]
