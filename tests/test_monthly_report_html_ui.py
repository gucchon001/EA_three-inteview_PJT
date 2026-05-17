from __future__ import annotations

import os
import re

import pytest
from fastapi.testclient import TestClient
import jwt

import eb_app.routers.monthly_reports as monthly_reports_router
from eb_app.main import create_app
from eb_app.monthly_reports.google_workspace import GoogleWorkspaceSource
from eb_app.monthly_reports.jobs import MockJobStore
from eb_app.monthly_reports.workflow import LLMCompletion, OpenRouterMonthlyReportProvider


_CSRF_RE = re.compile(r'name="csrf_token" value="(?P<token>[^"]+)"')


@pytest.fixture(autouse=True)
def isolated_monthly_report_store():
    old_store = monthly_reports_router._store
    monthly_reports_router._store = MockJobStore()
    yield
    monthly_reports_router._store = old_store


def test_monthly_report_ui_serves_html_pages_and_fragments():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    jobs = client.get("/monthly-reports/jobs")
    assert jobs.status_code == 200
    assert "text/html" in jobs.headers["content-type"]
    assert "レポート工房" in jobs.text
    assert "/monthly-reports/jobs/new" in jobs.text
    assert "/api/monthly-reports" not in jobs.text

    new_job = client.get("/monthly-reports/jobs/new")
    assert new_job.status_code == 200
    assert "text/html" in new_job.headers["content-type"]
    assert "ソース指定" in new_job.text
    assert 'name="prompt_scope_notes"' in new_job.text


def test_monthly_report_ui_create_job_returns_html_fragment():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    new_job = client.get("/monthly-reports/jobs/new")
    token = _CSRF_RE.search(new_job.text).group("token")

    created = client.post(
        "/monthly-reports/jobs",
        data={
            "csrf_token": token,
            "target_month": "2026-04",
            "household_key": "html_household",
            "owner_user_id": "html-ui-owner",
            "template_key": "pattern_b",
            "prompt_version": "monthly-report-v20260516.1",
            "prompt_scope_notes": "対象は平林様 Economics のみ",
        },
        headers={"HX-Request": "true"},
    )

    assert created.status_code == 200
    assert "text/html" in created.headers["content-type"]
    assert "mrj_" in created.text
    assert "queued" in created.text
    assert "/monthly-reports/jobs/" in created.text
    assert "/api/monthly-reports" not in created.text
    job_id = re.search(r"mrj_[a-z0-9]+", created.text).group(0)
    detail = client.get(f"/api/monthly-reports/jobs/{job_id}")
    assert detail.json()["prompt_scope_notes"] == "対象は平林様 Economics のみ"


def test_monthly_report_ui_create_job_is_idempotent_with_hidden_key():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    new_job = client.get("/monthly-reports/jobs/new")
    token = _CSRF_RE.search(new_job.text).group("token")
    idempotency_key = re.search(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        new_job.text,
    ).group("key")
    payload = {
        "csrf_token": token,
        "idempotency_key": idempotency_key,
        "target_month": "2026-04",
        "household_key": "html_idempotent_household",
        "owner_user_id": "html-idempotent-owner",
        "template_key": "pattern_b",
    }

    first = client.post("/monthly-reports/jobs", data=payload, headers={"HX-Request": "true"})
    second = client.post("/monthly-reports/jobs", data=payload, headers={"HX-Request": "true"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert re.search(r"mrj_[a-z0-9]+", first.text).group(0) == re.search(
        r"mrj_[a-z0-9]+",
        second.text,
    ).group(0)


def test_monthly_report_ui_rejects_post_without_csrf_token():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    client.get("/monthly-reports/jobs/new")
    rejected = client.post(
        "/monthly-reports/jobs",
        data={
            "target_month": "2026-04",
            "household_key": "html_household",
            "owner_user_id": "html-ui-owner",
        },
        headers={"HX-Request": "true"},
    )

    assert rejected.status_code == 403
    assert "text/html" in rejected.headers["content-type"]
    assert "CSRF" in rejected.text


def test_monthly_report_ui_sets_secure_csrf_cookie_outside_local_env(
    monkeypatch: pytest.MonkeyPatch,
):
    os.environ["EB_AUTH_MODE"] = "mock"
    monkeypatch.setenv("EB_ENV", "staging")
    app = create_app()
    client = TestClient(app)

    response = client.get("/monthly-reports/jobs/new")

    assert response.status_code == 200
    set_cookie = response.headers["set-cookie"]
    assert "eb_monthly_report_csrf=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "samesite=lax" in set_cookie.lower()
    assert "Secure" in set_cookie


def test_monthly_report_ui_reuses_existing_csrf_cookie_for_multiple_tabs():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    first = client.get("/monthly-reports/jobs/new")
    first_token = _CSRF_RE.search(first.text).group("token")
    second = client.get("/monthly-reports/jobs/new")
    second_token = _CSRF_RE.search(second.text).group("token")

    assert second_token == first_token


def test_monthly_report_html_get_fragments_use_rls_read_store_for_supabase_user(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:56321")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    app = create_app()
    client = TestClient(app)
    job = monthly_reports_router.MockJob(
        public_id="mrj_html_rls_owner",
        target_month="2026-04",
        household_key="html_rls_household",
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

    detail = client.get("/monthly-reports/jobs/mrj_html_rls_owner", headers=headers)
    status = client.get(
        "/monthly-reports/jobs/mrj_html_rls_owner/fragments/status",
        headers=headers,
    )
    preview = client.get(
        "/monthly-reports/jobs/mrj_html_rls_owner/fragments/preview",
        headers=headers,
    )
    sources = client.get(
        "/monthly-reports/jobs/mrj_html_rls_owner/fragments/sources",
        headers=headers,
    )
    validation = client.get(
        "/monthly-reports/jobs/mrj_html_rls_owner/fragments/validation",
        headers=headers,
    )

    assert detail.status_code == 200
    assert status.status_code == 200
    assert preview.status_code == 200
    assert sources.status_code == 200
    assert validation.status_code == 200
    assert read_store.calls == [
        "get",
        "get",
        "get",
        "list_artifacts",
        "get",
        "list_sources",
        "get",
        "list_validations",
    ]


def test_monthly_report_ui_edited_markdown_uses_rls_read_preflight_for_supabase_user(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:56321")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    app = create_app()
    client = TestClient(app)
    job = monthly_reports_router._store.create_job(
        target_month="2026-04",
        household_key="html_rls_edit_household",
        owner_user_id="user-a",
    )
    read_store = _FakeRLSReadStore(job)
    monkeypatch.setattr(
        monthly_reports_router,
        "_get_rls_read_store",
        lambda current_user: read_store,
    )
    headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}"
    }
    detail = client.get(f"/monthly-reports/jobs/{job.public_id}", headers=headers)
    token = _CSRF_RE.search(detail.text).group("token")
    read_store.calls.clear()

    saved = client.post(
        f"/monthly-reports/jobs/{job.public_id}/fragments/edited-markdown",
        data={"csrf_token": token, "edited_markdown": "# RLS final"},
        headers={**headers, "HX-Request": "true"},
    )

    assert saved.status_code == 200
    assert read_store.calls == ["get"]
    assert monthly_reports_router._store.list_artifacts(job.public_id)[-1].artifact_type == (
        "final_markdown"
    )


def test_monthly_report_ui_rerun_uses_rls_read_preflight_for_supabase_user(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:56321")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    app = create_app()
    client = TestClient(app)
    job = monthly_reports_router._store.create_job(
        target_month="2026-04",
        household_key="html_rls_rerun_household",
        owner_user_id="user-a",
    )
    read_store = _FakeRLSReadStore(job)
    monkeypatch.setattr(
        monthly_reports_router,
        "_get_rls_read_store",
        lambda current_user: read_store,
    )
    headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}"
    }
    detail = client.get(f"/monthly-reports/jobs/{job.public_id}", headers=headers)
    token = _CSRF_RE.search(detail.text).group("token")
    read_store.calls.clear()

    rerun = client.post(
        f"/monthly-reports/jobs/{job.public_id}/rerun",
        data={"csrf_token": token},
        headers={**headers, "HX-Request": "true"},
    )

    assert rerun.status_code == 200
    assert "queued" in rerun.text
    assert read_store.calls == ["get"]


def test_monthly_report_ui_source_action_uses_rls_read_preflight_for_supabase_user(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:56321")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    app = create_app()
    client = TestClient(app)
    job = monthly_reports_router._store.create_job(
        target_month="2026-04",
        household_key="html_rls_source_household",
        owner_user_id="user-a",
    )
    read_store = _FakeRLSReadStore(job)
    monkeypatch.setattr(
        monthly_reports_router,
        "_get_rls_read_store",
        lambda current_user: read_store,
    )
    headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}"
    }
    detail = client.get(f"/monthly-reports/jobs/{job.public_id}", headers=headers)
    token = _CSRF_RE.search(detail.text).group("token")
    read_store.calls.clear()

    saved = client.post(
        f"/monthly-reports/jobs/{job.public_id}/fragments/sources",
        data={
            "csrf_token": token,
            "source_type": "doc",
            "display_name": "RLS面談メモ",
            "snapshot_text": "RLS preflight後に保存",
        },
        headers={**headers, "HX-Request": "true"},
    )

    assert saved.status_code == 200
    assert read_store.calls == ["get"]
    assert monthly_reports_router._store.list_sources(job.public_id)[-1].display_name == (
        "RLS面談メモ"
    )


def test_monthly_report_ui_google_source_action_uses_rls_read_preflight_for_supabase_user(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:56321")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setattr(
        monthly_reports_router,
        "_resolve_google_workspace_access_token",
        lambda current_user: "fake-access-token",
    )

    class FakeGoogleWorkspaceClient:
        def __init__(self, *, access_token):
            assert access_token == "fake-access-token"

        def fetch_doc(self, *, document_id: str, display_name: str | None = None):
            assert document_id == "doc-id"
            return GoogleWorkspaceSource(
                source_type="google_doc",
                display_name=display_name or "RLS教師MTG",
                snapshot_text="RLS Google Doc本文",
                content_hash="sha256:rls-gdoc",
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
        household_key="html_rls_google_source_household",
        owner_user_id="user-a",
    )
    read_store = _FakeRLSReadStore(job)
    monkeypatch.setattr(
        monthly_reports_router,
        "_get_rls_read_store",
        lambda current_user: read_store,
    )
    headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}"
    }
    detail = client.get(f"/monthly-reports/jobs/{job.public_id}", headers=headers)
    token = _CSRF_RE.search(detail.text).group("token")
    read_store.calls.clear()

    fetched = client.post(
        f"/monthly-reports/jobs/{job.public_id}/fragments/google-sources",
        data={"csrf_token": token, "doc_ids": "doc-id"},
        headers={**headers, "HX-Request": "true"},
    )

    assert fetched.status_code == 200
    assert read_store.calls == ["get"]
    assert monthly_reports_router._store.list_sources(job.public_id)[-1].content_hash == (
        "sha256:rls-gdoc"
    )


def test_monthly_report_ui_feedback_action_uses_rls_read_preflight_for_supabase_user(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:56321")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    app = create_app()
    client = TestClient(app)
    job = monthly_reports_router._store.create_job(
        target_month="2026-04",
        household_key="html_rls_feedback_household",
        owner_user_id="user-a",
    )
    read_store = _FakeRLSReadStore(job)
    monkeypatch.setattr(
        monthly_reports_router,
        "_get_rls_read_store",
        lambda current_user: read_store,
    )
    headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}"
    }
    detail = client.get(f"/monthly-reports/jobs/{job.public_id}", headers=headers)
    token = _CSRF_RE.search(detail.text).group("token")
    read_store.calls.clear()

    feedback = client.post(
        f"/monthly-reports/jobs/{job.public_id}/fragments/feedback",
        data={
            "csrf_token": token,
            "category": "tone",
            "comment": "RLS preflight後に保存",
        },
        headers={**headers, "HX-Request": "true"},
    )

    assert feedback.status_code == 200
    assert read_store.calls == ["get"]
    assert len(monthly_reports_router._store.get(job.public_id).feedback) == 1


def test_monthly_report_ui_run_action_uses_rls_read_preflight_for_supabase_user(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:56321")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    app = create_app()
    client = TestClient(app)
    job = monthly_reports_router._store.create_job(
        target_month="2026-04",
        household_key="html_rls_run_household",
        owner_user_id="user-a",
    )
    read_store = _FakeRLSReadStore(job)
    monkeypatch.setattr(
        monthly_reports_router,
        "_get_rls_read_store",
        lambda current_user: read_store,
    )
    headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}"
    }
    detail = client.get(f"/monthly-reports/jobs/{job.public_id}", headers=headers)
    token = _CSRF_RE.search(detail.text).group("token")
    read_store.calls.clear()

    started = client.post(
        f"/monthly-reports/jobs/{job.public_id}/run",
        data={"csrf_token": token},
        headers={**headers, "HX-Request": "true"},
    )

    assert started.status_code == 200
    assert "running" in started.text
    assert read_store.calls == ["get"]


def test_monthly_report_ui_status_fragment_uses_html_namespace():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "fragment_household",
            "owner_user_id": "html-fragment-owner",
        },
    )
    job_id = created.json()["job_id"]

    fragment = client.get(f"/monthly-reports/jobs/{job_id}/fragments/status")

    assert fragment.status_code == 200
    assert "text/html" in fragment.headers["content-type"]
    assert "status:" in fragment.text
    assert "queued" in fragment.text


def test_monthly_report_ui_preview_and_validation_fragments_return_html():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "preview_household",
            "owner_user_id": "html-preview-owner",
        },
    )
    job_id = created.json()["job_id"]
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/artifacts",
        json={
            "artifact_type": "draft_markdown",
            "content": "# 4月度 月次レポート\n\nよく集中できています。",
            "content_hash": "sha256:html-preview",
        },
    )
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/validations",
        json={
            "rule_id": "non_empty_markdown",
            "severity": "info",
            "message": "本文があります",
        },
    )

    preview = client.get(f"/monthly-reports/jobs/{job_id}/fragments/preview")
    validation = client.get(f"/monthly-reports/jobs/{job_id}/fragments/validation")

    assert preview.status_code == 200
    assert "text/html" in preview.headers["content-type"]
    assert "4月度 月次レポート" in preview.text
    assert "sha256:html-preview" in preview.text
    assert "/api/monthly-reports" not in preview.text
    assert validation.status_code == 200
    assert "text/html" in validation.headers["content-type"]
    assert "non_empty_markdown" in validation.text
    assert "本文があります" in validation.text


def test_monthly_report_detail_exposes_edit_save_and_rerun_groundwork():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "edit_rerun_household",
            "owner_user_id": "html-edit-rerun-owner",
        },
    )
    job_id = created.json()["job_id"]

    detail = client.get(f"/monthly-reports/jobs/{job_id}")

    assert detail.status_code == 200
    assert "text/html" in detail.headers["content-type"]
    assert f'hx-post="/monthly-reports/jobs/{job_id}/fragments/edited-markdown"' in detail.text
    assert f'hx-post="/monthly-reports/jobs/{job_id}/rerun"' in detail.text
    assert 'name="edited_markdown"' in detail.text
    assert 'name="base_content_hash"' in detail.text
    assert "編集後Markdown保存" in detail.text
    assert "再生成" in detail.text
    assert "/api/monthly-reports" not in detail.text


def test_monthly_report_ui_saves_edited_markdown_as_final_artifact_fragment():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "edit_save_household",
            "owner_user_id": "html-edit-save-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    saved = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/edited-markdown",
        data={
            "csrf_token": token,
            "edited_markdown": "# 最終版\n\nご家庭向けの編集済み本文です。",
            "base_content_hash": "sha256:base",
        },
        headers={"HX-Request": "true"},
    )
    artifacts = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts")

    assert saved.status_code == 200
    assert "text/html" in saved.headers["content-type"]
    assert "final_markdown" in saved.text
    assert "ご家庭向けの編集済み本文です" in saved.text
    assert artifacts.json()["artifacts"][-1]["artifact_type"] == "final_markdown"


def test_monthly_report_ui_edited_markdown_action_is_idempotent_with_hidden_key():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "edit_idempotent_household",
            "owner_user_id": "html-edit-idempotent-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")
    idempotency_key = re.findall(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        detail.text,
    )[4]

    first = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/edited-markdown",
        data={
            "csrf_token": token,
            "idempotency_key": idempotency_key,
            "edited_markdown": "## 01 基本情報\n初回編集",
        },
        headers={"HX-Request": "true"},
    )
    second = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/edited-markdown",
        data={
            "csrf_token": token,
            "idempotency_key": idempotency_key,
            "edited_markdown": "## 01 基本情報\n二重送信",
        },
        headers={"HX-Request": "true"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert "初回編集" in second.text
    assert "二重送信" not in second.text

    artifacts = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts")
    assert len(artifacts.json()["artifacts"]) == 1
    assert artifacts.json()["artifacts"][0]["content"] == "## 01 基本情報\n初回編集"


def test_monthly_report_ui_rerun_action_returns_status_fragment():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "html_rerun_household",
            "owner_user_id": "html-rerun-owner",
            "template_key": "pattern_b",
        },
    )
    job_id = created.json()["job_id"]
    client.post(f"/api/monthly-reports/jobs/{job_id}/cancel")
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    rerun = client.post(
        f"/monthly-reports/jobs/{job_id}/rerun",
        data={"csrf_token": token},
        headers={"HX-Request": "true"},
    )

    assert rerun.status_code == 200
    assert "text/html" in rerun.headers["content-type"]
    assert "status:" in rerun.text
    assert "queued" in rerun.text


def test_monthly_report_ui_source_fragment_and_action_return_html():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "source_household",
            "owner_user_id": "html-source-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    empty = client.get(f"/monthly-reports/jobs/{job_id}/fragments/sources")
    saved = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/sources",
        data={
            "csrf_token": token,
            "source_type": "doc",
            "display_name": "面談メモ",
            "snapshot_text": "4月は単元確認を丁寧に進めました。",
            "content_hash": "sha256:html-source",
        },
        headers={"HX-Request": "true"},
    )

    assert empty.status_code == 200
    assert "text/html" in empty.headers["content-type"]
    assert "保存済みソースはまだありません" in empty.text
    assert saved.status_code == 200
    assert "text/html" in saved.headers["content-type"]
    assert "面談メモ" in saved.text
    assert "4月は単元確認" in saved.text
    assert "sha256:html-source" in saved.text
    assert "/api/monthly-reports" not in saved.text


def test_monthly_report_ui_source_action_is_idempotent_with_hidden_key():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "source_idempotent_household",
            "owner_user_id": "html-source-idempotent-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")
    idempotency_key = re.findall(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        detail.text,
    )[2]

    first = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/sources",
        data={
            "csrf_token": token,
            "idempotency_key": idempotency_key,
            "source_type": "doc",
            "display_name": "面談メモ",
            "snapshot_text": "4月は単元確認を丁寧に進めました。",
            "content_hash": "sha256:html-source-idempotent",
        },
        headers={"HX-Request": "true"},
    )
    second = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/sources",
        data={
            "csrf_token": token,
            "idempotency_key": idempotency_key,
            "source_type": "doc",
            "display_name": "二重送信",
            "snapshot_text": "これは保存されない",
            "content_hash": "sha256:changed",
        },
        headers={"HX-Request": "true"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert "面談メモ" in second.text
    assert "二重送信" not in second.text

    sources = client.get(f"/api/monthly-reports/jobs/{job_id}/sources")
    assert len(sources.json()["sources"]) == 1
    assert sources.json()["sources"][0]["display_name"] == "面談メモ"


def test_monthly_report_ui_source_action_rejects_missing_csrf_token():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "source_csrf_household",
            "owner_user_id": "html-source-csrf-owner",
        },
    )
    job_id = created.json()["job_id"]
    client.get(f"/monthly-reports/jobs/{job_id}")

    rejected = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/sources",
        data={
            "source_type": "doc",
            "display_name": "面談メモ",
            "snapshot_text": "本文",
        },
        headers={"HX-Request": "true"},
    )

    assert rejected.status_code == 403
    assert "text/html" in rejected.headers["content-type"]
    assert "CSRF" in rejected.text


def test_monthly_report_ui_google_source_action_returns_html_fragment(
    monkeypatch: pytest.MonkeyPatch,
):
    os.environ["EB_AUTH_MODE"] = "mock"
    monkeypatch.setattr(
        monthly_reports_router,
        "_resolve_google_workspace_access_token",
        lambda current_user: "fake-access-token",
    )

    class FakeGoogleWorkspaceClient:
        def __init__(self, *, access_token):
            assert access_token == "fake-access-token"

        def fetch_doc(self, *, document_id: str, display_name: str | None = None):
            assert document_id == "doc-id"
            return GoogleWorkspaceSource(
                source_type="google_doc",
                display_name=display_name or "教師MTG",
                snapshot_text="Google Doc本文",
                content_hash="sha256:gdoc",
            )

        def fetch_sheet_values(
            self,
            *,
            spreadsheet_id: str,
            range_name: str,
            display_name: str | None = None,
        ):
            assert spreadsheet_id == "sheet-id"
            assert range_name == "student!A1:B2"
            return GoogleWorkspaceSource(
                source_type="google_sheet",
                display_name=display_name or "student sheet",
                snapshot_text="Sheet本文",
                content_hash="sha256:sheet",
            )

    monkeypatch.setattr(
        monthly_reports_router,
        "GoogleWorkspaceClient",
        FakeGoogleWorkspaceClient,
    )
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "google_source_household",
            "owner_user_id": "html-google-source-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    fetched = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/google-sources",
        data={
            "csrf_token": token,
            "doc_ids": "doc-id",
            "spreadsheet_id": "sheet-id",
            "range_name": "student!A1:B2",
            "sheet_display_name": "学習計画表 student",
        },
        headers={"HX-Request": "true"},
    )

    assert fetched.status_code == 200
    assert "text/html" in fetched.headers["content-type"]
    assert "教師MTG" in fetched.text
    assert "Google Doc本文" in fetched.text
    assert "学習計画表 student" in fetched.text
    assert "Sheet本文" in fetched.text
    assert "/api/monthly-reports" not in fetched.text


def test_monthly_report_ui_google_source_action_is_idempotent_before_external_fetch(
    monkeypatch: pytest.MonkeyPatch,
):
    os.environ["EB_AUTH_MODE"] = "mock"
    monkeypatch.setattr(
        monthly_reports_router,
        "_resolve_google_workspace_access_token",
        lambda current_user: "fake-access-token",
    )
    calls = {"doc": 0}

    class FakeGoogleWorkspaceClient:
        def __init__(self, *, access_token):
            assert access_token == "fake-access-token"

        def fetch_doc(self, *, document_id: str, display_name: str | None = None):
            calls["doc"] += 1
            assert document_id == "doc-id"
            return GoogleWorkspaceSource(
                source_type="google_doc",
                display_name=display_name or "教師MTG",
                snapshot_text="Google Doc本文",
                content_hash="sha256:gdoc-idempotent",
            )

    monkeypatch.setattr(
        monthly_reports_router,
        "GoogleWorkspaceClient",
        FakeGoogleWorkspaceClient,
    )
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "google_source_idempotent_household",
            "owner_user_id": "html-google-source-idempotent-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")
    idempotency_keys = re.findall(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        detail.text,
    )
    google_idempotency_key = idempotency_keys[3]

    first = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/google-sources",
        data={
            "csrf_token": token,
            "idempotency_key": google_idempotency_key,
            "doc_ids": "doc-id",
        },
        headers={"HX-Request": "true"},
    )
    second = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/google-sources",
        data={
            "csrf_token": token,
            "idempotency_key": google_idempotency_key,
            "doc_ids": "changed-doc-id",
        },
        headers={"HX-Request": "true"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert "教師MTG" in second.text
    assert "changed-doc-id" not in second.text
    assert calls["doc"] == 1

    sources = client.get(f"/api/monthly-reports/jobs/{job_id}/sources")
    assert len(sources.json()["sources"]) == 1
    assert sources.json()["sources"][0]["content_hash"] == "sha256:gdoc-idempotent"


def test_monthly_report_ui_google_source_action_reports_missing_config(
    monkeypatch: pytest.MonkeyPatch,
):
    os.environ["EB_AUTH_MODE"] = "mock"
    monkeypatch.setattr(
        monthly_reports_router,
        "_resolve_google_workspace_access_token",
        lambda current_user: None,
    )
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "google_source_config_household",
            "owner_user_id": "html-google-source-config-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    fetched = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/google-sources",
        data={"csrf_token": token, "doc_ids": "doc-id"},
        headers={"HX-Request": "true"},
    )

    assert fetched.status_code == 503
    assert "text/html" in fetched.headers["content-type"]
    assert "Google Workspace access token is not configured" in fetched.text


def test_monthly_report_ui_google_source_action_sanitizes_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
):
    os.environ["EB_AUTH_MODE"] = "mock"
    monkeypatch.setattr(
        monthly_reports_router,
        "_resolve_google_workspace_access_token",
        lambda current_user: "fake-access-token",
    )

    class FailingGoogleWorkspaceClient:
        def __init__(self, *, access_token):
            assert access_token == "fake-access-token"

        def fetch_doc(self, *, document_id: str, display_name: str | None = None):
            from eb_app.monthly_reports.google_workspace import GoogleWorkspaceFetchError

            raise GoogleWorkspaceFetchError(
                "private provider body with fake-access-token"
            )

    monkeypatch.setattr(
        monthly_reports_router,
        "GoogleWorkspaceClient",
        FailingGoogleWorkspaceClient,
    )
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "google_source_failure_household",
            "owner_user_id": "html-google-source-failure-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    response = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/google-sources",
        data={"csrf_token": token, "doc_ids": "doc-id"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 502
    assert "Google Workspace source fetch failed" in response.text
    assert "fake-access-token" not in response.text
    assert "private provider body" not in response.text


def test_monthly_report_ui_google_source_action_rejects_missing_csrf_token():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "google_source_csrf_household",
            "owner_user_id": "html-google-source-csrf-owner",
        },
    )
    job_id = created.json()["job_id"]
    client.get(f"/monthly-reports/jobs/{job_id}")

    rejected = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/google-sources",
        data={"doc_ids": "doc-id"},
        headers={"HX-Request": "true"},
    )

    assert rejected.status_code == 403
    assert "text/html" in rejected.headers["content-type"]
    assert "CSRF" in rejected.text


def test_monthly_report_ui_feedback_action_returns_html_fragment():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "feedback_household",
            "owner_user_id": "html-feedback-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    feedback = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/feedback",
        data={
            "csrf_token": token,
            "category": "tone",
            "comment": "保護者向けにやや硬い",
        },
        headers={"HX-Request": "true"},
    )

    assert feedback.status_code == 200
    assert "text/html" in feedback.headers["content-type"]
    assert "tone" in feedback.text
    assert "保護者向けにやや硬い" in feedback.text
    assert "/api/monthly-reports" not in feedback.text


def test_monthly_report_ui_feedback_action_is_idempotent_with_hidden_key():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "feedback_idempotent_household",
            "owner_user_id": "html-feedback-idempotent-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")
    idempotency_key = re.findall(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        detail.text,
    )[5]

    first = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/feedback",
        data={
            "csrf_token": token,
            "idempotency_key": idempotency_key,
            "category": "tone",
            "comment": "保護者向けにやや硬い",
        },
        headers={"HX-Request": "true"},
    )
    second = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/feedback",
        data={
            "csrf_token": token,
            "idempotency_key": idempotency_key,
            "category": "tone",
            "comment": "二重送信",
        },
        headers={"HX-Request": "true"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert "保護者向けにやや硬い" in second.text
    assert "二重送信" not in second.text

    detail_after = client.get(f"/api/monthly-reports/jobs/{job_id}")
    assert detail_after.json()["feedback_count"] == 1


def test_monthly_report_ui_feedback_rejects_missing_csrf_token():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "feedback_csrf_household",
            "owner_user_id": "html-feedback-csrf-owner",
        },
    )
    job_id = created.json()["job_id"]
    client.get(f"/monthly-reports/jobs/{job_id}")

    feedback = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/feedback",
        data={
            "category": "tone",
            "comment": "保護者向けにやや硬い",
        },
        headers={"HX-Request": "true"},
    )

    assert feedback.status_code == 403
    assert "text/html" in feedback.headers["content-type"]
    assert "CSRF" in feedback.text


def test_monthly_report_ui_run_action_returns_status_fragment():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "run_household",
            "owner_user_id": "html-run-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    started = client.post(
        f"/monthly-reports/jobs/{job_id}/run",
        data={"csrf_token": token},
        headers={"HX-Request": "true"},
    )

    assert started.status_code == 200
    assert "text/html" in started.headers["content-type"]
    assert "status:" in started.text
    assert "running" in started.text
    assert "fetch_sources" in started.text
    assert "/api/monthly-reports" not in started.text


def test_monthly_report_ui_mock_run_persists_preview_and_validation_fragments():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "mock_run_household",
            "owner_user_id": "html-mock-run-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    completed = client.post(
        f"/monthly-reports/jobs/{job_id}/run",
        data={"csrf_token": token, "run_mode": "mock"},
        headers={"HX-Request": "true"},
    )
    preview = client.get(f"/monthly-reports/jobs/{job_id}/fragments/preview")
    validation = client.get(f"/monthly-reports/jobs/{job_id}/fragments/validation")
    detail_after = client.get(f"/api/monthly-reports/jobs/{job_id}")

    assert completed.status_code == 200
    assert "text/html" in completed.headers["content-type"]
    assert "succeeded" in completed.text
    assert "draft_markdown" in preview.text
    assert "## 05 学習の進捗" in preview.text
    assert "non_empty_markdown" in validation.text
    body = detail_after.json()
    assert body["prompt_version"] == "monthly-report-v20260516.1"
    assert body["model_report"] == "mock/html-ui-model"
    assert body["template_hash"].startswith("sha256:")
    assert body["source_bundle_hash"].startswith("sha256:")
    assert body["resolved_model_report"] == "mock/report-model"
    assert body["app_version"] == "local"


def test_monthly_report_ui_mock_run_is_idempotent_with_hidden_key():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "mock_run_idempotent_household",
            "owner_user_id": "html-mock-run-idempotent-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")
    idempotency_key = re.search(
        r'name="run_idempotency_key" value="(?P<key>[^"]+)"',
        detail.text,
    ).group("key")

    first = client.post(
        f"/monthly-reports/jobs/{job_id}/run",
        data={
            "csrf_token": token,
            "idempotency_key": idempotency_key,
            "run_mode": "mock",
        },
        headers={"HX-Request": "true"},
    )
    second = client.post(
        f"/monthly-reports/jobs/{job_id}/run",
        data={
            "csrf_token": token,
            "idempotency_key": idempotency_key,
            "run_mode": "mock",
        },
        headers={"HX-Request": "true"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert "succeeded" in first.text
    assert "succeeded" in second.text


def test_monthly_report_ui_openrouter_run_persists_preview_and_validation_fragments(
    monkeypatch: pytest.MonkeyPatch,
):
    os.environ["EB_AUTH_MODE"] = "mock"
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-secret")
    monkeypatch.setenv("OPENROUTER_MODEL_REPORT", "mock/openrouter-html-model")
    monkeypatch.setenv("EB_MONTHLY_REPORT_PROMPT_VERSION", "monthly-report-vhtml-openrouter.1")
    monkeypatch.setenv("EB_APP_VERSION", "html-openrouter-app")

    def fake_complete(self, *, messages, model=None):
        assert model == "mock/openrouter-html-model"
        return LLMCompletion(
            content="\n\n".join(
                [
                    "## 01 基本情報\n本文",
                    "## 02 塾での様子\n本文",
                    "## 03 授業内容\n本文",
                    "## 04 課題とアドバイス\n本文",
                    "## 05 学習の進捗\n本文",
                    "## 07 今後の授業計画\n本文",
                ]
            ),
            resolved_model="mock/openrouter-resolved-html-model",
            input_tokens=100,
            output_tokens=50,
            finish_reason="stop",
        )

    monkeypatch.setattr(OpenRouterMonthlyReportProvider, "complete", fake_complete)
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "openrouter_run_household",
            "owner_user_id": "html-openrouter-run-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    completed = client.post(
        f"/monthly-reports/jobs/{job_id}/run",
        data={"csrf_token": token, "run_mode": "openrouter"},
        headers={"HX-Request": "true"},
    )
    preview = client.get(f"/monthly-reports/jobs/{job_id}/fragments/preview")
    validation = client.get(f"/monthly-reports/jobs/{job_id}/fragments/validation")
    detail_after = client.get(f"/api/monthly-reports/jobs/{job_id}")

    assert completed.status_code == 200
    assert "text/html" in completed.headers["content-type"]
    assert "succeeded" in completed.text
    assert "draft_markdown" in preview.text
    assert "## 05 学習の進捗" in preview.text
    assert "non_empty_markdown" in validation.text
    body = detail_after.json()
    assert body["prompt_version"] == "monthly-report-vhtml-openrouter.1"
    assert body["model_report"] == "mock/openrouter-html-model"
    assert body["resolved_model_report"] == "mock/openrouter-resolved-html-model"
    assert body["app_version"] == "html-openrouter-app"


def test_monthly_report_ui_openrouter_run_reports_missing_api_key(
    monkeypatch: pytest.MonkeyPatch,
):
    os.environ["EB_AUTH_MODE"] = "mock"
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "openrouter_missing_key_household",
            "owner_user_id": "html-openrouter-missing-key-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    response = client.post(
        f"/monthly-reports/jobs/{job_id}/run",
        data={"csrf_token": token, "run_mode": "openrouter"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 503
    assert "text/html" in response.headers["content-type"]
    assert "OPENROUTER_API_KEY is not configured" in response.text


class _FakeRLSReadStore:
    def __init__(self, job: monthly_reports_router.MockJob) -> None:
        self.job = job
        self.calls: list[str] = []

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
        return [
            monthly_reports_router.MockSource(
                public_id="mrs_html_rls",
                job_id=public_id,
                source_type="google_doc",
                display_name="RLS source",
                snapshot_text="RLS source text",
            )
        ]

    def list_artifacts(self, public_id: str) -> list[monthly_reports_router.MockArtifact]:
        self.calls.append("list_artifacts")
        return [
            monthly_reports_router.MockArtifact(
                public_id="mra_html_rls",
                job_id=public_id,
                artifact_type="draft_markdown",
                content="## 01 基本情報\nRLS draft",
                content_hash="sha256:html-rls",
            )
        ]

    def list_validations(self, public_id: str) -> list[monthly_reports_router.MockValidation]:
        self.calls.append("list_validations")
        return [
            monthly_reports_router.MockValidation(
                public_id="mrv_html_rls",
                job_id=public_id,
                rule_id="non_empty_markdown",
                severity="info",
                message="ok",
            )
        ]


def _raise_if_direct_store_used():
    raise AssertionError("direct monthly report store should not be used for HTML RLS reads")


def _supabase_token(
    *,
    sub: str,
    email: str,
    secret: str = "test-supabase-jwt-secret",
) -> str:
    return jwt.encode(
        {
            "aud": "authenticated",
            "exp": 4102444800,
            "iat": 1760000000,
            "sub": sub,
            "email": email,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )
