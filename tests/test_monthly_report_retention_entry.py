from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from eb_app.config import Settings
from eb_app.monthly_reports.retention import (
    RETENTION_TARGETS,
    RetentionPlan,
    RetentionPlanItem,
)
from eb_app.monthly_reports import retention_entry


@dataclass
class FakeRepository:
    database_url: str


class FakeExecutor:
    calls: list[dict] = []
    eligible_count = 2

    def __init__(self, repository: FakeRepository, *, actor_id: str) -> None:
        self.repository = repository
        self.actor_id = actor_id

    def run(self, *, dry_run: bool) -> RetentionPlan:
        self.calls.append(
            {
                "database_url": self.repository.database_url,
                "actor_id": self.actor_id,
                "dry_run": dry_run,
            }
        )
        now = datetime(2026, 5, 17, 9, 0, tzinfo=timezone.utc)
        return RetentionPlan(
            generated_at=now,
            dry_run=dry_run,
            items=(
                RetentionPlanItem(
                    target=RETENTION_TARGETS[0],
                    cutoff_at=now,
                    eligible_count=self.eligible_count,
                    deleted_count=0 if dry_run else self.eligible_count,
                ),
            ),
        )


def _settings(database_url: str | None) -> Settings:
    return Settings(
        enable_mock_ui=False,
        auth_mode="supabase",
        env="test",
        monthly_report_database_url=database_url,
        monthly_report_prompt_version="test-prompt",
        app_version="test",
        openrouter_api_key=None,
        openrouter_model_report="test-report",
        openrouter_model_light="test-light",
        openrouter_timeout_seconds=1.0,
        openrouter_max_tokens=None,
        cloud_run_worker_job_project_id=None,
        cloud_run_worker_job_region=None,
        cloud_run_worker_job_name=None,
        cloud_run_worker_trigger_access_token=None,
        cloud_run_worker_trigger_timeout_seconds=15.0,
        google_workspace_access_token=None,
        google_oauth_client_id=None,
        google_oauth_client_secret=None,
        google_token_encryption_key=None,
        google_token_encryption_key_version="test-v1",
        supabase_url=None,
        supabase_anon_key=None,
        google_oauth_scopes="openid email",
        supabase_jwt_secret=None,
        supabase_jwt_audience="authenticated",
        allowed_email_domain="tomonokai-corp.com",
    )


def _install_fakes(monkeypatch, database_url: str | None) -> None:
    FakeExecutor.calls = []
    FakeExecutor.eligible_count = 2
    monkeypatch.setattr(retention_entry, "get_settings", lambda: _settings(database_url))
    monkeypatch.setattr(retention_entry, "PostgresRetentionRepository", FakeRepository)
    monkeypatch.setattr(retention_entry, "RetentionExecutor", FakeExecutor)


def test_retention_entry_defaults_to_dry_run_and_outputs_pii_safe_json(
    monkeypatch,
    capsys,
):
    _install_fakes(monkeypatch, "postgresql://user:secret@example.invalid/db")

    exit_code = retention_entry.main([])

    assert exit_code == 0
    assert FakeExecutor.calls == [
        {
            "database_url": "postgresql://user:secret@example.invalid/db",
            "actor_id": "monthly-report-retention-job",
            "dry_run": True,
        }
    ]
    summary = json.loads(capsys.readouterr().out)
    assert summary["ok"] is True
    assert summary["actor_id"] == "monthly-report-retention-job"
    assert summary["dry_run"] is True
    assert summary["total_eligible_count"] == 2
    assert summary["total_deleted_count"] == 0
    assert summary["targets"][0]["name"] == "sources"
    assert "secret" not in json.dumps(summary)
    assert "postgresql://" not in json.dumps(summary)


def test_retention_entry_delete_requires_confirmed_total_count(monkeypatch, capsys):
    _install_fakes(monkeypatch, "postgresql://user:secret@example.invalid/db")

    exit_code = retention_entry.main(["--delete"])

    assert exit_code == 1
    assert FakeExecutor.calls == []
    summary = json.loads(capsys.readouterr().out)
    assert summary == {
        "ok": False,
        "error_type": "delete_confirmation_required",
        "message": (
            "--confirm-total-eligible-count is required when --delete is used"
        ),
    }


def test_retention_entry_delete_rechecks_dry_run_count_before_delete(
    monkeypatch,
    capsys,
):
    _install_fakes(monkeypatch, "postgresql://user:secret@example.invalid/db")

    exit_code = retention_entry.main(
        ["--delete", "--confirm-total-eligible-count", "2"]
    )

    assert exit_code == 0
    assert FakeExecutor.calls == [
        {
            "database_url": "postgresql://user:secret@example.invalid/db",
            "actor_id": "monthly-report-retention-job",
            "dry_run": True,
        },
        {
            "database_url": "postgresql://user:secret@example.invalid/db",
            "actor_id": "monthly-report-retention-job",
            "dry_run": False,
        },
        {
            "database_url": "postgresql://user:secret@example.invalid/db",
            "actor_id": "monthly-report-retention-job",
            "dry_run": True,
        },
    ]
    summary = json.loads(capsys.readouterr().out)
    assert summary["actor_id"] == "monthly-report-retention-job"
    assert summary["dry_run"] is False
    assert summary["total_deleted_count"] == 2
    assert summary["post_delete_total_eligible_count"] == 2


def test_retention_entry_delete_refuses_when_confirmed_count_differs(
    monkeypatch,
    capsys,
):
    _install_fakes(monkeypatch, "postgresql://user:secret@example.invalid/db")
    FakeExecutor.eligible_count = 3

    exit_code = retention_entry.main(
        ["--delete", "--confirm-total-eligible-count", "2"]
    )

    assert exit_code == 1
    assert FakeExecutor.calls == [
        {
            "database_url": "postgresql://user:secret@example.invalid/db",
            "actor_id": "monthly-report-retention-job",
            "dry_run": True,
        }
    ]
    summary = json.loads(capsys.readouterr().out)
    assert summary == {
        "ok": False,
        "error_type": "delete_confirmation_mismatch",
        "message": "confirmed count does not match current dry-run count",
        "confirmed_total_eligible_count": 2,
        "actual_total_eligible_count": 3,
    }


def test_retention_entry_missing_database_url_returns_nonzero_json(
    monkeypatch,
    capsys,
):
    _install_fakes(monkeypatch, None)

    exit_code = retention_entry.main([])

    assert exit_code == 1
    assert FakeExecutor.calls == []
    summary = json.loads(capsys.readouterr().out)
    assert summary == {
        "ok": False,
        "error_type": "missing_database_url",
        "message": "EB_MONTHLY_REPORT_DATABASE_URL is required for retention",
    }


def test_retention_entry_rejects_post_delete_expectation_without_delete(
    monkeypatch,
    capsys,
):
    _install_fakes(monkeypatch, "postgresql://user:secret@example.invalid/db")

    exit_code = retention_entry.main(
        ["--post-delete-expected-total-eligible-count", "0"]
    )

    assert exit_code == 1
    assert FakeExecutor.calls == []
    summary = json.loads(capsys.readouterr().out)
    assert summary == {
        "ok": False,
        "error_type": "post_delete_expectation_requires_delete",
        "message": (
            "--post-delete-expected-total-eligible-count requires --delete"
        ),
    }


def test_retention_entry_delete_checks_post_delete_expected_count(
    monkeypatch,
    capsys,
):
    _install_fakes(monkeypatch, "postgresql://user:secret@example.invalid/db")

    exit_code = retention_entry.main(
        [
            "--delete",
            "--confirm-total-eligible-count",
            "2",
            "--post-delete-expected-total-eligible-count",
            "0",
        ]
    )

    assert exit_code == 1
    summary = json.loads(capsys.readouterr().out)
    assert summary == {
        "ok": False,
        "error_type": "post_delete_verification_mismatch",
        "message": "post-delete count does not match expected count",
        "expected_post_delete_total_eligible_count": 0,
        "actual_post_delete_total_eligible_count": 2,
    }


def test_retention_entry_allows_custom_actor_id(
    monkeypatch,
    capsys,
):
    _install_fakes(monkeypatch, "postgresql://user:secret@example.invalid/db")

    exit_code = retention_entry.main(["--actor-id", "ops-retention-manual"])

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["actor_id"] == "ops-retention-manual"
    assert FakeExecutor.calls == [
        {
            "database_url": "postgresql://user:secret@example.invalid/db",
            "actor_id": "ops-retention-manual",
            "dry_run": True,
        }
    ]


def test_retention_entry_failure_returns_nonzero_without_exception_details(
    monkeypatch,
    capsys,
):
    _install_fakes(monkeypatch, "postgresql://user:secret@example.invalid/db")

    def fail_run(self, *, dry_run: bool) -> RetentionPlan:
        raise RuntimeError("database password secret leaked")

    monkeypatch.setattr(FakeExecutor, "run", fail_run)

    exit_code = retention_entry.main(
        ["--delete", "--confirm-total-eligible-count", "2"]
    )

    assert exit_code == 1
    output = capsys.readouterr().out
    summary = json.loads(output)
    assert summary == {
        "ok": False,
        "error_type": "retention_failed",
        "message": "retention execution failed",
    }
    assert "secret" not in output
    assert "password" not in output
