from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

psycopg = pytest.importorskip("psycopg")

from eb_app.main import create_app


DATABASE_URL = os.environ.get("EB_MONTHLY_REPORT_DATABASE_URL")


pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="EB_MONTHLY_REPORT_DATABASE_URL is not set",
)


@pytest.fixture()
def postgres_api_client(monkeypatch: pytest.MonkeyPatch):
    assert DATABASE_URL is not None
    owner_prefix = f"pytest-api-postgres-{uuid4().hex}"
    monkeypatch.setenv("EB_MONTHLY_REPORT_DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("EB_AUTH_MODE", "mock")
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(
            "delete from public.monthly_report_jobs where created_by like %s",
            (f"{owner_prefix}%",),
        )
    return TestClient(create_app()), owner_prefix


def test_monthly_report_api_uses_postgres_store_for_job_feedback_and_rerun(
    postgres_api_client,
):
    client, owner_prefix = postgres_api_client
    owner = f"{owner_prefix}-owner"

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "postgres_api_household",
            "owner_user_id": owner,
        },
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    feedback = client.post(
        f"/api/monthly-reports/jobs/{job_id}/feedback",
        json={"category": "tone", "comment": "DB経由で保存"},
    )
    assert feedback.status_code == 200
    assert feedback.json()["feedback_id"].startswith("mrf_")

    detail = client.get(f"/api/monthly-reports/jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["feedback_count"] == 1

    rerun = client.post(f"/api/monthly-reports/jobs/{job_id}/rerun")
    assert rerun.status_code == 200
    assert rerun.json()["job_id"] != job_id
    assert rerun.json()["owner_user_id"] == owner


def test_monthly_report_api_uses_postgres_store_for_sources_and_artifacts(
    postgres_api_client,
):
    client, owner_prefix = postgres_api_client
    owner = f"{owner_prefix}-persistence-owner"

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "postgres_api_persistence",
            "owner_user_id": owner,
        },
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    source = client.post(
        f"/api/monthly-reports/jobs/{job_id}/sources",
        json={
            "source_type": "sheet",
            "display_name": "授業記録",
            "snapshot_text": "学習ログ",
            "content_hash": "sha256:postgres-source",
        },
    )
    assert source.status_code == 200

    sources = client.get(f"/api/monthly-reports/jobs/{job_id}/sources")
    assert sources.status_code == 200
    assert sources.json()["sources"][0]["source_id"] == source.json()["source_id"]
    assert sources.json()["sources"][0]["display_name"] == "授業記録"

    artifact = client.post(
        f"/api/monthly-reports/jobs/{job_id}/artifacts",
        json={
            "artifact_type": "draft_markdown",
            "content": "# 4月度 月次レポート",
            "content_hash": "sha256:postgres-artifact",
        },
    )
    assert artifact.status_code == 200

    artifacts = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts")
    assert artifacts.status_code == 200
    assert artifacts.json()["artifacts"][0]["artifact_id"] == artifact.json()["artifact_id"]
    assert artifacts.json()["artifacts"][0]["artifact_type"] == "draft_markdown"

    validation = client.post(
        f"/api/monthly-reports/jobs/{job_id}/validations",
        json={
            "rule_id": "required-heading",
            "severity": "error",
            "message": "学習の進捗セクションがありません",
            "path": "sections.learning_progress",
        },
    )
    assert validation.status_code == 200

    validations = client.get(f"/api/monthly-reports/jobs/{job_id}/validations")
    assert validations.status_code == 200
    assert validations.json()["validations"][0]["validation_id"] == validation.json()["validation_id"]
    assert validations.json()["validations"][0]["severity"] == "error"


def test_monthly_report_api_uses_postgres_store_for_pipeline_control(
    postgres_api_client,
):
    client, owner_prefix = postgres_api_client
    owner = f"{owner_prefix}-pipeline-owner"

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "postgres_api_pipeline",
            "owner_user_id": owner,
        },
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    started = client.post(f"/api/monthly-reports/jobs/{job_id}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "running"
    assert started.json()["current_stage"] == "fetch_sources"

    completed = client.post(f"/api/monthly-reports/jobs/{job_id}/complete-stage")
    assert completed.status_code == 200
    assert completed.json()["current_stage"] == "bundle"

    failed = client.post(
        f"/api/monthly-reports/jobs/{job_id}/fail",
        json={
            "error_type": "provider_timeout",
            "error_message": "OpenRouter timed out",
        },
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert failed.json()["error_type"] == "provider_timeout"
