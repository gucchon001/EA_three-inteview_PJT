from __future__ import annotations

from eb_app.config import Settings
from eb_app.monthly_reports.jobs import JobStatus, MockJob
from eb_app.monthly_reports.worker import WorkerRunResult, WorkerRunStatus
from eb_app.monthly_reports import worker_entry


def _settings(**overrides) -> Settings:
    values = {
        "enable_mock_ui": False,
        "auth_mode": "supabase",
        "env": "test",
        "monthly_report_database_url": "postgresql://example",
        "monthly_report_prompt_version": "monthly-report-v20260517.1",
        "app_version": "test-sha",
        "openrouter_api_key": "sk-test",
        "openrouter_model_report": "mock/model",
        "openrouter_model_light": "mock/light-model",
        "openrouter_timeout_seconds": 30.0,
        "openrouter_max_tokens": 1000,
        "cloud_run_worker_job_project_id": None,
        "cloud_run_worker_job_region": None,
        "cloud_run_worker_job_name": None,
        "cloud_run_worker_trigger_access_token": None,
        "cloud_run_worker_trigger_timeout_seconds": 15.0,
        "google_workspace_access_token": None,
        "google_oauth_client_id": None,
        "google_oauth_client_secret": None,
        "google_token_encryption_key": None,
        "google_token_encryption_key_version": "test-v1",
        "supabase_url": None,
        "supabase_anon_key": None,
        "google_oauth_scopes": "openid email",
        "supabase_jwt_secret": None,
        "supabase_jwt_audience": "authenticated",
        "allowed_email_domain": "tomonokai-corp.com",
    }
    values.update(overrides)
    return Settings(**values)


def test_run_worker_once_requires_database_url():
    try:
        worker_entry.run_worker_once(
            settings=_settings(monthly_report_database_url=None),
        )
    except RuntimeError as exc:
        assert "EB_MONTHLY_REPORT_DATABASE_URL" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_run_worker_once_requires_openrouter_api_key():
    try:
        worker_entry.run_worker_once(settings=_settings(openrouter_api_key=None))
    except RuntimeError as exc:
        assert "OPENROUTER_API_KEY" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_run_worker_batch_stops_on_no_job(monkeypatch):
    calls = []

    def fake_run_worker_once(**kwargs):
        calls.append(kwargs)
        return WorkerRunResult(status=WorkerRunStatus.NO_JOB)

    monkeypatch.setattr(worker_entry, "run_worker_once", fake_run_worker_once)

    results = worker_entry.run_worker_batch(
        max_jobs=3,
        sleep_seconds=0,
        owner_user_id="owner-a",
        lease_timeout_seconds=120,
        settings=_settings(),
    )

    assert [result.status for result in results] == [WorkerRunStatus.NO_JOB]
    assert calls[0]["public_id"] is None
    assert calls[0]["owner_user_id"] == "owner-a"
    assert calls[0]["lease_timeout_seconds"] == 120


def test_run_worker_batch_passes_job_id(monkeypatch):
    calls = []

    def fake_run_worker_once(**kwargs):
        calls.append(kwargs)
        return WorkerRunResult(status=WorkerRunStatus.NO_JOB)

    monkeypatch.setattr(worker_entry, "run_worker_once", fake_run_worker_once)

    worker_entry.run_worker_batch(
        max_jobs=1,
        sleep_seconds=0,
        public_id="mrj_targeted",
        settings=_settings(),
    )

    assert calls[0]["public_id"] == "mrj_targeted"


def test_worker_result_summary_excludes_error_message():
    job = MockJob(
        public_id="mrj_worker_entry",
        target_month="2026-04",
        household_key="household",
        owner_user_id="owner",
        status=JobStatus.FAILED,
        error_type="provider_call_failed",
        error_message="private provider body",
    )
    result = WorkerRunResult(
        status=WorkerRunStatus.FAILED,
        claimed_job_id=job.public_id,
        job=job,
        error_type=job.error_type,
        error_message=job.error_message,
    )

    summary = worker_entry.worker_result_summary(result)

    assert summary == {
        "status": WorkerRunStatus.FAILED,
        "claimed_job_id": "mrj_worker_entry",
        "job_id": "mrj_worker_entry",
        "job_status": JobStatus.FAILED,
        "job_stage": None,
        "error_type": "provider_call_failed",
        "manual_recovery_job_count": 0,
        "manual_recovery_stages": None,
    }
    assert "private provider body" not in str(summary)


def test_worker_result_summary_includes_manual_recovery_without_error_message():
    job = MockJob(
        public_id="mrj_manual_recovery",
        target_month="2026-04",
        household_key="household",
        owner_user_id="owner",
        status=JobStatus.RUNNING,
        current_stage="call_llm",
        error_message="private provider body",
    )
    result = WorkerRunResult(
        status=WorkerRunStatus.MANUAL_RECOVERY_REQUIRED,
        job=job,
        error_type="manual_recovery_required",
        error_message=job.error_message,
        manual_recovery_job_count=2,
        manual_recovery_stages=("call_llm", "validate"),
    )

    summary = worker_entry.worker_result_summary(result)

    assert summary == {
        "status": WorkerRunStatus.MANUAL_RECOVERY_REQUIRED,
        "claimed_job_id": None,
        "job_id": "mrj_manual_recovery",
        "job_status": JobStatus.RUNNING,
        "job_stage": "call_llm",
        "error_type": "manual_recovery_required",
        "manual_recovery_job_count": 2,
        "manual_recovery_stages": "call_llm,validate",
    }
    assert "private provider body" not in str(summary)


def test_run_worker_batch_stops_on_manual_recovery_required(monkeypatch):
    calls = []

    def fake_run_worker_once(**kwargs):
        calls.append(kwargs)
        return WorkerRunResult(status=WorkerRunStatus.MANUAL_RECOVERY_REQUIRED)

    monkeypatch.setattr(worker_entry, "run_worker_once", fake_run_worker_once)

    results = worker_entry.run_worker_batch(
        max_jobs=0,
        sleep_seconds=0,
        settings=_settings(),
    )

    assert [result.status for result in results] == [
        WorkerRunStatus.MANUAL_RECOVERY_REQUIRED
    ]
    assert len(calls) == 1


def test_main_returns_nonzero_when_any_worker_run_failed(monkeypatch, capsys):
    def fake_run_worker_batch(**kwargs):
        return [WorkerRunResult(status=WorkerRunStatus.FAILED, error_type="boom")]

    monkeypatch.setattr(worker_entry, "run_worker_batch", fake_run_worker_batch)

    exit_code = worker_entry.main(["--max-jobs", "1"])

    assert exit_code == 1
    assert "boom" in capsys.readouterr().out


def test_main_returns_nonzero_when_manual_recovery_required(monkeypatch, capsys):
    def fake_run_worker_batch(**kwargs):
        return [
            WorkerRunResult(
                status=WorkerRunStatus.MANUAL_RECOVERY_REQUIRED,
                error_type="manual_recovery_required",
                manual_recovery_job_count=1,
                manual_recovery_stages=("call_llm",),
            )
        ]

    monkeypatch.setattr(worker_entry, "run_worker_batch", fake_run_worker_batch)

    exit_code = worker_entry.main(["--max-jobs", "1"])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "manual_recovery_required" in output
    assert "call_llm" in output
