from __future__ import annotations

import os
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from eb_app.main import create_app
from eb_app.monthly_reports.google_workspace import GoogleWorkspaceClient, GoogleWorkspaceSource
from eb_app.monthly_reports.workflow import LLMCompletion, OpenRouterMonthlyReportProvider
import eb_app.routers.monthly_reports as monthly_reports_router


@pytest.fixture(autouse=True)
def monthly_report_mock_auth_env():
    old = os.environ.get("EB_AUTH_MODE")
    os.environ["EB_AUTH_MODE"] = "mock"
    yield
    if old is None:
        os.environ.pop("EB_AUTH_MODE", None)
    else:
        os.environ["EB_AUTH_MODE"] = old


def _minimal_pattern_b_markdown(body: str) -> str:
    return "\n".join(
        [
            "# 月次レポート",
            "## 01 基本情報",
            "本文",
            "## 02 塾での様子",
            "本文",
            "## 03 授業内容",
            "本文",
            "## 04 課題とアドバイス",
            "本文",
            "## 05 学習の進捗",
            "本文",
            f"## 07 今後の授業計画\n{body}",
        ]
    )


def test_monthly_report_api_creates_lists_gets_and_cancels_job():
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_household",
            "template_key": "pattern_b",
            "prompt_version": "monthly-report-v20260514.1",
            "template_hash": "sha256:template-demo",
            "model_report": "anthropic/claude-sonnet-4.6",
            "model_light": "openai/gpt-4.1-mini",
            "resolved_model_report": "anthropic/claude-sonnet-4.6",
            "source_bundle_hash": "sha256:bundle-demo",
            "app_version": "test-sha",
            "prompt_scope_notes": "対象は平林様 Economics のみ",
        },
    )

    assert created.status_code == 200
    body = created.json()
    assert body["job_id"].startswith("mrj_")
    assert body["status"] == "queued"

    listed = client.get("/api/monthly-reports/jobs")
    assert listed.status_code == 200
    assert listed.json()["jobs"][0]["job_id"] == body["job_id"]

    detail = client.get(f"/api/monthly-reports/jobs/{body['job_id']}")
    assert detail.status_code == 200
    assert detail.json()["target_month"] == "2026-04"
    assert detail.json()["household_key"] == "demo_household"
    assert detail.json()["template_key"] == "pattern_b"
    assert detail.json()["prompt_version"] == "monthly-report-v20260514.1"
    assert detail.json()["template_hash"] == "sha256:template-demo"
    assert detail.json()["model_report"] == "anthropic/claude-sonnet-4.6"
    assert detail.json()["model_light"] == "openai/gpt-4.1-mini"
    assert detail.json()["resolved_model_report"] == "anthropic/claude-sonnet-4.6"
    assert detail.json()["source_bundle_hash"] == "sha256:bundle-demo"
    assert detail.json()["app_version"] == "test-sha"
    assert detail.json()["prompt_scope_notes"] == "対象は平林様 Economics のみ"

    cancelled = client.post(f"/api/monthly-reports/jobs/{body['job_id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_monthly_report_api_uses_supabase_user_as_owner_and_filters_other_users(
    monkeypatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    app = create_app()
    client = TestClient(app)

    user_a_headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}"
    }
    user_b_headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-b', email='user-b@tomonokai-corp.com')}"
    }

    created = client.post(
        "/api/monthly-reports/jobs",
        headers=user_a_headers,
        json={
            "target_month": "2026-04",
            "household_key": "demo_authz",
            "owner_user_id": "spoofed-owner",
        },
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]
    assert created.json()["owner_user_id"] == "user-a"

    user_a_jobs = client.get("/api/monthly-reports/jobs", headers=user_a_headers)
    user_b_jobs = client.get("/api/monthly-reports/jobs", headers=user_b_headers)

    assert [job["job_id"] for job in user_a_jobs.json()["jobs"]] == [job_id]
    assert user_b_jobs.json()["jobs"] == []
    assert client.get(f"/api/monthly-reports/jobs/{job_id}", headers=user_b_headers).status_code == 404
    assert (
        client.post(
            f"/api/monthly-reports/jobs/{job_id}/cancel",
            headers={**user_b_headers, "X-EB-Caller-Intent": "e2e"},
        ).status_code
        == 404
    )


def test_monthly_report_api_create_job_stays_service_owned_direct_insert(
    monkeypatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")

    class FakeDirectCreateStore:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def create_job_with_active_limit(self, **kwargs):
            self.calls.append(("create_job_with_active_limit", kwargs))
            return monthly_reports_router.MockJob(
                public_id="mrj_direct_create",
                target_month=str(kwargs["target_month"]),
                household_key=str(kwargs["household_key"]),
                owner_user_id=str(kwargs["owner_user_id"]),
                status="queued",
                template_key=kwargs.get("template_key"),
                prompt_version=kwargs.get("prompt_version"),
            )

    store = FakeDirectCreateStore()
    app = create_app()
    client = TestClient(app)

    monkeypatch.setattr(monthly_reports_router, "_get_store", lambda: store)
    monkeypatch.setattr(
        monthly_reports_router,
        "_get_rls_read_store",
        lambda current_user: (_ for _ in ()).throw(
            AssertionError("create_job should not resolve an RLS read/write store")
        ),
    )

    headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}"
    }
    created = client.post(
        "/api/monthly-reports/jobs",
        headers=headers,
        json={
            "target_month": "2026-04",
            "household_key": "service_owned_direct_create",
            "owner_user_id": "spoofed-owner",
            "template_key": "pattern_b",
            "prompt_version": "monthly-report-vservice-owned.1",
        },
    )

    assert created.status_code == 200
    assert created.json()["job_id"] == "mrj_direct_create"
    assert created.json()["owner_user_id"] == "user-a"
    assert store.calls == [
        (
            "create_job_with_active_limit",
            {
                "target_month": "2026-04",
                "household_key": "service_owned_direct_create",
                "owner_user_id": "user-a",
                "max_active_jobs": monthly_reports_router.MAX_ACTIVE_JOBS_PER_USER,
                "template_key": "pattern_b",
                "prompt_version": "monthly-report-vservice-owned.1",
                "template_hash": None,
                "model_report": None,
                "model_light": None,
                "resolved_model_report": None,
                "source_bundle_hash": None,
                "app_version": None,
                "prompt_scope_notes": None,
            },
        )
    ]


def test_monthly_report_api_uses_rls_read_store_for_supabase_user_reads(monkeypatch):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:56321")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    app = create_app()
    client = TestClient(app)
    job = monthly_reports_router.MockJob(
        public_id="mrj_rls_owner",
        target_month="2026-04",
        household_key="rls_household",
        owner_user_id="user-a",
    )
    read_store = _FakeRLSReadStore(job)

    monkeypatch.setattr(
        monthly_reports_router,
        "_get_rls_read_store",
        lambda current_user: read_store,
    )
    monkeypatch.setattr(monthly_reports_router, "_get_store", _raise_if_direct_store_used)
    headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}"
    }

    listed = client.get("/api/monthly-reports/jobs", headers=headers)
    detail = client.get("/api/monthly-reports/jobs/mrj_rls_owner", headers=headers)
    sources = client.get("/api/monthly-reports/jobs/mrj_rls_owner/sources", headers=headers)
    artifacts = client.get("/api/monthly-reports/jobs/mrj_rls_owner/artifacts", headers=headers)
    validations = client.get("/api/monthly-reports/jobs/mrj_rls_owner/validations", headers=headers)
    llm_calls = client.get("/api/monthly-reports/jobs/mrj_rls_owner/llm-calls", headers=headers)

    assert listed.status_code == 200
    assert listed.json()["jobs"][0]["job_id"] == "mrj_rls_owner"
    assert detail.status_code == 200
    assert sources.json()["sources"][0]["source_id"] == "mrs_rls"
    assert artifacts.json()["artifacts"][0]["artifact_id"] == "mra_rls"
    assert validations.json()["validations"][0]["validation_id"] == "mrv_rls"
    assert llm_calls.json()["llm_calls"][0]["llm_call_id"] == "mrl_rls"
    assert read_store.calls == [
        "list_jobs",
        "get",
        "get",
        "list_sources",
        "get",
        "list_artifacts",
        "get",
        "list_validations",
        "get",
        "list_llm_calls",
    ]


def test_monthly_report_api_write_actions_use_rls_read_preflight_for_supabase_user(
    monkeypatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:56321")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    app = create_app()
    client = TestClient(app)
    job = monthly_reports_router._store.create_job(
        target_month="2026-04",
        household_key="api_rls_write_household",
        owner_user_id="user-a",
    )
    read_store = _FakeRLSReadStore(job)
    monkeypatch.setattr(
        monthly_reports_router,
        "_get_rls_read_store",
        lambda current_user: read_store,
    )
    headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}",
        "Idempotency-Key": "api-rls-write-key",
    }

    source = client.post(
        f"/api/monthly-reports/jobs/{job.public_id}/sources",
        headers=headers,
        json={
            "source_type": "doc",
            "display_name": "RLS API source",
            "snapshot_text": "RLS read preflight",
        },
    )
    artifact = client.post(
        f"/api/monthly-reports/jobs/{job.public_id}/artifacts",
        headers={**headers, "Idempotency-Key": "api-rls-artifact-key"},
        json={
            "artifact_type": "draft_markdown",
            "content": "## 01 基本情報\nRLS API artifact",
        },
    )
    validation = client.post(
        f"/api/monthly-reports/jobs/{job.public_id}/validations",
        headers={**headers, "X-EB-Caller-Intent": "e2e"},
        json={
            "rule_id": "rls_api_validation",
            "severity": "info",
            "message": "ok",
        },
    )
    feedback = client.post(
        f"/api/monthly-reports/jobs/{job.public_id}/feedback",
        headers={**headers, "Idempotency-Key": "api-rls-feedback-key"},
        json={
            "category": "tone",
            "comment": "RLS API feedback",
        },
    )

    assert source.status_code == 200
    assert artifact.status_code == 200
    assert validation.status_code == 200
    assert feedback.status_code == 200
    assert read_store.calls == [
        "get",
        "record_source",
        "get",
        "record_artifact",
        "get",
        "record_validation",
        "get",
        "record_feedback",
    ]
    assert read_store.sources[-1].display_name == "RLS API source"
    assert validation.json()["validation_id"].startswith("mrv_api_rls_")
    assert any(item.comment == "RLS API feedback" for item in read_store.job.feedback)


def test_monthly_report_api_fetch_google_sources_uses_rls_write_store_for_supabase_user(
    monkeypatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:56321")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setattr(
        monthly_reports_router,
        "_resolve_google_workspace_access_token",
        lambda current_user: "resolved-access-token",
    )

    class FakeGoogleWorkspaceClient:
        def __init__(self, *, access_token):
            assert access_token == "resolved-access-token"

        def fetch_doc(self, *, document_id, display_name=None):
            assert document_id == "doc-id"
            return GoogleWorkspaceSource(
                source_type="google_doc",
                display_name=display_name or "RLS API Google Doc",
                snapshot_text="doc text",
                content_hash="sha256:api-rls-gdoc",
            )

    monkeypatch.setattr(
        monthly_reports_router,
        "GoogleWorkspaceClient",
        FakeGoogleWorkspaceClient,
    )
    app = create_app()
    client = TestClient(app)
    job = monthly_reports_router._store.create_job(
        target_month="2026-04",
        household_key="api_rls_google_source_household",
        owner_user_id="user-a",
    )
    read_store = _FakeRLSReadStore(job)
    monkeypatch.setattr(
        monthly_reports_router,
        "_get_rls_read_store",
        lambda current_user: read_store,
    )
    headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}",
        "Idempotency-Key": "api-rls-google-fetch-key",
    }

    fetched = client.post(
        f"/api/monthly-reports/jobs/{job.public_id}/fetch-google-sources",
        headers=headers,
        json={"doc_ids": ["doc-id"], "sheet_ranges": []},
    )

    assert fetched.status_code == 200
    assert read_store.calls[:2] == ["get", "record_source"]
    assert read_store.sources[-1].content_hash == "sha256:api-rls-gdoc"
    assert monthly_reports_router._store.list_sources(job.public_id) == []


def test_monthly_report_api_rejects_invalid_create_payload():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/monthly-reports/jobs",
        json={"target_month": "", "household_key": ""},
    )

    assert response.status_code == 422


def test_monthly_report_api_returns_404_for_unknown_job():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/monthly-reports/jobs/mrj_missing")

    assert response.status_code == 404


def test_monthly_report_api_rejects_fourth_active_job_for_same_mock_owner():
    app = create_app()
    client = TestClient(app)

    payload = {
        "target_month": "2026-04",
        "household_key": "demo_household",
        "owner_user_id": "owner-limit-api",
    }
    for _ in range(3):
        response = client.post("/api/monthly-reports/jobs", json=payload)
        assert response.status_code == 200

    rejected = client.post("/api/monthly-reports/jobs", json=payload)

    assert rejected.status_code == 429
    assert "active generation jobs" in rejected.json()["detail"]


def test_monthly_report_api_create_job_is_idempotent_with_header_key():
    app = create_app()
    client = TestClient(app)

    payload = {
        "target_month": "2026-04",
        "household_key": "demo_idempotent",
        "owner_user_id": "owner-idempotent-api",
    }
    first = client.post(
        "/api/monthly-reports/jobs",
        headers={"Idempotency-Key": "job-create-demo-idem"},
        json=payload,
    )
    second = client.post(
        "/api/monthly-reports/jobs",
        headers={"Idempotency-Key": "job-create-demo-idem"},
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["job_id"] == first.json()["job_id"]

    jobs = client.get("/api/monthly-reports/jobs")
    matching = [
        job
        for job in jobs.json()["jobs"]
        if job["owner_user_id"] == "owner-idempotent-api"
        and job["household_key"] == "demo_idempotent"
    ]
    assert len(matching) == 1


def test_monthly_report_api_idempotent_create_does_not_consume_active_limit_twice():
    app = create_app()
    client = TestClient(app)

    payload = {
        "target_month": "2026-04",
        "household_key": "demo_idempotent_limit",
        "owner_user_id": "owner-idempotent-limit-api",
    }
    for index in range(3):
        response = client.post(
            "/api/monthly-reports/jobs",
            headers={"Idempotency-Key": f"job-create-limit-{index}"},
            json=payload,
        )
        assert response.status_code == 200

    duplicate = client.post(
        "/api/monthly-reports/jobs",
        headers={"Idempotency-Key": "job-create-limit-0"},
        json=payload,
    )
    assert duplicate.status_code == 200

    rejected = client.post(
        "/api/monthly-reports/jobs",
        headers={"Idempotency-Key": "job-create-limit-new"},
        json=payload,
    )
    assert rejected.status_code == 429


def test_monthly_report_api_run_mock_is_idempotent_with_header_key():
    app = create_app()
    client = TestClient(app)
    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_run_idempotent",
            "owner_user_id": "owner-run-idempotent-api",
        },
    )
    job_id = created.json()["job_id"]

    first = client.post(
        f"/api/monthly-reports/jobs/{job_id}/run-mock",
        headers={"Idempotency-Key": "run-mock-demo-idem"},
        json={
            "content": "\n\n".join(
                [
                    "## 01 基本情報\n初回生成",
                    "## 02 塾での様子\n集中しています。",
                    "## 03 授業内容\n復習を進めました。",
                    "## 04 課題とアドバイス\n演習を続けます。",
                    "## 05 学習の進捗\n基礎が定着しています。",
                    "## 07 今後の授業計画\n次回は応用演習です。",
                ]
            )
        },
    )
    second = client.post(
        f"/api/monthly-reports/jobs/{job_id}/run-mock",
        headers={"Idempotency-Key": "run-mock-demo-idem"},
        json={"content": "## 01 基本情報\n二重送信"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["job_id"] == first.json()["job_id"]
    assert second.json()["status"] == "succeeded"


def test_monthly_report_api_does_not_count_cancelled_jobs_against_mock_owner_limit():
    app = create_app()
    client = TestClient(app)

    payload = {
        "target_month": "2026-04",
        "household_key": "demo_household",
        "owner_user_id": "owner-completed-api",
    }
    for _ in range(3):
        created = client.post("/api/monthly-reports/jobs", json=payload)
        assert created.status_code == 200
        cancelled = client.post(
            f"/api/monthly-reports/jobs/{created.json()['job_id']}/cancel"
        )
        assert cancelled.status_code == 200

    response = client.post("/api/monthly-reports/jobs", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "queued"


def test_monthly_report_api_records_feedback_and_includes_feedback_count():
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_feedback",
            "owner_user_id": "owner-feedback-api",
        },
    )
    job_id = created.json()["job_id"]

    feedback = client.post(
        f"/api/monthly-reports/jobs/{job_id}/feedback",
        json={"category": "tone", "comment": "保護者向けにやや硬い"},
    )

    assert feedback.status_code == 200
    assert feedback.json()["feedback_id"].startswith("mrf_")
    assert feedback.json()["job_id"] == job_id
    assert feedback.json()["category"] == "tone"
    assert feedback.json()["comment"] == "保護者向けにやや硬い"

    detail = client.get(f"/api/monthly-reports/jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["feedback_count"] == 1


def test_monthly_report_api_record_feedback_is_idempotent_with_header_key():
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_feedback_idempotent",
            "owner_user_id": "owner-feedback-idempotent-api",
        },
    )
    job_id = created.json()["job_id"]

    first = client.post(
        f"/api/monthly-reports/jobs/{job_id}/feedback",
        headers={"Idempotency-Key": "feedback-demo-idem"},
        json={"category": "tone", "comment": "保護者向けにやや硬い"},
    )
    second = client.post(
        f"/api/monthly-reports/jobs/{job_id}/feedback",
        headers={"Idempotency-Key": "feedback-demo-idem"},
        json={"category": "tone", "comment": "二重送信"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()

    detail = client.get(f"/api/monthly-reports/jobs/{job_id}")
    assert detail.json()["feedback_count"] == 1


def test_monthly_report_api_records_source_snapshot_and_artifact():
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_persistence",
            "owner_user_id": "owner-persistence-api",
        },
    )
    job_id = created.json()["job_id"]

    source = client.post(
        f"/api/monthly-reports/jobs/{job_id}/sources",
        json={
            "source_type": "doc",
            "display_name": "面談メモ",
            "snapshot_text": "4月の学習記録",
            "content_hash": "sha256:source-demo",
        },
    )

    assert source.status_code == 200
    assert source.json()["source_id"].startswith("mrs_")
    assert source.json()["job_id"] == job_id
    assert source.json()["display_name"] == "面談メモ"

    sources = client.get(f"/api/monthly-reports/jobs/{job_id}/sources")
    assert sources.status_code == 200
    assert sources.json()["sources"] == [source.json()]

    artifact = client.post(
        f"/api/monthly-reports/jobs/{job_id}/artifacts",
        json={
            "artifact_type": "draft_markdown",
            "content": "# 4月度 月次レポート",
            "content_hash": "sha256:artifact-demo",
        },
    )

    assert artifact.status_code == 200
    assert artifact.json()["artifact_id"].startswith("mra_")
    assert artifact.json()["job_id"] == job_id
    assert artifact.json()["artifact_type"] == "draft_markdown"

    artifacts = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts")
    assert artifacts.status_code == 200
    assert artifacts.json()["artifacts"] == [artifact.json()]


def test_monthly_report_api_record_validation_is_idempotent_with_header_key():
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_validation_idempotent",
            "owner_user_id": "owner-validation-idempotent-api",
        },
    )
    job_id = created.json()["job_id"]

    first = client.post(
        f"/api/monthly-reports/jobs/{job_id}/validations",
        headers={
            "Idempotency-Key": "validation-demo-idem",
            "X-EB-Caller-Intent": "e2e",
        },
        json={
            "rule_id": "non_empty_markdown",
            "severity": "info",
            "message": "初回validation",
        },
    )
    second = client.post(
        f"/api/monthly-reports/jobs/{job_id}/validations",
        headers={
            "Idempotency-Key": "validation-demo-idem",
            "X-EB-Caller-Intent": "e2e",
        },
        json={
            "rule_id": "non_empty_markdown",
            "severity": "error",
            "message": "二重送信",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    validations = client.get(f"/api/monthly-reports/jobs/{job_id}/validations")
    assert validations.json()["validations"] == [first.json()]


def test_monthly_report_api_record_artifact_is_idempotent_with_header_key():
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_artifact_idempotent",
            "owner_user_id": "owner-artifact-idempotent-api",
        },
    )
    job_id = created.json()["job_id"]

    first = client.post(
        f"/api/monthly-reports/jobs/{job_id}/artifacts",
        headers={"Idempotency-Key": "artifact-demo-idem"},
        json={
            "artifact_type": "draft_markdown",
            "content": "# 初回",
            "content_hash": "sha256:artifact-idem",
        },
    )
    second = client.post(
        f"/api/monthly-reports/jobs/{job_id}/artifacts",
        headers={"Idempotency-Key": "artifact-demo-idem"},
        json={
            "artifact_type": "draft_markdown",
            "content": "# 二重送信",
            "content_hash": "sha256:changed",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()

    artifacts = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts")
    assert len(artifacts.json()["artifacts"]) == 1
    assert artifacts.json()["artifacts"][0]["content"] == "# 初回"


def test_monthly_report_api_record_source_is_idempotent_with_header_key():
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_source_idempotent",
            "owner_user_id": "owner-source-idempotent-api",
        },
    )
    job_id = created.json()["job_id"]
    payload = {
        "source_type": "doc",
        "display_name": "面談メモ",
        "snapshot_text": "4月の学習記録",
        "content_hash": "sha256:source-idempotent",
    }

    first = client.post(
        f"/api/monthly-reports/jobs/{job_id}/sources",
        headers={"Idempotency-Key": "source-save-demo-idem"},
        json=payload,
    )
    second = client.post(
        f"/api/monthly-reports/jobs/{job_id}/sources",
        headers={"Idempotency-Key": "source-save-demo-idem"},
        json={**payload, "display_name": "二重送信"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()

    sources = client.get(f"/api/monthly-reports/jobs/{job_id}/sources")
    assert len(sources.json()["sources"]) == 1
    assert sources.json()["sources"][0]["display_name"] == "面談メモ"


def test_monthly_report_api_fetches_google_workspace_sources(monkeypatch):
    monkeypatch.setenv("EB_GOOGLE_WORKSPACE_ACCESS_TOKEN", "access-token")

    def fake_fetch_doc(self, *, document_id, display_name=None):
        assert document_id == "doc-id"
        return GoogleWorkspaceSource(
            source_type="google_doc",
            display_name=display_name or "教師MTG",
            snapshot_text="doc text",
            content_hash="sha256:doc",
        )

    def fake_fetch_sheet_values(self, *, spreadsheet_id, range_name, display_name=None):
        assert spreadsheet_id == "sheet-id"
        assert range_name == "student!A1:B2"
        return GoogleWorkspaceSource(
            source_type="google_sheet",
            display_name=display_name or "student sheet",
            snapshot_text="sheet text",
            content_hash="sha256:sheet",
        )

    monkeypatch.setattr(GoogleWorkspaceClient, "fetch_doc", fake_fetch_doc)
    monkeypatch.setattr(GoogleWorkspaceClient, "fetch_sheet_values", fake_fetch_sheet_values)

    app = create_app()
    client = TestClient(app)
    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_gws",
            "owner_user_id": "owner-gws-api",
        },
    )
    job_id = created.json()["job_id"]

    response = client.post(
        f"/api/monthly-reports/jobs/{job_id}/fetch-google-sources",
        json={
            "doc_ids": ["doc-id"],
            "sheet_ranges": [
                {
                    "spreadsheet_id": "sheet-id",
                    "range_name": "student!A1:B2",
                    "display_name": "student sheet",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert [
        (source["source_type"], source["display_name"])
        for source in response.json()["sources"]
    ] == [
        ("google_doc", "教師MTG"),
        ("google_sheet", "student sheet"),
    ]

    listed = client.get(f"/api/monthly-reports/jobs/{job_id}/sources")
    assert [source["content_hash"] for source in listed.json()["sources"]] == [
        "sha256:doc",
        "sha256:sheet",
    ]


def test_monthly_report_api_fetch_google_sources_is_idempotent_before_external_fetch(
    monkeypatch,
):
    monkeypatch.setenv("EB_GOOGLE_WORKSPACE_ACCESS_TOKEN", "access-token")
    calls = {"doc": 0}

    def fake_fetch_doc(self, *, document_id, display_name=None):
        calls["doc"] += 1
        assert document_id == "doc-id"
        return GoogleWorkspaceSource(
            source_type="google_doc",
            display_name=display_name or "教師MTG",
            snapshot_text="doc text",
            content_hash="sha256:doc-idempotent",
        )

    monkeypatch.setattr(GoogleWorkspaceClient, "fetch_doc", fake_fetch_doc)

    app = create_app()
    client = TestClient(app)
    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_gws_idempotent",
            "owner_user_id": "owner-gws-idempotent-api",
        },
    )
    job_id = created.json()["job_id"]
    payload = {"doc_ids": ["doc-id"], "sheet_ranges": []}

    first = client.post(
        f"/api/monthly-reports/jobs/{job_id}/fetch-google-sources",
        headers={"Idempotency-Key": "google-fetch-demo-idem"},
        json=payload,
    )
    second = client.post(
        f"/api/monthly-reports/jobs/{job_id}/fetch-google-sources",
        headers={"Idempotency-Key": "google-fetch-demo-idem"},
        json={"doc_ids": ["changed-doc-id"], "sheet_ranges": []},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert calls["doc"] == 1

    listed = client.get(f"/api/monthly-reports/jobs/{job_id}/sources")
    assert len(listed.json()["sources"]) == 1
    assert listed.json()["sources"][0]["content_hash"] == "sha256:doc-idempotent"


def test_monthly_report_api_rejects_google_workspace_fetch_without_server_token(
    monkeypatch,
):
    monkeypatch.delenv("EB_GOOGLE_WORKSPACE_ACCESS_TOKEN", raising=False)
    app = create_app()
    client = TestClient(app)
    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_gws_no_token",
            "owner_user_id": "owner-gws-no-token-api",
        },
    )

    response = client.post(
        f"/api/monthly-reports/jobs/{created.json()['job_id']}/fetch-google-sources",
        json={"doc_ids": ["doc-id"], "sheet_ranges": []},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Google Workspace access token is not configured"


def test_monthly_report_api_fetches_google_workspace_sources_with_resolved_oauth_token(
    monkeypatch,
):
    monkeypatch.delenv("EB_GOOGLE_WORKSPACE_ACCESS_TOKEN", raising=False)

    def fake_resolve_google_workspace_access_token(current_user):
        assert current_user.email.endswith("@tomonokai-corp.com")
        return "resolved-access-token"

    def fake_fetch_doc(self, *, document_id, display_name=None):
        assert self._access_token == "resolved-access-token"
        return GoogleWorkspaceSource(
            source_type="google_doc",
            display_name="教師MTG",
            snapshot_text="doc text",
            content_hash="sha256:doc",
        )

    monkeypatch.setattr(
        monthly_reports_router,
        "_resolve_google_workspace_access_token",
        fake_resolve_google_workspace_access_token,
    )
    monkeypatch.setattr(GoogleWorkspaceClient, "fetch_doc", fake_fetch_doc)

    app = create_app()
    client = TestClient(app)
    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_gws_resolved",
            "owner_user_id": "owner-gws-resolved-api",
        },
    )

    response = client.post(
        f"/api/monthly-reports/jobs/{created.json()['job_id']}/fetch-google-sources",
        json={"doc_ids": ["doc-id"], "sheet_ranges": []},
    )

    assert response.status_code == 200
    assert response.json()["sources"][0]["content_hash"] == "sha256:doc"


def test_monthly_report_api_records_validation_result():
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_validation",
            "owner_user_id": "owner-validation-api",
        },
    )
    job_id = created.json()["job_id"]

    validation = client.post(
        f"/api/monthly-reports/jobs/{job_id}/validations",
        headers={"X-EB-Caller-Intent": "e2e"},
        json={
            "rule_id": "required-heading",
            "severity": "error",
            "message": "学習の進捗セクションがありません",
            "path": "sections.learning_progress",
        },
    )

    assert validation.status_code == 200
    assert validation.json()["validation_id"].startswith("mrv_")
    assert validation.json()["job_id"] == job_id
    assert validation.json()["severity"] == "error"

    validations = client.get(f"/api/monthly-reports/jobs/{job_id}/validations")
    assert validations.status_code == 200
    assert validations.json()["validations"] == [validation.json()]


def test_monthly_report_api_validation_requires_caller_intent_for_supabase_user(
    monkeypatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setattr(monthly_reports_router, "_store", monthly_reports_router.MockJobStore())
    app = create_app()
    client = TestClient(app)
    headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}"
    }

    created = client.post(
        "/api/monthly-reports/jobs",
        headers=headers,
        json={
            "target_month": "2026-04",
            "household_key": "validation-caller-intent",
        },
    )
    assert created.status_code == 200

    response = client.post(
        f"/api/monthly-reports/jobs/{created.json()['job_id']}/validations",
        headers=headers,
        json={
            "rule_id": "required-heading",
            "severity": "error",
            "message": "missing",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "validations requires X-EB-Caller-Intent: admin, e2e"
    )


def test_monthly_report_api_validation_allows_e2e_caller_intent_for_supabase_user(
    monkeypatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setattr(monthly_reports_router, "_store", monthly_reports_router.MockJobStore())
    app = create_app()
    client = TestClient(app)
    headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}",
        "X-EB-Caller-Intent": "e2e",
    }

    created = client.post(
        "/api/monthly-reports/jobs",
        headers=headers,
        json={
            "target_month": "2026-04",
            "household_key": "validation-caller-e2e",
        },
    )
    assert created.status_code == 200

    response = client.post(
        f"/api/monthly-reports/jobs/{created.json()['job_id']}/validations",
        headers=headers,
        json={
            "rule_id": "required-heading",
            "severity": "error",
            "message": "missing",
        },
    )

    assert response.status_code == 200
    assert response.json()["validation_id"].startswith("mrv_")


@pytest.mark.parametrize(
    ("route_suffix", "payload", "extra_headers"),
    [
        (
            "sources",
            {
                "source_type": "doc",
                "display_name": "面談メモ",
                "snapshot_text": "need owner access",
            },
            {"Idempotency-Key": "non-owner-source-idem"},
        ),
        (
            "artifacts",
            {
                "artifact_type": "draft_markdown",
                "content": "## 01 基本情報\nneed owner access",
            },
            {"Idempotency-Key": "non-owner-artifact-idem"},
        ),
        (
            "feedback",
            {
                "category": "tone",
                "comment": "need owner access",
            },
            {"Idempotency-Key": "non-owner-feedback-idem"},
        ),
        (
            "validations",
            {
                "rule_id": "required-heading",
                "severity": "error",
                "message": "need owner access",
            },
            {
                "Idempotency-Key": "non-owner-validation-idem",
                "X-EB-Caller-Intent": "e2e",
            },
        ),
    ],
)
def test_monthly_report_api_content_write_routes_return_404_for_non_owner_supabase_user(
    monkeypatch,
    route_suffix: str,
    payload: dict[str, object],
    extra_headers: dict[str, str],
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setattr(monthly_reports_router, "_store", monthly_reports_router.MockJobStore())
    app = create_app()
    client = TestClient(app)

    owner_headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}",
    }
    other_headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-b', email='user-b@tomonokai-corp.com')}",
    }

    created = client.post(
        "/api/monthly-reports/jobs",
        headers=owner_headers,
        json={
            "target_month": "2026-04",
            "household_key": f"non-owner-content-write-{route_suffix}",
        },
    )
    assert created.status_code == 200

    response = client.post(
        f"/api/monthly-reports/jobs/{created.json()['job_id']}/{route_suffix}",
        headers={**other_headers, **extra_headers},
        json=payload,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


@pytest.mark.parametrize(
    ("suffix", "payload"),
    [
        ("start", None),
        ("complete-stage", None),
        ("fail", {"error_type": "provider_timeout", "error_message": "boom"}),
        ("cancel", None),
        ("run-mock", {"content": _minimal_pattern_b_markdown("本文です。")}),
        ("run-openrouter", None),
        ("rerun", None),
    ],
)
def test_monthly_report_api_state_mutation_routes_require_caller_intent_for_supabase_user(
    monkeypatch,
    suffix: str,
    payload: dict[str, object] | None,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setattr(monthly_reports_router, "_store", monthly_reports_router.MockJobStore())
    app = create_app()
    client = TestClient(app)
    headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}"
    }

    created = client.post(
        "/api/monthly-reports/jobs",
        headers=headers,
        json={
            "target_month": "2026-04",
            "household_key": f"state-mutation-{suffix}",
        },
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    if suffix == "run-mock":
        source = client.post(
            f"/api/monthly-reports/jobs/{job_id}/sources",
            headers={**headers, "Idempotency-Key": f"source-{suffix}"},
            json={
                "source_type": "doc",
                "display_name": "面談メモ",
                "snapshot_text": "4月は需要曲線の読み取りを扱った。",
            },
        )
        assert source.status_code == 200

    response = client.post(
        f"/api/monthly-reports/jobs/{job_id}/{suffix}",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        f"{suffix} requires X-EB-Caller-Intent: admin, e2e"
    )


def test_monthly_report_api_cancel_allows_e2e_caller_intent_for_supabase_user(
    monkeypatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setattr(monthly_reports_router, "_store", monthly_reports_router.MockJobStore())
    app = create_app()
    client = TestClient(app)
    headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}",
        "X-EB-Caller-Intent": "e2e",
    }

    created = client.post(
        "/api/monthly-reports/jobs",
        headers=headers,
        json={
            "target_month": "2026-04",
            "household_key": "state-mutation-cancel-e2e",
        },
    )
    assert created.status_code == 200

    cancelled = client.post(
        f"/api/monthly-reports/jobs/{created.json()['job_id']}/cancel",
        headers=headers,
    )

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_monthly_report_api_admin_caller_intent_requires_admin_role(monkeypatch):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setattr(monthly_reports_router, "_store", monthly_reports_router.MockJobStore())
    app = create_app()
    client = TestClient(app)
    user_headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}"
    }
    created = client.post(
        "/api/monthly-reports/jobs",
        headers=user_headers,
        json={
            "target_month": "2026-04",
            "household_key": "state-mutation-admin-intent",
        },
    )
    assert created.status_code == 200

    rejected = client.post(
        f"/api/monthly-reports/jobs/{created.json()['job_id']}/cancel",
        headers={**user_headers, "X-EB-Caller-Intent": "admin"},
    )

    assert rejected.status_code == 403
    assert rejected.json()["detail"] == "admin caller intent requires admin role"


def test_monthly_report_api_admin_caller_intent_allows_admin_role(monkeypatch):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setattr(monthly_reports_router, "_store", monthly_reports_router.MockJobStore())
    app = create_app()
    client = TestClient(app)
    owner_headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}"
    }
    created = client.post(
        "/api/monthly-reports/jobs",
        headers=owner_headers,
        json={
            "target_month": "2026-04",
            "household_key": "state-mutation-admin-role",
        },
    )
    assert created.status_code == 200

    admin_headers = {
        "Authorization": (
            f"Bearer {_supabase_token(sub='admin-user', email='admin@tomonokai-corp.com', role='admin')}"
        ),
        "X-EB-Caller-Intent": "admin",
    }
    cancelled = client.post(
        f"/api/monthly-reports/jobs/{created.json()['job_id']}/cancel",
        headers=admin_headers,
    )

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_monthly_report_api_manual_recovery_fail_requires_admin_caller_intent(
    monkeypatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    store = monthly_reports_router.MockJobStore()
    monkeypatch.setattr(monthly_reports_router, "_store", store)
    app = create_app()
    client = TestClient(app)
    owner_headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}"
    }
    admin_headers = {
        "Authorization": (
            f"Bearer {_supabase_token(sub='admin-user', email='admin@tomonokai-corp.com', role='admin')}"
        ),
        "X-EB-Caller-Intent": "e2e",
    }

    created = client.post(
        "/api/monthly-reports/jobs",
        headers=owner_headers,
        json={
            "target_month": "2026-04",
            "household_key": "manual-recovery-intent",
        },
    )
    assert created.status_code == 200

    started = client.post(
        f"/api/monthly-reports/jobs/{created.json()['job_id']}/start",
        headers=admin_headers,
    )
    assert started.status_code == 200

    rejected = client.post(
        f"/api/monthly-reports/jobs/{created.json()['job_id']}/manual-recovery/fail",
        headers=admin_headers,
        json={"error_message": "needs admin intent"},
    )

    assert rejected.status_code == 403
    assert rejected.json()["detail"] == "manual-recovery/fail requires X-EB-Caller-Intent: admin"


def test_monthly_report_api_admin_manual_recovery_fail_marks_running_job_failed(
    monkeypatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    store = monthly_reports_router.MockJobStore()
    monkeypatch.setattr(monthly_reports_router, "_store", store)
    app = create_app()
    client = TestClient(app)
    owner_headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}"
    }
    admin_headers = {
        "Authorization": (
            f"Bearer {_supabase_token(sub='admin-user', email='admin@tomonokai-corp.com', role='admin')}"
        ),
        "X-EB-Caller-Intent": "admin",
    }

    created = client.post(
        "/api/monthly-reports/jobs",
        headers=owner_headers,
        json={
            "target_month": "2026-04",
            "household_key": "manual-recovery-success",
        },
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    started = client.post(
        f"/api/monthly-reports/jobs/{job_id}/start",
        headers=admin_headers,
    )
    assert started.status_code == 200
    assert started.json()["status"] == "running"

    recovered = client.post(
        f"/api/monthly-reports/jobs/{job_id}/manual-recovery/fail",
        headers=admin_headers,
        json={"error_message": "worker heartbeat timed out in staging"},
    )

    assert recovered.status_code == 200
    assert recovered.json()["status"] == "failed"
    assert recovered.json()["error_type"] == "manual_recovery_required"
    assert recovered.json()["error_message"] == "worker heartbeat timed out in staging"
    assert recovered.json()["current_stage"] == "fetch_sources"

    audit_logs = store.list_audit_logs(job_id)
    assert audit_logs[-1].action == "monthly_report_job_manual_recovery_failed"
    assert audit_logs[-1].metadata["caller_intent"] == "admin"
    assert audit_logs[-1].metadata["previous_stage"] == "fetch_sources"
    assert audit_logs[-1].metadata["operator_note_present"] is True


def test_monthly_report_api_admin_manual_recovery_fail_rejects_non_running_job(
    monkeypatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    store = monthly_reports_router.MockJobStore()
    monkeypatch.setattr(monthly_reports_router, "_store", store)
    app = create_app()
    client = TestClient(app)
    admin_headers = {
        "Authorization": (
            f"Bearer {_supabase_token(sub='admin-user', email='admin@tomonokai-corp.com', role='admin')}"
        ),
        "X-EB-Caller-Intent": "admin",
    }

    created = client.post(
        "/api/monthly-reports/jobs",
        headers=admin_headers,
        json={
            "target_month": "2026-04",
            "household_key": "manual-recovery-non-running",
        },
    )
    assert created.status_code == 200

    rejected = client.post(
        f"/api/monthly-reports/jobs/{created.json()['job_id']}/manual-recovery/fail",
        headers=admin_headers,
        json={"error_message": "not running"},
    )

    assert rejected.status_code == 409
    assert rejected.json()["detail"] == "manual recovery fail requires running job"


def test_monthly_report_api_returns_404_when_recording_feedback_for_unknown_job():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/monthly-reports/jobs/mrj_missing/feedback",
        json={"category": "tone", "comment": "missing"},
    )

    assert response.status_code == 404


def test_monthly_report_api_reruns_existing_job_with_same_target_household_and_owner():
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_rerun",
            "owner_user_id": "owner-rerun-api",
            "prompt_scope_notes": "対象は平林様 Economics のみ",
        },
    )
    original = created.json()

    rerun = client.post(f"/api/monthly-reports/jobs/{original['job_id']}/rerun")

    assert rerun.status_code == 200
    body = rerun.json()
    assert body["job_id"] != original["job_id"]
    assert body["status"] == "queued"
    assert body["target_month"] == original["target_month"]
    assert body["household_key"] == original["household_key"]
    assert body["owner_user_id"] == original["owner_user_id"]
    assert body["prompt_scope_notes"] == original["prompt_scope_notes"]


def test_monthly_report_api_returns_404_when_rerunning_unknown_job():
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/monthly-reports/jobs/mrj_missing/rerun")

    assert response.status_code == 404


def test_monthly_report_api_advances_pipeline_and_succeeds_job():
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={"target_month": "2026-04", "household_key": "demo_pipeline"},
    )
    job_id = created.json()["job_id"]

    started = client.post(f"/api/monthly-reports/jobs/{job_id}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "running"
    assert started.json()["current_stage"] == "fetch_sources"

    completed = client.post(f"/api/monthly-reports/jobs/{job_id}/complete-stage")
    assert completed.status_code == 200
    assert completed.json()["status"] == "running"
    assert completed.json()["current_stage"] == "bundle"
    assert completed.json()["completed_stages"] == ["fetch_sources"]

    body = completed.json()
    while body["status"] == "running":
        response = client.post(f"/api/monthly-reports/jobs/{job_id}/complete-stage")
        assert response.status_code == 200
        body = response.json()

    assert body["status"] == "succeeded"
    assert body["current_stage"] is None
    assert body["completed_stages"][-1] == "persist"


def test_monthly_report_api_fails_running_job_with_error_details():
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={"target_month": "2026-04", "household_key": "demo_fail"},
    )
    job_id = created.json()["job_id"]
    client.post(f"/api/monthly-reports/jobs/{job_id}/start")

    failed = client.post(
        f"/api/monthly-reports/jobs/{job_id}/fail",
        json={
            "error_type": "provider_timeout",
            "error_message": "OpenRouter timed out",
        },
    )

    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert failed.json()["current_stage"] == "fetch_sources"
    assert failed.json()["error_type"] == "provider_timeout"
    assert failed.json()["error_message"] == "OpenRouter timed out"

    detail = client.get(f"/api/monthly-reports/jobs/{job_id}")
    assert detail.json()["error_type"] == "provider_timeout"


def test_monthly_report_api_returns_409_for_invalid_pipeline_transition():
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={"target_month": "2026-04", "household_key": "demo_invalid"},
    )

    response = client.post(
        f"/api/monthly-reports/jobs/{created.json()['job_id']}/complete-stage"
    )

    assert response.status_code == 409


def test_monthly_report_api_runs_provider_mock_pipeline_and_persists_outputs():
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_run_mock",
            "owner_user_id": "owner-run-mock-api",
            "prompt_scope_notes": "対象は平林様 Economics のみ",
            "model_report": "mock/report-model",
        },
    )
    job_id = created.json()["job_id"]
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/sources",
        json={
            "source_type": "doc",
            "display_name": "面談メモ",
            "snapshot_text": "4月は需要曲線の読み取りを扱った。",
        },
    )

    draft = _minimal_pattern_b_markdown("本文です。")
    response = client.post(
        f"/api/monthly-reports/jobs/{job_id}/run-mock",
        json={"content": draft},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"

    artifacts = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts")
    assert artifacts.status_code == 200
    assert artifacts.json()["artifacts"][0]["artifact_type"] == "draft_markdown"
    assert artifacts.json()["artifacts"][0]["content"] == draft

    validations = client.get(f"/api/monthly-reports/jobs/{job_id}/validations")
    assert validations.status_code == 200
    assert validations.json()["validations"][0]["rule_id"] == "non_empty_markdown"
    assert validations.json()["validations"][0]["severity"] == "info"

    llm_calls = client.get(f"/api/monthly-reports/jobs/{job_id}/llm-calls")
    assert llm_calls.status_code == 200
    assert llm_calls.json()["llm_calls"][0]["prompt_kind"] == "report"
    assert llm_calls.json()["llm_calls"][0]["provider"] == "openrouter"
    assert llm_calls.json()["llm_calls"][0]["request_hash"].startswith("sha256:")
    assert llm_calls.json()["llm_calls"][0]["response_hash"].startswith("sha256:")
    assert "content" not in llm_calls.json()["llm_calls"][0]


def test_monthly_report_api_rejects_openrouter_run_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)
    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_openrouter_missing_key",
            "owner_user_id": "owner-openrouter-missing-key-api",
        },
    )

    response = client.post(
        f"/api/monthly-reports/jobs/{created.json()['job_id']}/run-openrouter"
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "OPENROUTER_API_KEY is not configured"


def test_monthly_report_api_runs_openrouter_pipeline_and_persists_outputs(
    monkeypatch,
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-secret")
    monkeypatch.setenv("OPENROUTER_MODEL_REPORT", "mock/report-model")
    monkeypatch.setenv("OPENROUTER_MAX_TOKENS", "64")

    def fake_complete(self, *, messages, model=None):
        assert model == "mock/report-model"
        assert "4月は需要曲線" in messages[1]["content"]
        return LLMCompletion(
            content=_minimal_pattern_b_markdown("OpenRouter本文です。"),
            resolved_model="mock/resolved-model",
        )

    monkeypatch.setattr(OpenRouterMonthlyReportProvider, "complete", fake_complete)

    app = create_app()
    client = TestClient(app)
    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_openrouter",
            "owner_user_id": "owner-openrouter-api",
            "model_report": "mock/report-model",
        },
    )
    job_id = created.json()["job_id"]
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/sources",
        json={
            "source_type": "doc",
            "display_name": "面談メモ",
            "snapshot_text": "4月は需要曲線の読み取りを扱った。",
        },
    )

    response = client.post(f"/api/monthly-reports/jobs/{job_id}/run-openrouter")

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    artifacts = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts")
    assert artifacts.json()["artifacts"][0]["content"] == (
        _minimal_pattern_b_markdown("OpenRouter本文です。")
    )


def test_monthly_report_api_run_openrouter_fills_missing_reproducibility_meta(
    monkeypatch,
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-secret")
    monkeypatch.setenv("OPENROUTER_MODEL_REPORT", "mock/report-model")
    monkeypatch.setenv("EB_MONTHLY_REPORT_PROMPT_VERSION", "monthly-report-vtest.1")
    monkeypatch.setenv("EB_APP_VERSION", "test-app-version")

    def fake_complete(self, *, messages, model=None):
        assert model == "mock/report-model"
        return LLMCompletion(
            content=_minimal_pattern_b_markdown("OpenRouter本文です。"),
            resolved_model="mock/resolved-model",
        )

    monkeypatch.setattr(OpenRouterMonthlyReportProvider, "complete", fake_complete)

    app = create_app()
    client = TestClient(app)
    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "demo_openrouter_meta",
            "owner_user_id": "owner-openrouter-meta-api",
        },
    )
    job_id = created.json()["job_id"]
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/sources",
        json={
            "source_type": "doc",
            "display_name": "面談メモ",
            "snapshot_text": "4月は需要曲線の読み取りを扱った。",
        },
    )

    response = client.post(f"/api/monthly-reports/jobs/{job_id}/run-openrouter")

    assert response.status_code == 200
    body = response.json()
    assert body["prompt_version"] == "monthly-report-vtest.1"
    assert body["template_hash"].startswith("sha256:")
    assert body["model_report"] == "mock/report-model"
    assert body["resolved_model_report"] == "mock/resolved-model"
    assert body["source_bundle_hash"].startswith("sha256:")
    assert body["app_version"] == "test-app-version"

    detail = client.get(f"/api/monthly-reports/jobs/{job_id}")
    assert detail.json()["prompt_version"] == "monthly-report-vtest.1"
    assert detail.json()["template_hash"] == body["template_hash"]
    assert detail.json()["model_report"] == "mock/report-model"
    assert detail.json()["resolved_model_report"] == "mock/resolved-model"
    assert detail.json()["source_bundle_hash"] == body["source_bundle_hash"]
    assert detail.json()["app_version"] == "test-app-version"


def test_monthly_report_api_rerun_respects_owner_active_job_limit():
    app = create_app()
    client = TestClient(app)

    payload = {
        "target_month": "2026-04",
        "household_key": "demo_rerun_limit",
        "owner_user_id": "owner-rerun-limit-api",
    }
    created_jobs = []
    for _ in range(3):
        response = client.post("/api/monthly-reports/jobs", json=payload)
        assert response.status_code == 200
        created_jobs.append(response.json())

    rejected = client.post(
        f"/api/monthly-reports/jobs/{created_jobs[0]['job_id']}/rerun"
    )

    assert rejected.status_code == 429
    assert "active generation jobs" in rejected.json()["detail"]


class _FakeRLSReadStore:
    def __init__(self, job: monthly_reports_router.MockJob) -> None:
        self.job = job
        self.calls: list[str] = []
        self.sources = [
            monthly_reports_router.MockSource(
                public_id="mrs_rls",
                job_id=job.public_id,
                source_type="google_doc",
            )
        ]
        self.artifacts = [
            monthly_reports_router.MockArtifact(
                public_id="mra_rls",
                job_id=job.public_id,
                artifact_type="draft_markdown",
            )
        ]
        self.validations = [
            monthly_reports_router.MockValidation(
                public_id="mrv_rls",
                job_id=job.public_id,
                rule_id="non_empty_markdown",
                severity="info",
                message="ok",
            )
        ]

    def list_jobs(self) -> list[monthly_reports_router.MockJob]:
        self.calls.append("list_jobs")
        return [self.job]

    def get(self, public_id: str) -> monthly_reports_router.MockJob:
        self.calls.append("get")
        if public_id != self.job.public_id:
            raise KeyError(public_id)
        return self.job

    def list_sources(self, public_id: str) -> list[monthly_reports_router.MockSource]:
        self.calls.append("list_sources")
        return list(self.sources)

    def record_source(
        self,
        public_id: str,
        *,
        source_type: str,
        display_name: str | None = None,
        snapshot_text: str | None = None,
        content_hash: str | None = None,
    ) -> monthly_reports_router.MockSource:
        self.calls.append("record_source")
        if public_id != self.job.public_id:
            raise KeyError(public_id)
        source = monthly_reports_router.MockSource(
            public_id=f"mrs_api_rls_{len(self.sources) + 1}",
            job_id=public_id,
            source_type=source_type,
            display_name=display_name,
            snapshot_text=snapshot_text,
            content_hash=content_hash,
        )
        self.sources.append(source)
        return source

    def list_artifacts(self, public_id: str) -> list[monthly_reports_router.MockArtifact]:
        self.calls.append("list_artifacts")
        return list(self.artifacts)

    def list_validations(self, public_id: str) -> list[monthly_reports_router.MockValidation]:
        self.calls.append("list_validations")
        return list(self.validations)

    def list_llm_calls(self, public_id: str) -> list[monthly_reports_router.MockLLMCall]:
        self.calls.append("list_llm_calls")
        return [
            monthly_reports_router.MockLLMCall(
                public_id="mrl_rls",
                job_id=public_id,
                prompt_kind="report",
                provider="openrouter",
            )
        ]

    def record_feedback(
        self,
        public_id: str,
        *,
        category: str,
        comment: str,
    ) -> monthly_reports_router.MockFeedback:
        self.calls.append("record_feedback")
        if public_id != self.job.public_id:
            raise KeyError(public_id)
        feedback = monthly_reports_router.MockFeedback(
            public_id=f"mrf_api_rls_{len(self.job.feedback) + 1}",
            job_id=public_id,
            category=category,
            comment=comment,
        )
        self.job.feedback.append(feedback)
        return feedback

    def record_artifact(
        self,
        public_id: str,
        *,
        artifact_type: str,
        content: str | None = None,
        content_hash: str | None = None,
    ) -> monthly_reports_router.MockArtifact:
        self.calls.append("record_artifact")
        if public_id != self.job.public_id:
            raise KeyError(public_id)
        artifact = monthly_reports_router.MockArtifact(
            public_id=f"mra_api_rls_{len(self.artifacts) + 1}",
            job_id=public_id,
            artifact_type=artifact_type,
            content=content,
            content_hash=content_hash,
        )
        self.artifacts.append(artifact)
        return artifact

    def record_validation(
        self,
        public_id: str,
        *,
        rule_id: str,
        severity: str,
        message: str,
        path: str | None = None,
    ) -> monthly_reports_router.MockValidation:
        self.calls.append("record_validation")
        if public_id != self.job.public_id:
            raise KeyError(public_id)
        validation = monthly_reports_router.MockValidation(
            public_id=f"mrv_api_rls_{len(self.validations) + 1}",
            job_id=public_id,
            rule_id=rule_id,
            severity=severity,
            message=message,
            path=path,
        )
        self.validations.append(validation)
        return validation


def _raise_if_direct_store_used():
    raise AssertionError("direct monthly report store should not be used for RLS reads")


def _supabase_token(
    *,
    sub: str,
    email: str,
    role: str = "authenticated",
    secret: str = "test-supabase-jwt-secret",
) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "aud": "authenticated",
            "exp": now + 300,
            "iat": now,
            "sub": sub,
            "email": email,
            "role": role,
        },
        secret,
        algorithm="HS256",
    )
