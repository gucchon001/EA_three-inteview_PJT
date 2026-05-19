from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

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


def _create_exported_monthly_report_job(client: TestClient) -> tuple[str, str, str]:
    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "html_source_household",
            "owner_user_id": "html-source-owner",
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
    assert completed.status_code == 200
    artifacts = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts").json()[
        "artifacts"
    ]
    artifact_hash = artifacts[-1]["content_hash"]
    approval_fragment = client.get(f"/monthly-reports/jobs/{job_id}/fragments/approval")
    approval_key = re.search(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        approval_fragment.text,
    ).group("key")
    approval = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/approval",
        data={
            "csrf_token": token,
            "idempotency_key": approval_key,
            "artifact_hash": artifact_hash,
            "confirm_ready": "yes",
        },
        headers={"HX-Request": "true"},
    )
    assert approval.status_code == 200
    export_fragment = client.get(f"/monthly-reports/jobs/{job_id}/fragments/export")
    export_key = re.search(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        export_fragment.text,
    ).group("key")
    export = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/export",
        data={
            "csrf_token": token,
            "idempotency_key": export_key,
            "artifact_hash": artifact_hash,
        },
        headers={"HX-Request": "true"},
    )
    assert export.status_code == 200
    export_artifact = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts").json()[
        "artifacts"
    ][-1]
    return job_id, token, export_artifact["content_hash"]


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
    assert "htmx-busy-overlay" in jobs.text
    assert "htmx-error-banner" in jobs.text
    assert "htmx:responseError" in jobs.text

    new_job = client.get("/monthly-reports/jobs/new")
    assert new_job.status_code == 200
    assert "text/html" in new_job.headers["content-type"]
    assert "新規読み込みの流れ" in new_job.text
    assert "Google Docs URL / Sheets URL は、作成後に開くジョブ詳細" in new_job.text
    assert "ジョブ基本情報" in new_job.text
    assert "ジョブを作成してソース登録へ進む" in new_job.text
    assert 'name="prompt_scope_notes"' in new_job.text
    assert "処理中です" in new_job.text

    favicon = client.get("/favicon.ico")
    assert favicon.status_code == 204


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
    assert "次はデータソース登録です" in created.text
    assert "ソース登録へ進む" in created.text
    assert "取得してレポート生成" in created.text
    assert "/api/monthly-reports" not in created.text
    job_id = re.search(r"mrj_[a-z0-9]+", created.text).group(0)
    detail = client.get(f"/api/monthly-reports/jobs/{job_id}")
    assert detail.json()["prompt_scope_notes"] == "対象は平林様 Economics のみ"


def test_monthly_report_empty_detail_explains_source_then_generate_flow():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "empty_detail_household",
            "owner_user_id": "html-empty-detail-owner",
        },
    )
    job_id = created.json()["job_id"]

    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    preview = client.get(f"/monthly-reports/jobs/{job_id}/fragments/preview")

    assert detail.status_code == 200
    assert "まだレポートは生成されていません" in detail.text
    assert "Google Docs / Sheetsを登録" in detail.text
    assert "取得してレポート生成" in detail.text
    assert "実行状況・ログ" in detail.text
    assert "/fragments/operation-log" in detail.text
    assert preview.status_code == 200
    assert "まだレポートビューに表示できる生成物はありません" in preview.text

    log = client.get(f"/monthly-reports/jobs/{job_id}/fragments/operation-log")

    assert log.status_code == 200
    assert "ジョブ作成" in log.text
    assert "データソース取得" in log.text
    assert "未実行" in log.text
    assert "Google Docs / Sheets URL投入" in log.text
    assert re.search(r"\d{4}-\d{2}-\d{2}", log.text)


def test_monthly_report_new_job_page_exposes_admin_tuning_fields_only_for_admin(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "mock")
    monkeypatch.setenv("EB_MOCK_USER_EMAIL", "mock-admin@tomonokai-corp.com")
    app = create_app()
    client = TestClient(app)

    admin_page = client.get("/monthly-reports/jobs/new")

    assert admin_page.status_code == 200
    assert "管理者チューニング" in admin_page.text
    assert 'name="prompt_version"' in admin_page.text
    assert 'name="model_report"' in admin_page.text
    assert 'name="model_light"' in admin_page.text

    monkeypatch.setenv("EB_MOCK_USER_EMAIL", "mock-user@tomonokai-corp.com")
    user_page = client.get("/monthly-reports/jobs/new")

    assert user_page.status_code == 200
    assert "管理者チューニング" not in user_page.text
    assert 'name="prompt_version"' not in user_page.text
    assert 'name="model_report"' not in user_page.text
    assert 'name="model_light"' not in user_page.text
    assert 'name="prompt_scope_notes"' in user_page.text


def test_monthly_report_ui_create_job_persists_model_overrides_for_admin_only(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "mock")
    monkeypatch.setenv("EB_MOCK_USER_EMAIL", "mock-admin@tomonokai-corp.com")
    app = create_app()
    client = TestClient(app)

    admin_page = client.get("/monthly-reports/jobs/new")
    admin_token = _CSRF_RE.search(admin_page.text).group("token")
    admin_created = client.post(
        "/monthly-reports/jobs",
        data={
            "csrf_token": admin_token,
            "target_month": "2026-04",
            "household_key": "admin_tuning_household",
            "owner_user_id": "admin-tuning-owner",
            "template_key": "pattern_b",
            "prompt_version": "monthly-report-v20260517.admin",
            "model_report": "openrouter/admin-report-model",
            "model_light": "openrouter/admin-light-model",
        },
        headers={"HX-Request": "true"},
    )

    assert admin_created.status_code == 200
    admin_job_id = re.search(r"mrj_[a-z0-9]+", admin_created.text).group(0)
    admin_detail = client.get(f"/api/monthly-reports/jobs/{admin_job_id}").json()
    assert admin_detail["prompt_version"] == "monthly-report-v20260517.admin"
    assert admin_detail["model_report"] == "openrouter/admin-report-model"
    assert admin_detail["model_light"] == "openrouter/admin-light-model"

    monkeypatch.setenv("EB_MOCK_USER_EMAIL", "mock-user@tomonokai-corp.com")
    user_page = client.get("/monthly-reports/jobs/new")
    user_token = _CSRF_RE.search(user_page.text).group("token")
    user_created = client.post(
        "/monthly-reports/jobs",
        data={
            "csrf_token": user_token,
            "target_month": "2026-04",
            "household_key": "user_tuning_household",
            "owner_user_id": "user-tuning-owner",
            "template_key": "pattern_b",
            "prompt_version": "monthly-report-v20260517.forbidden",
            "model_report": "openrouter/forbidden-report-model",
            "model_light": "openrouter/forbidden-light-model",
        },
        headers={"HX-Request": "true"},
    )

    assert user_created.status_code == 200
    user_job_id = re.search(r"mrj_[a-z0-9]+", user_created.text).group(0)
    user_detail = client.get(f"/api/monthly-reports/jobs/{user_job_id}").json()
    assert user_detail["prompt_version"] is None
    assert user_detail["model_report"] is None
    assert user_detail["model_light"] is None


def test_monthly_report_jobs_page_shows_next_action_and_latest_artifact_summary():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "summary_household",
            "owner_user_id": "html-summary-owner",
        },
    )
    job_id = created.json()["job_id"]
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/sources",
        json={
            "source_type": "google_doc",
            "display_name": "面談メモ",
            "snapshot_text": "Physicsの面談メモ",
        },
    )
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/artifacts",
        json={
            "artifact_type": "draft_markdown",
            "content": "## 01 基本情報\n本文",
            "content_hash": "sha256:list-summary-draft",
        },
    )
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/validations",
        json={
            "rule_id": "needs_fix",
            "severity": "error",
            "message": "送付前に修正が必要です",
        },
    )

    jobs = client.get("/monthly-reports/jobs")

    assert jobs.status_code == 200
    assert "次の操作" in jobs.text
    assert "素材/成果物" in jobs.text
    assert 'aria-label="ジョブ絞り込み"' in jobs.text
    assert 'name="q"' in jobs.text
    assert 'name="status"' in jobs.text
    assert "source 1 / artifact 1" in jobs.text
    assert "sha256:list-summary-draft" in jobs.text
    assert "1 validation error" in jobs.text
    assert "ソース確認後、生成開始" in jobs.text
    assert f"/monthly-reports/jobs/{job_id}#sources-panel" in jobs.text
    assert "/api/monthly-reports" not in jobs.text


def test_monthly_report_jobs_page_filters_by_query_and_status():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    alpha = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "alpha_household",
            "owner_user_id": "html-filter-owner",
        },
    ).json()["job_id"]
    beta = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-05",
            "household_key": "beta_household",
            "owner_user_id": "html-filter-owner",
        },
    ).json()["job_id"]

    by_query = client.get("/monthly-reports/jobs?q=alpha")
    by_status = client.get("/monthly-reports/jobs?status=queued")

    assert by_query.status_code == 200
    assert alpha in by_query.text
    assert beta not in by_query.text
    assert "表示 1 件" in by_query.text
    assert 'value="alpha"' in by_query.text
    assert by_status.status_code == 200
    assert alpha in by_status.text
    assert beta in by_status.text
    assert '<option value="queued" selected>queued</option>' in by_status.text


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
    monkeypatch.setattr(
        monthly_reports_router,
        "_get_store",
        lambda: _TrackingDirectStore(monthly_reports_router._store),
    )
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
    assert read_store.calls.count("get") >= 5
    assert "list_sources" in read_store.calls
    assert "list_artifacts" in read_store.calls
    assert "list_validations" in read_store.calls


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
    assert "record_artifact" in read_store.calls
    assert read_store.artifacts[-1].artifact_type == "final_markdown"
    assert monthly_reports_router._store.list_artifacts(job.public_id) == []


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
    job.status = "cancelled"
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
        data={"csrf_token": token, "idempotency_key": "rls-rerun-preflight-key"},
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
    assert read_store.calls[:2] == ["get", "record_source"]
    assert read_store.sources[-1].display_name == "RLS面談メモ"
    assert monthly_reports_router._store.list_sources(job.public_id) == []


def test_monthly_report_ui_source_action_rejects_empty_text():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)
    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "empty_source_household",
            "owner_user_id": "html-empty-source-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    saved = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/sources",
        data={
            "csrf_token": token,
            "source_type": "doc",
            "display_name": "面談メモ",
            "snapshot_text": "   ",
        },
        headers={"HX-Request": "true"},
    )

    assert saved.status_code == 422
    assert "source text is required" in saved.text
    assert monthly_reports_router._store.list_sources(job_id) == []


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
    assert read_store.calls[:2] == ["get", "record_source"]
    assert read_store.sources[-1].content_hash == "sha256:rls-gdoc"
    assert monthly_reports_router._store.list_sources(job.public_id) == []


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
    assert read_store.calls[:2] == ["get", "record_feedback"]
    assert "record_feedback" in read_store.calls
    assert any(item.comment == "RLS preflight後に保存" for item in read_store.job.feedback)


def test_monthly_report_ui_routes_supabase_user_stage_generation_to_worker_queue(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:56321")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setenv("EB_CLOUD_RUN_WORKER_JOB_PROJECT_ID", "project-id")
    monkeypatch.setenv("EB_CLOUD_RUN_WORKER_JOB_REGION", "asia-northeast1")
    monkeypatch.setenv("EB_CLOUD_RUN_WORKER_JOB_NAME", "monthly-report-worker-staging")
    monkeypatch.setattr(
        monthly_reports_router,
        "_resolve_google_workspace_access_token",
        lambda current_user: "fake-access-token",
    )
    trigger_calls: list[dict[str, object]] = []

    class FakeGoogleWorkspaceClient:
        def __init__(self, *, access_token):
            assert access_token == "fake-access-token"

        def fetch_doc(self, *, document_id: str, display_name: str | None = None):
            assert document_id == "https://docs.google.com/document/d/doc-id/edit"
            return GoogleWorkspaceSource(
                source_type="google_doc",
                display_name=display_name or "RLS面談メモ",
                snapshot_text="RLS Google Doc本文",
                content_hash="sha256:rls-gdoc-worker-queue",
            )

    class FakeCloudRunJobExecutor:
        def __init__(
            self,
            *,
            project_id: str,
            region: str,
            job_name: str,
            token_provider,
            timeout_seconds: float,
            http_client=None,
        ) -> None:
            trigger_calls.append(
                {
                    "project_id": project_id,
                    "region": region,
                    "job_name": job_name,
                    "timeout_seconds": timeout_seconds,
                }
            )

        def run(self, *, env_vars=None):
            trigger_calls[-1]["env_vars"] = env_vars
            return {"name": f"operations/{env_vars['EB_WORKER_JOB_ID']}"}

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
    monkeypatch.setattr(
        monthly_reports_router,
        "GoogleWorkspaceClient",
        FakeGoogleWorkspaceClient,
    )
    monkeypatch.setattr(
        monthly_reports_router,
        "CloudRunJobExecutor",
        FakeCloudRunJobExecutor,
    )
    detail = client.get(f"/monthly-reports/jobs/{job.public_id}", headers=headers)
    token = _CSRF_RE.search(detail.text).group("token")
    read_store.calls.clear()
    assert "通常ユーザーは「生成開始」「取得してレポート生成」で worker へ依頼してください。" in detail.text

    started = client.post(
        f"/monthly-reports/jobs/{job.public_id}/run",
        data={"csrf_token": token, "idempotency_key": "blocked-run-key"},
        headers={**headers, "HX-Request": "true"},
    )
    generated = client.post(
        f"/monthly-reports/jobs/{job.public_id}/fragments/google-sources",
        data={
            "csrf_token": token,
            "idempotency_key": "blocked-google-generate-key",
            "doc_ids": "https://docs.google.com/document/d/doc-id/edit",
            "after_fetch_action": "generate_openrouter",
        },
        headers={**headers, "HX-Request": "true"},
    )
    rejected_mock = client.post(
        f"/monthly-reports/jobs/{job.public_id}/run",
        data={
            "csrf_token": token,
            "idempotency_key": "blocked-mock-run-key",
            "run_mode": "mock",
        },
        headers={**headers, "HX-Request": "true"},
    )

    assert started.status_code == 200
    assert "queued" in started.text
    assert "worker" in started.text
    assert generated.status_code == 200
    assert "worker" in generated.text
    assert "RLS面談メモ" in generated.text
    assert rejected_mock.status_code == 403
    assert "通常UIの即時生成（モック生成 / OpenRouter生成）は mock/admin の補助導線です。" in rejected_mock.text
    assert "record_source" in read_store.calls
    assert monthly_reports_router._store.list_sources(job.public_id) == []
    audit_logs = monthly_reports_router._store.list_audit_logs(job.public_id)
    assert [entry.action for entry in audit_logs] == [
        "monthly_report_worker_owned_workflow_requested",
        "monthly_report_worker_job_triggered",
        "monthly_report_worker_owned_workflow_requested",
        "monthly_report_worker_job_triggered",
    ]
    assert audit_logs[0].metadata["trigger"] == "html_run"
    assert audit_logs[0].metadata["mode"] == "stage"
    assert audit_logs[0].metadata["boundary"] == "worker_owned_workflow"
    assert audit_logs[1].metadata["trigger"] == "html_run"
    assert audit_logs[1].metadata["operation_name"] == f"operations/{job.public_id}"
    assert audit_logs[2].metadata["trigger"] == "html_google_sources"
    assert audit_logs[3].metadata["trigger"] == "html_google_sources"
    assert trigger_calls == [
        {
            "project_id": "project-id",
            "region": "asia-northeast1",
            "job_name": "monthly-report-worker-staging",
            "timeout_seconds": 15.0,
            "env_vars": {"EB_WORKER_JOB_ID": job.public_id},
        },
        {
            "project_id": "project-id",
            "region": "asia-northeast1",
            "job_name": "monthly-report-worker-staging",
            "timeout_seconds": 15.0,
            "env_vars": {"EB_WORKER_JOB_ID": job.public_id},
        },
    ]


def test_monthly_report_ui_artifact_actions_use_rls_write_store_for_supabase_user(
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
        household_key="html_rls_artifact_household",
        owner_user_id="user-a",
    )
    job.status = "succeeded"
    read_store = _FakeRLSReadStore(job)
    read_store.artifacts = [
        monthly_reports_router.MockArtifact(
            public_id="mra_html_rls_final",
            job_id=job.public_id,
            artifact_type="final_markdown",
            content="# final\n\nRLS artifact flow",
            content_hash="sha256:html-rls-final",
        )
    ]
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

    edit_fragment = client.get(
        f"/monthly-reports/jobs/{job.public_id}/fragments/preview",
        headers=headers,
    )
    assert edit_fragment.status_code == 200
    read_store.calls.clear()
    edited_markdown = client.post(
        f"/monthly-reports/jobs/{job.public_id}/fragments/edited-markdown",
        data={
            "csrf_token": token,
            "idempotency_key": "html-rls-edited-markdown-key",
            "base_content_hash": "sha256:html-rls-final",
            "edited_markdown": "## 01 Basic information\nRLS final markdown",
        },
        headers={**headers, "HX-Request": "true"},
    )
    assert edited_markdown.status_code == 200
    assert "record_artifact" in read_store.calls
    final_markdown_artifact = read_store.artifacts[-1]
    assert final_markdown_artifact.artifact_type == "final_markdown"

    approval_fragment = client.get(
        f"/monthly-reports/jobs/{job.public_id}/fragments/approval",
        headers=headers,
    )
    approval_key = re.search(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        approval_fragment.text,
    ).group("key")
    read_store.calls.clear()
    approval = client.post(
        f"/monthly-reports/jobs/{job.public_id}/fragments/approval",
        data={
            "csrf_token": token,
            "idempotency_key": approval_key,
            "artifact_hash": final_markdown_artifact.content_hash,
            "confirm_ready": "yes",
        },
        headers={**headers, "HX-Request": "true"},
    )
    assert approval.status_code == 200
    assert "record_artifact" in read_store.calls
    approval_artifact = read_store.artifacts[-1]
    assert approval_artifact.artifact_type == "approval"

    export_fragment = client.get(
        f"/monthly-reports/jobs/{job.public_id}/fragments/export",
        headers=headers,
    )
    export_key = re.search(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        export_fragment.text,
    ).group("key")
    read_store.calls.clear()
    export = client.post(
        f"/monthly-reports/jobs/{job.public_id}/fragments/export",
        data={
            "csrf_token": token,
            "idempotency_key": export_key,
            "artifact_hash": final_markdown_artifact.content_hash,
        },
        headers={**headers, "HX-Request": "true"},
    )
    assert export.status_code == 200
    assert "record_artifact" in read_store.calls
    export_artifact = read_store.artifacts[-1]
    assert export_artifact.artifact_type == "export_html"

    html_source_fragment = client.get(
        f"/monthly-reports/jobs/{job.public_id}/fragments/html-source",
        headers=headers,
    )
    html_source_key = re.search(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        html_source_fragment.text,
    ).group("key")
    read_store.calls.clear()
    edited = client.post(
        f"/monthly-reports/jobs/{job.public_id}/fragments/html-source",
        data={
            "csrf_token": token,
            "idempotency_key": html_source_key,
            "base_export_hash": export_artifact.content_hash,
            "html_source": "<article>RLS edited export</article>",
        },
        headers={**headers, "HX-Request": "true"},
    )
    assert edited.status_code == 200
    assert "record_artifact" in read_store.calls
    edited_export = read_store.artifacts[-1]
    assert edited_export.artifact_type == "export_html"

    distribution_fragment = client.get(
        f"/monthly-reports/jobs/{job.public_id}/fragments/distribution",
        headers=headers,
    )
    distribution_key = re.search(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        distribution_fragment.text,
    ).group("key")
    read_store.calls.clear()
    distribution = client.post(
        f"/monthly-reports/jobs/{job.public_id}/fragments/distribution",
        data={
            "csrf_token": token,
            "idempotency_key": distribution_key,
            "export_hash": edited_export.content_hash,
        },
        headers={**headers, "HX-Request": "true"},
    )
    assert distribution.status_code == 200
    assert "record_artifact" in read_store.calls
    assert read_store.artifacts[-1].artifact_type == "distribution_package"
    audit_logs = monthly_reports_router._store.list_audit_logs(job.public_id)
    assert [entry.action for entry in audit_logs] == [
        "monthly_report_approval_saved",
        "monthly_report_export_html_saved",
        "monthly_report_export_html_edited",
        "monthly_report_distribution_package_saved",
    ]


def test_monthly_report_ui_source_summary_uses_rls_write_store_for_supabase_user(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:56321")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-secret")
    monkeypatch.setenv("OPENROUTER_MODEL_LIGHT", "mock/light-summary")

    def fake_complete(self, *, messages, model=None):
        return LLMCompletion(
            content="## 取得内容サマリー\nRLS source summary",
            resolved_model="mock/light-summary-resolved",
            input_tokens=12,
            output_tokens=8,
            finish_reason="stop",
        )

    monkeypatch.setattr(OpenRouterMonthlyReportProvider, "complete", fake_complete)
    app = create_app()
    client = TestClient(app)
    job = monthly_reports_router._store.create_job(
        target_month="2026-04",
        household_key="html_rls_source_summary_household",
        owner_user_id="user-a",
    )
    read_store = _FakeRLSReadStore(job)
    read_store.sources = [
        monthly_reports_router.MockSource(
            public_id="mrs_html_rls_summary",
            job_id=job.public_id,
            source_type="google_doc",
            display_name="RLS source",
            snapshot_text="RLS source body",
            content_hash="sha256:rls-source",
        )
    ]
    monkeypatch.setattr(
        monthly_reports_router,
        "_get_rls_read_store",
        lambda current_user: read_store,
    )
    direct_store = _TrackingDirectStore(monthly_reports_router._store)
    monkeypatch.setattr(monthly_reports_router, "_get_store", lambda: direct_store)
    headers = {
        "Authorization": f"Bearer {_supabase_token(sub='user-a', email='user-a@tomonokai-corp.com')}"
    }
    detail = client.get(f"/monthly-reports/jobs/{job.public_id}", headers=headers)
    token = _CSRF_RE.search(detail.text).group("token")
    read_store.calls.clear()

    summary = client.post(
        f"/monthly-reports/jobs/{job.public_id}/fragments/source-summary",
        data={"csrf_token": token, "idempotency_key": "html-rls-summary-key"},
        headers={**headers, "HX-Request": "true"},
    )

    assert summary.status_code == 200
    assert "source_summary_markdown" in summary.text
    assert "list_sources" in read_store.calls
    assert "record_artifact" in read_store.calls
    assert read_store.artifacts[-1].artifact_type == "source_summary_markdown"
    assert direct_store.recorded_llm_calls[-1]["prompt_kind"] == "source_summary"
    assert direct_store.recorded_llm_calls[-1]["requested_model"] == "mock/light-summary"


def test_monthly_report_ui_google_source_generate_openrouter_uses_service_owned_workflow_in_mock(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "mock")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-secret")
    monkeypatch.setenv("OPENROUTER_MODEL_REPORT", "mock/report-html")
    monkeypatch.setenv("OPENROUTER_MODEL_LIGHT", "mock/light-html")
    monkeypatch.setattr(
        monthly_reports_router,
        "_resolve_google_workspace_access_token",
        lambda current_user: "fake-access-token",
    )

    class FakeGoogleWorkspaceClient:
        def __init__(self, *, access_token):
            assert access_token == "fake-access-token"

        def fetch_doc(self, *, document_id: str, display_name: str | None = None):
            assert document_id == "https://docs.google.com/document/d/doc-id/edit"
            return GoogleWorkspaceSource(
                source_type="google_doc",
                display_name=display_name or "RLS面談メモ",
                snapshot_text="RLS Google Doc本文",
                content_hash="sha256:rls-gdoc-direct-workflow",
            )

    def fake_complete(self, *, messages, model=None):
        return LLMCompletion(
            content="\n\n".join(
                [
                    "# 4月度 月次レポート",
                    "## 01 基本情報\n本文",
                    "## 02 塾での様子\n本文",
                    "## 03 授業内容\n本文",
                    "## 04 課題とアドバイス\n本文",
                    "## 05 学習の進捗\n本文",
                    "## 07 今後の授業計画\nRLS generate openrouter本文",
                ]
            ),
            resolved_model="mock/report-html-resolved",
            input_tokens=21,
            output_tokens=13,
            finish_reason="stop",
        )

    monkeypatch.setattr(
        monthly_reports_router,
        "GoogleWorkspaceClient",
        FakeGoogleWorkspaceClient,
    )
    monkeypatch.setattr(OpenRouterMonthlyReportProvider, "complete", fake_complete)
    app = create_app()
    client = TestClient(app)
    job = monthly_reports_router._store.create_job(
        target_month="2026-04",
        household_key="html_mock_google_generate_household",
        owner_user_id="mock-user",
    )
    direct_store = _TrackingDirectStore(monthly_reports_router._store)
    monkeypatch.setattr(monthly_reports_router, "_get_store", lambda: direct_store)
    detail = client.get(f"/monthly-reports/jobs/{job.public_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    generated = client.post(
        f"/monthly-reports/jobs/{job.public_id}/fragments/google-sources",
        data={
            "csrf_token": token,
            "doc_ids": "https://docs.google.com/document/d/doc-id/edit",
            "after_fetch_action": "generate_openrouter",
        },
        headers={"HX-Request": "true"},
    )

    assert generated.status_code == 200
    assert direct_store.recorded_llm_calls[-1]["prompt_kind"] == "report"
    assert direct_store.recorded_llm_calls[-1]["requested_model"] == "mock/report-html"
    assert any(
        artifact.artifact_type == "draft_markdown"
        for artifact in direct_store._inner.list_artifacts(job.public_id)
    )
    assert any(
        validation.rule_id == "non_empty_markdown"
        for validation in direct_store._inner.list_validations(job.public_id)
    )
    audit_logs = direct_store._inner.list_audit_logs(job.public_id)
    assert audit_logs[-1].action == "monthly_report_service_owned_workflow_executed"
    assert audit_logs[-1].metadata["trigger"] == "html_google_sources"
    assert audit_logs[-1].metadata["mode"] == "openrouter"
    assert audit_logs[-1].metadata["boundary"] == "service_owned_workflow"


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
    assert "表示中:" in preview.text
    assert "生成ドラフト" in preview.text
    assert "4月度 月次レポート" in preview.text
    assert "sha256:html-preview" in preview.text
    assert "/api/monthly-reports" not in preview.text
    assert validation.status_code == 200
    assert "text/html" in validation.headers["content-type"]
    assert "non_empty_markdown" in validation.text
    assert "本文があります" in validation.text


def test_monthly_report_preview_prefers_final_markdown_over_later_draft():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "preview_final_priority_household",
            "owner_user_id": "html-preview-final-priority-owner",
        },
    )
    job_id = created.json()["job_id"]
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/artifacts",
        json={
            "artifact_type": "final_markdown",
            "content": "## final\n保存済み本文",
            "content_hash": "sha256:final-priority",
        },
    )
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/artifacts",
        json={
            "artifact_type": "draft_markdown",
            "content": "## draft\n古いドラフト表示になると困る",
            "content_hash": "sha256:later-draft",
        },
    )

    preview = client.get(f"/monthly-reports/jobs/{job_id}/fragments/preview")
    detail = client.get(f"/monthly-reports/jobs/{job_id}")

    assert preview.status_code == 200
    assert "final_markdown" in preview.text
    assert "編集保存済み" in preview.text
    assert "保存済み本文" in preview.text
    assert "古いドラフト表示になると困る" not in preview.text
    assert "保存済み" in detail.text
    assert "Markdownは中間成果物として保存します" in detail.text
    assert "保存済み本文" in detail.text


def test_monthly_report_ui_diff_fragment_compares_draft_and_final_markdown():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "diff_household",
            "owner_user_id": "html-diff-owner",
        },
    )
    job_id = created.json()["job_id"]
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/artifacts",
        json={
            "artifact_type": "draft_markdown",
            "content": "## 01 基本情報\nold line\nkeep",
            "content_hash": "sha256:draft-diff",
        },
    )
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/artifacts",
        json={
            "artifact_type": "final_markdown",
            "content": "## 01 基本情報\nnew line\nkeep",
            "content_hash": "sha256:final-diff",
        },
    )

    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    diff = client.get(f"/monthly-reports/jobs/{job_id}/fragments/diff")

    assert detail.status_code == 200
    assert f'hx-get="/monthly-reports/jobs/{job_id}/fragments/diff"' in detail.text
    assert "draft / final 差分" in detail.text
    assert diff.status_code == 200
    assert "text/html" in diff.headers["content-type"]
    assert "sha256:draft-diff" in diff.text
    assert "sha256:final-diff" in diff.text
    assert "old line" in diff.text
    assert "new line" in diff.text
    assert "+1" in diff.text
    assert "-1" in diff.text
    assert "/api/monthly-reports" not in diff.text


def test_monthly_report_ui_diff_fragment_handles_missing_final_markdown():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "diff_missing_final_household",
            "owner_user_id": "html-diff-missing-final-owner",
        },
    )
    job_id = created.json()["job_id"]
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/artifacts",
        json={
            "artifact_type": "draft_markdown",
            "content": "## 01 基本情報\n本文",
            "content_hash": "sha256:draft-only",
        },
    )

    diff = client.get(f"/monthly-reports/jobs/{job_id}/fragments/diff")

    assert diff.status_code == 200
    assert "final_markdown がまだありません" in diff.text


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
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/artifacts",
        json={
            "artifact_type": "draft_markdown",
            "content": "## 01 基本情報\nprefill本文",
            "content_hash": "sha256:detail-prefill",
        },
    )

    detail = client.get(f"/monthly-reports/jobs/{job_id}")

    assert detail.status_code == 200
    assert "text/html" in detail.headers["content-type"]
    assert "現在位置" in detail.text
    assert 'aria-label="レポート工房メニュー"' in detail.text
    assert "新規ジョブ登録" in detail.text
    assert "データソース登録" in detail.text
    assert "生成・再生成" in detail.text
    assert "プレビュー・編集" in detail.text
    assert "承認・出力" in detail.text
    assert "承認 -> HTMLエクスポート -> 送付用固定の順で進みます" in detail.text
    assert "送付前の進め方" in detail.text
    assert "1. 承認" in detail.text
    assert "2. HTMLエクスポート" in detail.text
    assert "3. 送付用固定" in detail.text
    assert "チューニングメモ" in detail.text
    assert "次の操作: ソース確認後、生成開始" in detail.text
    assert "最新プレビュー" in detail.text
    assert "sha256:detail-prefill" in detail.text
    assert "プレビュー / 編集" in detail.text
    assert "配布面プレビュー" in detail.text
    assert "配布面の確定と編集" in detail.text
    assert "生成Markdown（中間成果物）" in detail.text
    assert "未保存の変更" in detail.text
    assert "生成Markdownを保存" in detail.text
    assert "draft / final 差分" in detail.text
    assert "## 01 基本情報" in detail.text
    assert "prefill本文" in detail.text
    assert "データソース登録・確認" in detail.text
    assert "まず Google Docs の面談メモと Google Sheets の基本情報・学習計画表を取得します" in detail.text
    assert "通常はこちら: Googleから取得" in detail.text
    assert "例外対応: 手入力で保存" in detail.text
    assert "プレビュー/編集" in detail.text
    assert f'hx-post="/monthly-reports/jobs/{job_id}/fragments/edited-markdown"' in detail.text
    assert f'hx-post="/monthly-reports/jobs/{job_id}/rerun"' in detail.text
    assert f'hx-post="/monthly-reports/jobs/{job_id}/cancel"' in detail.text
    assert 'name="edited_markdown"' in detail.text
    assert 'name="base_content_hash"' in detail.text
    assert "Markdownは中間成果物として保存します" in detail.text
    assert "再生成" in detail.text
    assert f'hx-get="/monthly-reports/jobs/{job_id}/fragments/approval"' in detail.text
    assert f'hx-get="/monthly-reports/jobs/{job_id}/fragments/export"' in detail.text
    assert f'hx-get="/monthly-reports/jobs/{job_id}/fragments/html-source"' in detail.text
    assert "student と lesson plan を全範囲取得" in detail.text
    assert "Googleからソース取得" in detail.text
    assert "手入力ソースを保存" in detail.text
    assert "範囲指定は不要です" in detail.text
    assert "シート名を確認" in detail.text
    assert "Google Sheets ID / URLを入力してください" in detail.text
    assert "取得内容を要約" in detail.text
    assert "/api/monthly-reports" not in detail.text


def test_monthly_report_detail_disables_invalid_actions_for_succeeded_job():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)
    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "succeeded_detail_household",
            "owner_user_id": "html-succeeded-detail-owner",
        },
    )
    job_id = created.json()["job_id"]
    monthly_reports_router._store.start_next(job_id)
    for _ in monthly_reports_router.PIPELINE_STAGES:
        monthly_reports_router._store.complete_current_stage(job_id)

    detail = client.get(f"/monthly-reports/jobs/{job_id}")

    assert detail.status_code == 200
    assert "queued のジョブだけ生成開始できます" in detail.text
    assert "queued / running のジョブだけキャンセルできます" in detail.text
    assert "生成開始</button>" in detail.text
    assert 'name="snapshot_text" rows="4" required' in detail.text
    assert 'name="edited_markdown"' in detail.text
    assert 'rows="18"' in detail.text
    assert 'name="comment" rows="3" required' in detail.text


def test_monthly_report_ui_cancel_action_returns_status_fragment():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "cancel_household",
            "owner_user_id": "html-cancel-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")
    cancel_key = re.search(
        r'hx-post="/monthly-reports/jobs/[^"]+/cancel".*?name="idempotency_key" value="(?P<key>[^"]+)"',
        detail.text,
        re.S,
    ).group("key")

    cancelled = client.post(
        f"/monthly-reports/jobs/{job_id}/cancel",
        data={"csrf_token": token, "idempotency_key": cancel_key},
        headers={"HX-Request": "true"},
    )
    repeated = client.post(
        f"/monthly-reports/jobs/{job_id}/cancel",
        data={"csrf_token": token, "idempotency_key": cancel_key},
        headers={"HX-Request": "true"},
    )

    assert cancelled.status_code == 200
    assert "text/html" in cancelled.headers["content-type"]
    assert "cancelled" in cancelled.text
    assert "status:" in cancelled.text
    assert repeated.status_code == 200
    assert "cancelled" in repeated.text
    assert "/api/monthly-reports" not in cancelled.text


def test_monthly_report_ui_cancel_action_blocks_completed_job():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "cancel_completed_household",
            "owner_user_id": "html-cancel-completed-owner",
        },
    )
    job_id = created.json()["job_id"]
    monthly_reports_router._store.start_next(job_id)
    for _ in monthly_reports_router.PIPELINE_STAGES:
        monthly_reports_router._store.complete_current_stage(job_id)
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")
    cancel_key = re.search(
        r'hx-post="/monthly-reports/jobs/[^"]+/cancel".*?name="idempotency_key" value="(?P<key>[^"]+)"',
        detail.text,
        re.S,
    ).group("key")

    cancelled = client.post(
        f"/monthly-reports/jobs/{job_id}/cancel",
        data={"csrf_token": token, "idempotency_key": cancel_key},
        headers={"HX-Request": "true"},
    )

    assert cancelled.status_code == 409
    assert "queued / running のジョブだけキャンセルできます" in cancelled.text


def test_monthly_report_ui_source_summary_uses_light_model_and_saves_artifact(
    monkeypatch: pytest.MonkeyPatch,
):
    os.environ["EB_AUTH_MODE"] = "mock"
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-secret")
    monkeypatch.setenv("OPENROUTER_MODEL_LIGHT", "mock/light-summary")
    calls: list[dict[str, object]] = []

    def fake_complete(self, *, messages, model=None):
        calls.append({"messages": messages, "model": model})
        assert model == "mock/light-summary"
        user_content = messages[-1]["content"]
        assert "教師MTG" in user_content
        assert "student sheet" in user_content
        return LLMCompletion(
            content=(
                "## 取得内容サマリー\n"
                "- 文字起こしと学習計画表を確認しました。\n"
                "## 対象・期間・科目の確認\n"
                "- 対象は平林様 Physics です。\n"
                "## ズレ/不足の可能性\n"
                "- lesson planの月次範囲確認が必要です。"
            ),
            resolved_model="mock/light-summary-resolved",
            input_tokens=120,
            output_tokens=80,
            finish_reason="stop",
        )

    monkeypatch.setattr(OpenRouterMonthlyReportProvider, "complete", fake_complete)
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "source_summary_household",
            "owner_user_id": "html-source-summary-owner",
        },
    )
    job_id = created.json()["job_id"]
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/sources",
        json={
            "source_type": "google_doc",
            "display_name": "教師MTG",
            "snapshot_text": "平林様のPhysics文字起こし",
        },
    )
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/sources",
        json={
            "source_type": "google_sheet",
            "display_name": "student sheet",
            "snapshot_text": '{"range":"student","values":[["name","平林様"]]}',
        },
    )
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    summary = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/source-summary",
        data={"csrf_token": token, "idempotency_key": "summary-key"},
        headers={"HX-Request": "true"},
    )
    duplicate = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/source-summary",
        data={"csrf_token": token, "idempotency_key": "summary-key"},
        headers={"HX-Request": "true"},
    )
    artifacts = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts").json()[
        "artifacts"
    ]
    llm_calls = client.get(f"/api/monthly-reports/jobs/{job_id}/llm-calls").json()[
        "llm_calls"
    ]

    assert summary.status_code == 200
    assert duplicate.status_code == 200
    assert "source_summary_markdown" in summary.text
    assert duplicate.text == summary.text
    assert "lesson planの月次範囲確認" in summary.text
    assert artifacts[-1]["artifact_type"] == "source_summary_markdown"
    assert llm_calls[-1]["prompt_kind"] == "source_summary"
    assert llm_calls[-1]["requested_model"] == "mock/light-summary"
    assert len(calls) == 1
    assert len(artifacts) == 1
    assert len(llm_calls) == 1


def test_monthly_report_ui_source_summary_rejects_empty_sources(
    monkeypatch: pytest.MonkeyPatch,
):
    os.environ["EB_AUTH_MODE"] = "mock"
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "empty_summary_household",
            "owner_user_id": "html-empty-summary-owner",
        },
    )
    job_id = created.json()["job_id"]
    monthly_reports_router._store.record_source(
        job_id,
        source_type="doc",
        display_name="空の面談メモ",
        snapshot_text="   ",
    )
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    summary = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/source-summary",
        data={"csrf_token": token, "idempotency_key": "empty-summary-key"},
        headers={"HX-Request": "true"},
    )

    assert summary.status_code == 422
    assert "source is required before summary" in summary.text


def test_monthly_report_ui_source_summary_requires_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
):
    os.environ["EB_AUTH_MODE"] = "mock"
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "summary_missing_key_household",
            "owner_user_id": "html-summary-missing-key-owner",
        },
    )
    job_id = created.json()["job_id"]
    monthly_reports_router._store.record_source(
        job_id,
        source_type="doc",
        display_name="面談メモ",
        snapshot_text="Physicsの面談メモ",
    )
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    summary = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/source-summary",
        data={"csrf_token": token},
        headers={"HX-Request": "true"},
    )

    assert summary.status_code == 422
    assert "idempotency_key is required" in summary.text


def test_monthly_report_ui_approval_and_export_fragments_return_blocked_html():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "approval_export_household",
            "owner_user_id": "html-approval-export-owner",
        },
    )
    job_id = created.json()["job_id"]
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/artifacts",
        json={
            "artifact_type": "draft_markdown",
            "content": "## 01 基本情報\n本文",
            "content_hash": "sha256:approval-export-draft",
        },
    )

    approval = client.get(f"/monthly-reports/jobs/{job_id}/fragments/approval")
    export = client.get(f"/monthly-reports/jobs/{job_id}/fragments/export")

    assert approval.status_code == 200
    assert "text/html" in approval.headers["content-type"]
    assert "承認はまだ実行できません" in approval.text
    assert "生成が完了していません" in approval.text
    assert "承認状態" in approval.text
    assert "次の操作" in approval.text
    assert "不足を解消" in approval.text
    assert "保存後の流れ: まず現在の配布面を承認し、そのあと下のHTMLエクスポートへ進みます。" in approval.text
    assert "sha256:approval-export-draft" in approval.text
    assert "/api/monthly-reports" not in approval.text
    assert export.status_code == 200
    assert "text/html" in export.headers["content-type"]
    assert "HTMLエクスポートはまだ作成できません" in export.text
    assert "人間承認がまだありません" in export.text
    assert "承認状態" in export.text
    assert "HTML export" in export.text
    assert "ここで配布用HTMLを確定します" in export.text
    assert "/api/monthly-reports" not in export.text


def test_monthly_report_ui_approval_and_export_actions_create_artifacts():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "approval_export_action_household",
            "owner_user_id": "html-approval-export-action-owner",
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
    assert completed.status_code == 200

    artifacts = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts").json()[
        "artifacts"
    ]
    artifact_hash = artifacts[-1]["content_hash"]
    approval_fragment = client.get(f"/monthly-reports/jobs/{job_id}/fragments/approval")
    approval_key = re.search(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        approval_fragment.text,
    ).group("key")

    approval = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/approval",
        data={
            "csrf_token": token,
            "idempotency_key": approval_key,
            "artifact_hash": artifact_hash,
            "confirm_ready": "yes",
            "approval_comment": "送付前確認済み",
        },
        headers={"HX-Request": "true"},
    )
    export_fragment = client.get(f"/monthly-reports/jobs/{job_id}/fragments/export")
    export_key = re.search(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        export_fragment.text,
    ).group("key")
    export = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/export",
        data={
            "csrf_token": token,
            "idempotency_key": export_key,
            "artifact_hash": artifact_hash,
        },
        headers={"HX-Request": "true"},
    )
    stored = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts").json()[
        "artifacts"
    ]
    audit_logs = monthly_reports_router._store.list_audit_logs(job_id)

    assert approval.status_code == 200
    assert "text/html" in approval.headers["content-type"]
    assert "送付前承認を保存しました" in approval.text
    assert "次は `HTMLエクスポート` パネルで export を作成し、その後 `送付用固定` へ進めます。" in approval.text
    assert artifact_hash in approval.text
    assert export.status_code == 200
    assert "text/html" in export.headers["content-type"]
    assert "export_html" in export.text
    assert "HTMLエクスポートを再作成" in export.text
    assert "作成後はそのまま送付用固定へ進めます" in export.text
    assert stored[-2]["artifact_type"] == "approval"
    assert stored[-1]["artifact_type"] == "export_html"
    assert "<article" in stored[-1]["content"]
    assert [entry.action for entry in audit_logs] == [
        "monthly_report_service_owned_workflow_executed",
        "monthly_report_approval_saved",
        "monthly_report_export_html_saved",
    ]
    assert audit_logs[1].actor_id.endswith("@tomonokai-corp.com")
    assert audit_logs[1].metadata["approved_artifact_hash"] == artifact_hash
    assert audit_logs[1].metadata["comment_present"] is True
    assert audit_logs[2].metadata["source_artifact_hash"] == artifact_hash
    assert "/api/monthly-reports" not in approval.text
    assert "/api/monthly-reports" not in export.text


def test_monthly_report_ui_export_action_blocks_without_current_approval():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "export_without_approval_household",
            "owner_user_id": "html-export-without-approval-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")
    client.post(
        f"/monthly-reports/jobs/{job_id}/run",
        data={"csrf_token": token, "run_mode": "mock"},
        headers={"HX-Request": "true"},
    )
    artifacts = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts").json()[
        "artifacts"
    ]
    export_fragment = client.get(f"/monthly-reports/jobs/{job_id}/fragments/export")
    export_key = re.search(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        export_fragment.text,
    ).group("key")

    export = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/export",
        data={
            "csrf_token": token,
            "idempotency_key": export_key,
            "artifact_hash": artifacts[-1]["content_hash"],
        },
        headers={"HX-Request": "true"},
    )

    assert export.status_code == 422
    assert "HTMLエクスポートはまだ作成できません" in export.text
    assert "人間承認がまだありません" in export.text


def test_monthly_report_ui_html_source_fragment_blocks_without_export():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "html_source_blocked_household",
            "owner_user_id": "html-source-blocked-owner",
        },
    )
    job_id = created.json()["job_id"]

    fragment = client.get(f"/monthly-reports/jobs/{job_id}/fragments/html-source")

    assert fragment.status_code == 200
    assert "text/html" in fragment.headers["content-type"]
    assert "HTMLソース編集はまだ実行できません" in fragment.text
    assert "HTML export artifactがまだありません" in fragment.text
    assert 'name="html_source"' in fragment.text
    assert "disabled" in fragment.text
    assert "/api/monthly-reports" not in fragment.text


def test_monthly_report_ui_html_source_action_saves_new_export_artifact():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)
    job_id, token, export_hash = _create_exported_monthly_report_job(client)
    fragment = client.get(f"/monthly-reports/jobs/{job_id}/fragments/html-source")
    edit_key = re.search(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        fragment.text,
    ).group("key")
    edited_html = '<article class="monthly-report-export"><h1>編集済みHTML</h1></article>'

    saved = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/html-source",
        data={
            "csrf_token": token,
            "idempotency_key": edit_key,
            "base_export_hash": export_hash,
            "html_source": edited_html,
        },
        headers={"HX-Request": "true"},
    )
    stored = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts").json()[
        "artifacts"
    ]
    audit_logs = monthly_reports_router._store.list_audit_logs(job_id)

    assert saved.status_code == 200
    assert "text/html" in saved.headers["content-type"]
    assert "HTMLソースを保存しました" in saved.text
    assert "編集済みHTML" in saved.text
    assert "HTMLプレビュー" in saved.text
    assert 'title="HTML export preview"' in saved.text
    assert "iframe" in saved.text
    assert stored[-1]["artifact_type"] == "export_html"
    assert stored[-1]["content"] == edited_html
    assert stored[-1]["content_hash"] != export_hash
    assert audit_logs[-1].action == "monthly_report_export_html_edited"
    assert audit_logs[-1].metadata["base_export_hash"] == export_hash
    assert audit_logs[-1].metadata["html_length"] == len(edited_html)
    assert "/api/monthly-reports" not in saved.text


def test_monthly_report_ui_html_source_action_rejects_stale_export_hash():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)
    job_id, token, _export_hash = _create_exported_monthly_report_job(client)
    fragment = client.get(f"/monthly-reports/jobs/{job_id}/fragments/html-source")
    edit_key = re.search(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        fragment.text,
    ).group("key")

    saved = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/html-source",
        data={
            "csrf_token": token,
            "idempotency_key": edit_key,
            "base_export_hash": "sha256:stale",
            "html_source": "<article>stale</article>",
        },
        headers={"HX-Request": "true"},
    )

    assert saved.status_code == 409
    assert "latest export artifact hash does not match" in saved.text


def test_monthly_report_ui_html_source_action_is_idempotent():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)
    job_id, token, export_hash = _create_exported_monthly_report_job(client)
    fragment = client.get(f"/monthly-reports/jobs/{job_id}/fragments/html-source")
    edit_key = re.search(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        fragment.text,
    ).group("key")
    before = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts").json()[
        "artifacts"
    ]
    before_export_count = sum(
        artifact["artifact_type"] == "export_html" for artifact in before
    )
    payload = {
        "csrf_token": token,
        "idempotency_key": edit_key,
        "base_export_hash": export_hash,
        "html_source": "<article><p>one save</p></article>",
    }

    first = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/html-source",
        data=payload,
        headers={"HX-Request": "true"},
    )
    second = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/html-source",
        data=payload,
        headers={"HX-Request": "true"},
    )
    after = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts").json()[
        "artifacts"
    ]
    after_export_count = sum(
        artifact["artifact_type"] == "export_html" for artifact in after
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert "HTMLソースを保存しました" in second.text
    assert after_export_count == before_export_count + 1


def test_monthly_report_ui_export_html_download_returns_attachment():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)
    job_id, _token, _export_hash = _create_exported_monthly_report_job(client)

    response = client.get(f"/monthly-reports/jobs/{job_id}/download/export-html")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "attachment;" in response.headers["content-disposition"]
    assert f"{job_id}.html" in response.headers["content-disposition"]
    assert "monthly-report-export" in response.text


def test_monthly_report_ui_serves_legacy_full_editor_connection():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    editor = client.get("/monthly-reports/legacy-full-editor")

    assert editor.status_code == 200
    assert "text/html" in editor.headers["content-type"]
    assert "ea_monthly_report_full_editor_draft_html" in editor.text
    assert "previewTab" in editor.text
    assert "/api/monthly-reports" not in editor.text

    job_id, _token, _export_hash = _create_exported_monthly_report_job(client)
    html_source = client.get(f"/monthly-reports/jobs/{job_id}/fragments/html-source")

    assert html_source.status_code == 200
    assert "/monthly-reports/legacy-full-editor" in html_source.text
    assert "既存全文エディタ" in html_source.text


def test_monthly_report_ui_legacy_full_editor_bridge_loads_latest_export_artifact():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)
    job_id, _token, _export_hash = _create_exported_monthly_report_job(client)

    bridge = client.get(f"/monthly-reports/jobs/{job_id}/legacy-full-editor")

    assert bridge.status_code == 200
    assert "text/html" in bridge.headers["content-type"]
    assert "ea_monthly_report_full_editor_draft_html_v4" in bridge.text
    assert "TextDecoder" in bridge.text
    assert "location.replace('/monthly-reports/legacy-full-editor')" in bridge.text
    assert "/api/monthly-reports" not in bridge.text


def test_monthly_report_ui_distribution_fragment_blocks_without_export():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)
    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "distribution_blocked_household",
            "owner_user_id": "html-distribution-blocked-owner",
        },
    )
    job_id = created.json()["job_id"]

    fragment = client.get(f"/monthly-reports/jobs/{job_id}/fragments/distribution")

    assert fragment.status_code == 200
    assert "送付エクスポートはまだ準備できません" in fragment.text
    assert "HTML export artifactがまだありません" in fragment.text
    assert "送付用固定" in fragment.text
    assert "次の操作" in fragment.text
    assert "送付用に固定" in fragment.text
    assert "最後に、実際に配布する版をここで固定します" in fragment.text
    assert "disabled" in fragment.text
    assert "/api/monthly-reports" not in fragment.text


def test_monthly_report_ui_distribution_action_creates_package_idempotently():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)
    job_id, token, export_hash = _create_exported_monthly_report_job(client)
    fragment = client.get(f"/monthly-reports/jobs/{job_id}/fragments/distribution")
    distribution_key = re.search(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        fragment.text,
    ).group("key")
    before = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts").json()[
        "artifacts"
    ]
    before_count = sum(
        artifact["artifact_type"] == "distribution_package" for artifact in before
    )

    first = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/distribution",
        data={
            "csrf_token": token,
            "idempotency_key": distribution_key,
            "export_hash": export_hash,
        },
        headers={"HX-Request": "true"},
    )
    second = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/distribution",
        data={
            "csrf_token": token,
            "idempotency_key": distribution_key,
            "export_hash": export_hash,
        },
        headers={"HX-Request": "true"},
    )
    after = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts").json()[
        "artifacts"
    ]
    after_count = sum(
        artifact["artifact_type"] == "distribution_package" for artifact in after
    )
    audit_logs = monthly_reports_router._store.list_audit_logs(job_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert "ready_for_manual_distribution" in second.text
    assert "送付用固定を更新" in second.text
    assert "固定後は保存したHTMLをそのまま配布対象として扱います" in second.text
    assert after_count == before_count + 1
    assert after[-1]["artifact_type"] == "distribution_package"
    assert export_hash in after[-1]["content"]
    assert audit_logs[-1].action == "monthly_report_distribution_package_saved"
    assert audit_logs[-1].metadata["export_artifact_hash"] == export_hash


def test_monthly_report_ui_distribution_action_rejects_stale_export_hash():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)
    job_id, token, _export_hash = _create_exported_monthly_report_job(client)
    fragment = client.get(f"/monthly-reports/jobs/{job_id}/fragments/distribution")
    distribution_key = re.search(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        fragment.text,
    ).group("key")

    response = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/distribution",
        data={
            "csrf_token": token,
            "idempotency_key": distribution_key,
            "export_hash": "sha256:stale",
        },
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 409
    assert "latest export artifact hash does not match" in response.text


def test_monthly_report_ui_approval_rejects_stale_artifact_hash():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "approval_stale_hash_household",
            "owner_user_id": "html-approval-stale-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")
    client.post(
        f"/monthly-reports/jobs/{job_id}/run",
        data={"csrf_token": token, "run_mode": "mock"},
        headers={"HX-Request": "true"},
    )
    approval_fragment = client.get(f"/monthly-reports/jobs/{job_id}/fragments/approval")
    approval_key = re.search(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        approval_fragment.text,
    ).group("key")

    approval = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/approval",
        data={
            "csrf_token": token,
            "idempotency_key": approval_key,
            "artifact_hash": "sha256:stale",
            "confirm_ready": "yes",
        },
        headers={"HX-Request": "true"},
    )

    assert approval.status_code == 409
    assert "latest distribution artifact hash does not match" in approval.text


def test_monthly_report_ui_approval_requires_idempotency_key_and_clean_validation():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "approval_validation_error_household",
            "owner_user_id": "html-approval-validation-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")
    client.post(
        f"/monthly-reports/jobs/{job_id}/run",
        data={"csrf_token": token, "run_mode": "mock"},
        headers={"HX-Request": "true"},
    )
    artifacts = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts").json()[
        "artifacts"
    ]
    missing_key = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/approval",
        data={
            "csrf_token": token,
            "artifact_hash": artifacts[-1]["content_hash"],
            "confirm_ready": "yes",
        },
        headers={"HX-Request": "true"},
    )
    client.post(
        f"/api/monthly-reports/jobs/{job_id}/validations",
        json={
            "rule_id": "distribution_blocker",
            "severity": "error",
            "message": "送付前に修正が必要です",
        },
    )

    blocked = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/approval",
        data={
            "csrf_token": token,
            "idempotency_key": "approval-validation-error-key",
            "artifact_hash": artifacts[-1]["content_hash"],
            "confirm_ready": "yes",
        },
        headers={"HX-Request": "true"},
    )

    assert missing_key.status_code == 422
    assert "idempotency_key is required" in missing_key.text
    assert blocked.status_code == 422
    assert "承認はまだ実行できません" in blocked.text
    assert "validation errorが残っています" in blocked.text


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


def test_monthly_report_ui_rejects_stale_edited_markdown_base_hash():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "edit_conflict_household",
            "owner_user_id": "html-edit-conflict-owner",
        },
    )
    job_id = created.json()["job_id"]
    initial = client.post(
        f"/api/monthly-reports/jobs/{job_id}/artifacts",
        json={
            "artifact_type": "draft_markdown",
            "content": "## 初期ドラフト",
            "content_hash": "sha256:initial-draft",
        },
    )
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")
    assert initial.status_code == 200
    assert 'name="base_content_hash" value="sha256:initial-draft"' in detail.text

    concurrent = client.post(
        f"/api/monthly-reports/jobs/{job_id}/artifacts",
        json={
            "artifact_type": "final_markdown",
            "content": "## 別タブで保存済み",
            "content_hash": "sha256:concurrent-final",
        },
    )
    stale_save = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/edited-markdown",
        data={
            "csrf_token": token,
            "idempotency_key": "edit-conflict-key",
            "base_content_hash": "sha256:initial-draft",
            "edited_markdown": "## 古いタブからの保存",
        },
        headers={"HX-Request": "true"},
    )

    artifacts = client.get(f"/api/monthly-reports/jobs/{job_id}/artifacts").json()[
        "artifacts"
    ]

    assert concurrent.status_code == 200
    assert stale_save.status_code == 409
    assert "base content hash does not match" in stale_save.text
    assert artifacts[-1]["content"] == "## 別タブで保存済み"


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
        data={"csrf_token": token, "idempotency_key": "rerun-status-fragment-key"},
        headers={"HX-Request": "true"},
    )

    assert rerun.status_code == 200
    assert "text/html" in rerun.headers["content-type"]
    assert "status:" in rerun.text
    assert "queued" in rerun.text
    assert "再生成ジョブを作成しました" in rerun.text
    assert "/monthly-reports/jobs/" in rerun.text


def test_monthly_report_ui_rerun_allows_admin_tuning_overrides_only(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EB_AUTH_MODE", "mock")
    monkeypatch.setenv("EB_MOCK_USER_EMAIL", "mock-admin@tomonokai-corp.com")
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "html_rerun_tuning_household",
            "owner_user_id": "html-rerun-tuning-owner",
            "template_key": "pattern_b",
            "prompt_version": "monthly-report-v20260517.source",
            "model_report": "openrouter/source-report-model",
            "model_light": "openrouter/source-light-model",
        },
    )
    job_id = created.json()["job_id"]
    client.post(f"/api/monthly-reports/jobs/{job_id}/cancel")
    admin_detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(admin_detail.text).group("token")

    assert "再生成チューニング" in admin_detail.text
    assert 'name="rerun_prompt_version"' in admin_detail.text
    assert 'name="rerun_model_report"' in admin_detail.text
    assert 'name="rerun_model_light"' in admin_detail.text

    admin_rerun = client.post(
        f"/monthly-reports/jobs/{job_id}/rerun",
        data={
            "csrf_token": token,
            "idempotency_key": "admin-rerun-tuning-key",
            "rerun_prompt_version": "monthly-report-v20260517.rerun",
            "rerun_model_report": "openrouter/rerun-report-model",
            "rerun_model_light": "openrouter/rerun-light-model",
        },
        headers={"HX-Request": "true"},
    )
    admin_rerun_job = monthly_reports_router._store.list_jobs()[-1]
    admin_rerun_detail = client.get(
        f"/api/monthly-reports/jobs/{admin_rerun_job.public_id}"
    ).json()

    assert admin_rerun.status_code == 200
    assert admin_rerun_detail["prompt_version"] == "monthly-report-v20260517.rerun"
    assert admin_rerun_detail["model_report"] == "openrouter/rerun-report-model"
    assert admin_rerun_detail["model_light"] == "openrouter/rerun-light-model"

    monkeypatch.setenv("EB_MOCK_USER_EMAIL", "mock-user@tomonokai-corp.com")
    user_detail = client.get(f"/monthly-reports/jobs/{job_id}")
    user_token = _CSRF_RE.search(user_detail.text).group("token")

    assert "再生成チューニング" not in user_detail.text
    assert 'name="rerun_prompt_version"' not in user_detail.text
    assert 'name="rerun_model_report"' not in user_detail.text
    assert 'name="rerun_model_light"' not in user_detail.text

    user_rerun = client.post(
        f"/monthly-reports/jobs/{job_id}/rerun",
        data={
            "csrf_token": user_token,
            "idempotency_key": "user-rerun-tuning-key",
            "rerun_prompt_version": "monthly-report-v20260517.forbidden",
            "rerun_model_report": "openrouter/forbidden-report-model",
            "rerun_model_light": "openrouter/forbidden-light-model",
        },
        headers={"HX-Request": "true"},
    )
    user_rerun_job = monthly_reports_router._store.list_jobs()[-1]
    user_rerun_detail = client.get(
        f"/api/monthly-reports/jobs/{user_rerun_job.public_id}"
    ).json()

    assert user_rerun.status_code == 200
    assert user_rerun_detail["prompt_version"] == "monthly-report-v20260517.source"
    assert user_rerun_detail["model_report"] == "openrouter/source-report-model"
    assert user_rerun_detail["model_light"] == "openrouter/source-light-model"


def test_monthly_report_ui_rerun_action_is_idempotent_with_hidden_key():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "html_rerun_idempotent_household",
            "owner_user_id": "html-rerun-idempotent-owner",
        },
    )
    job_id = created.json()["job_id"]
    client.post(f"/api/monthly-reports/jobs/{job_id}/cancel")
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")
    rerun_key = re.findall(
        r'name="idempotency_key" value="(?P<key>[^"]+)"',
        detail.text,
    )[1]

    first = client.post(
        f"/monthly-reports/jobs/{job_id}/rerun",
        data={"csrf_token": token, "idempotency_key": rerun_key},
        headers={"HX-Request": "true"},
    )
    second = client.post(
        f"/monthly-reports/jobs/{job_id}/rerun",
        data={"csrf_token": token, "idempotency_key": rerun_key},
        headers={"HX-Request": "true"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    jobs = [
        job
        for job in monthly_reports_router._store.list_jobs()
        if job.owner_user_id == "html-rerun-idempotent-owner"
    ]
    assert len(jobs) == 2


def test_monthly_report_ui_rerun_form_targets_stable_panel():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "html_rerun_target_household",
            "owner_user_id": "html-rerun-target-owner",
        },
    ).json()
    client.post(f"/api/monthly-reports/jobs/{created['job_id']}/cancel")

    detail = client.get(f"/monthly-reports/jobs/{created['job_id']}")

    assert detail.status_code == 200
    assert 'hx-target="#rerun-created-panel"' in detail.text
    assert 'id="rerun-created-panel"' in detail.text
    assert 'id="status-panel"' in detail.text


def test_monthly_report_ui_rerun_action_rejects_active_source_jobs():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    queued = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "html_rerun_reject_queued",
            "owner_user_id": "html-rerun-reject-owner",
        },
    ).json()
    queued_detail = client.get(f"/monthly-reports/jobs/{queued['job_id']}")
    queued_token = _CSRF_RE.search(queued_detail.text).group("token")

    queued_rerun = client.post(
        f"/monthly-reports/jobs/{queued['job_id']}/rerun",
        data={"csrf_token": queued_token, "idempotency_key": "reject-queued-rerun"},
        headers={"HX-Request": "true"},
    )

    assert queued_rerun.status_code == 409
    assert "実行中/待機中のジョブは再生成できません" in queued_rerun.text

    running = monthly_reports_router._store.claim_next_runnable_job(
        owner_user_id="html-rerun-reject-owner"
    )
    assert running is not None
    running_detail = client.get(f"/monthly-reports/jobs/{running.public_id}")
    running_token = _CSRF_RE.search(running_detail.text).group("token")
    running_rerun = client.post(
        f"/monthly-reports/jobs/{running.public_id}/rerun",
        data={"csrf_token": running_token, "idempotency_key": "reject-running-rerun"},
        headers={"HX-Request": "true"},
    )

    assert running_rerun.status_code == 409
    assert len(monthly_reports_router._store.list_jobs()) == 1


def test_monthly_report_ui_rerun_action_idempotency_is_locked_for_concurrent_posts():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "html_rerun_concurrent_household",
            "owner_user_id": "html-rerun-concurrent-owner",
        },
    ).json()
    client.post(f"/api/monthly-reports/jobs/{created['job_id']}/cancel")
    detail = client.get(f"/monthly-reports/jobs/{created['job_id']}")
    token = _CSRF_RE.search(detail.text).group("token")

    def post_rerun() -> int:
        response = client.post(
            f"/monthly-reports/jobs/{created['job_id']}/rerun",
            data={"csrf_token": token, "idempotency_key": "concurrent-rerun-key"},
            headers={"HX-Request": "true"},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _: post_rerun(), range(2)))

    assert statuses == [200, 200]
    jobs = [
        job
        for job in monthly_reports_router._store.list_jobs()
        if job.owner_user_id == "html-rerun-concurrent-owner"
    ]
    assert len(jobs) == 2


def test_monthly_report_ui_rerun_comparison_fragment_compares_reproducibility_meta():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    original = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "html_rerun_compare_household",
            "owner_user_id": "html-rerun-compare-owner",
            "template_key": "pattern_b",
            "prompt_version": "monthly-report-v20260517.base",
            "model_report": "openrouter/base-report-model",
            "model_light": "openrouter/base-light-model",
            "resolved_model_report": "resolved/base-report-model",
        },
    ).json()
    source_job = monthly_reports_router._store.get(original["job_id"])
    rerun = monthly_reports_router._store.create_job(
        target_month=source_job.target_month,
        household_key=source_job.household_key,
        owner_user_id=source_job.owner_user_id,
        template_key=source_job.template_key,
        prompt_version="monthly-report-v20260517.compare",
        template_hash="sha256:template-compare",
        model_report="openrouter/compare-report-model",
        model_light="openrouter/compare-light-model",
        resolved_model_report="resolved/compare-report-model",
        source_bundle_hash="sha256:bundle-compare",
        app_version="compare-app",
        prompt_scope_notes=source_job.prompt_scope_notes,
    )

    fragment = client.get(
        f"/monthly-reports/jobs/{original['job_id']}/fragments/rerun-comparison"
        f"?compare_job_id={rerun.public_id}"
    )

    assert fragment.status_code == 200
    assert "再生成メタ比較" in fragment.text
    assert "比較候補" in fragment.text
    assert f'value="{rerun.public_id}"' in fragment.text
    assert "prompt_version" in fragment.text
    assert "monthly-report-v20260517.base" in fragment.text
    assert "monthly-report-v20260517.compare" in fragment.text
    assert "openrouter/base-report-model" in fragment.text
    assert "openrouter/compare-report-model" in fragment.text
    assert "changed" in fragment.text
    assert "/api/monthly-reports" not in fragment.text


def test_monthly_report_ui_rerun_comparison_rejects_different_household():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    base = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "html_rerun_compare_base",
            "owner_user_id": "html-rerun-compare-owner",
        },
    ).json()
    other = monthly_reports_router._store.create_job(
        target_month="2026-04",
        household_key="html_rerun_compare_other",
        owner_user_id="html-rerun-compare-owner",
    )

    comparison = client.get(
        f"/monthly-reports/jobs/{base['job_id']}/fragments/rerun-comparison"
        f"?compare_job_id={other.public_id}"
    )
    diff = client.get(
        f"/monthly-reports/jobs/{base['job_id']}/fragments/rerun-diff"
        f"?compare_job_id={other.public_id}"
    )

    assert comparison.status_code == 422
    assert diff.status_code == 422
    assert "同一ユーザー・同一世帯" in comparison.text
    assert "同一ユーザー・同一世帯" in diff.text


def test_monthly_report_ui_rerun_diff_fragment_compares_latest_markdown():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    original = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "html_rerun_diff_household",
            "owner_user_id": "html-rerun-diff-owner",
        },
    ).json()
    source_job = monthly_reports_router._store.get(original["job_id"])
    compare_job = monthly_reports_router._store.create_job(
        target_month=source_job.target_month,
        household_key=source_job.household_key,
        owner_user_id=source_job.owner_user_id,
    )
    monthly_reports_router._store.record_artifact(
        source_job.public_id,
        artifact_type="final_markdown",
        content="## 01 基本情報\nbase line\nsame line",
        content_hash="sha256:base-rerun-diff",
    )
    monthly_reports_router._store.record_artifact(
        compare_job.public_id,
        artifact_type="draft_markdown",
        content="## 01 基本情報\ncompare line\nsame line",
        content_hash="sha256:compare-rerun-diff",
    )

    detail = client.get(f"/monthly-reports/jobs/{source_job.public_id}")
    fragment = client.get(
        f"/monthly-reports/jobs/{source_job.public_id}/fragments/rerun-diff"
        f"?compare_job_id={compare_job.public_id}"
    )

    assert detail.status_code == 200
    assert f'hx-get="/monthly-reports/jobs/{source_job.public_id}/fragments/rerun-diff"' in detail.text
    assert fragment.status_code == 200
    assert "再生成本文差分" in fragment.text
    assert compare_job.public_id in fragment.text
    assert "sha256:base-rerun-diff" in fragment.text
    assert "sha256:compare-rerun-diff" in fragment.text
    assert "base line" in fragment.text
    assert "compare line" in fragment.text
    assert "+1" in fragment.text
    assert "-1" in fragment.text
    assert "/api/monthly-reports" not in fragment.text


def test_monthly_report_ui_rerun_diff_ignores_html_artifacts():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    original = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "html_rerun_diff_html_household",
            "owner_user_id": "html-rerun-diff-html-owner",
        },
    ).json()
    base_job = monthly_reports_router._store.get(original["job_id"])
    compare_job = monthly_reports_router._store.create_job(
        target_month=base_job.target_month,
        household_key=base_job.household_key,
        owner_user_id=base_job.owner_user_id,
    )
    monthly_reports_router._store.record_artifact(
        base_job.public_id,
        artifact_type="html",
        content="<h1>HTML ONLY SHOULD NOT BE DIFFED</h1>",
        content_hash="sha256:base-html-only",
    )
    monthly_reports_router._store.record_artifact(
        compare_job.public_id,
        artifact_type="draft_markdown",
        content="## 01 基本情報\ncompare markdown",
        content_hash="sha256:compare-markdown",
    )

    fragment = client.get(
        f"/monthly-reports/jobs/{base_job.public_id}/fragments/rerun-diff"
        f"?compare_job_id={compare_job.public_id}"
    )

    assert fragment.status_code == 200
    assert "元ジョブに比較できる draft_markdown / final_markdown がまだありません" in fragment.text
    assert "HTML ONLY SHOULD NOT BE DIFFED" not in fragment.text
    assert "sha256:base-html-only" not in fragment.text


def test_monthly_report_ui_rerun_diff_escapes_markdown_content():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    original = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "html_rerun_diff_escape_household",
            "owner_user_id": "html-rerun-diff-escape-owner",
        },
    ).json()
    base_job = monthly_reports_router._store.get(original["job_id"])
    compare_job = monthly_reports_router._store.create_job(
        target_month=base_job.target_month,
        household_key=base_job.household_key,
        owner_user_id=base_job.owner_user_id,
    )
    monthly_reports_router._store.record_artifact(
        base_job.public_id,
        artifact_type="final_markdown",
        content="## 01 基本情報\n<script>alert('base')</script>",
        content_hash="sha256:base-script",
    )
    monthly_reports_router._store.record_artifact(
        compare_job.public_id,
        artifact_type="draft_markdown",
        content="## 01 基本情報\n<script>alert('compare')</script>",
        content_hash="sha256:compare-script",
    )

    fragment = client.get(
        f"/monthly-reports/jobs/{base_job.public_id}/fragments/rerun-diff"
        f"?compare_job_id={compare_job.public_id}"
    )

    assert fragment.status_code == 200
    assert "<script>alert" not in fragment.text
    assert "&lt;script&gt;alert" in fragment.text


def test_monthly_report_status_fragment_shows_running_recovery_guidance():
    os.environ["EB_AUTH_MODE"] = "mock"
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "html_running_recovery_household",
            "owner_user_id": "html-running-recovery-owner",
        },
    ).json()
    job = monthly_reports_router._store.claim_next_runnable_job(
        owner_user_id="html-running-recovery-owner"
    )
    assert job is not None

    status = client.get(
        f"/monthly-reports/jobs/{created['job_id']}/fragments/status"
    )

    assert status.status_code == 200
    assert "ページを閉じても処理は継続します" in status.text
    assert "自動更新" in status.text

    job.current_stage = "call_llm"
    job.worker_last_claimed_at = datetime.now(timezone.utc) - timedelta(minutes=31)
    stale_status = client.get(
        f"/monthly-reports/jobs/{created['job_id']}/fragments/status"
    )

    assert stale_status.status_code == 200
    assert "長時間更新がありません" in stale_status.text
    assert "worker runbook" in stale_status.text


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


def test_monthly_report_ui_google_source_action_fetches_default_sheet_ranges(
    monkeypatch: pytest.MonkeyPatch,
):
    os.environ["EB_AUTH_MODE"] = "mock"
    monkeypatch.setattr(
        monthly_reports_router,
        "_resolve_google_workspace_access_token",
        lambda current_user: "fake-access-token",
    )
    sheet_calls: list[tuple[str, str, str | None]] = []

    class FakeGoogleWorkspaceClient:
        def __init__(self, *, access_token):
            assert access_token == "fake-access-token"

        def fetch_doc(self, *, document_id: str, display_name: str | None = None):
            raise AssertionError("doc fetch should not be called")

        def fetch_sheet_values(
            self,
            *,
            spreadsheet_id: str,
            range_name: str,
            display_name: str | None = None,
        ):
            assert spreadsheet_id == "sheet-id"
            sheet_calls.append((spreadsheet_id, range_name, display_name))
            return GoogleWorkspaceSource(
                source_type="google_sheet",
                display_name=display_name or range_name,
                snapshot_text=f"{range_name}本文",
                content_hash=f"sha256:{range_name}",
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
            "household_key": "google_source_default_sheet_household",
            "owner_user_id": "html-google-source-default-sheet-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    fetched = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/google-sources",
        data={
            "csrf_token": token,
            "spreadsheet_id": "sheet-id",
        },
        headers={"HX-Request": "true"},
    )

    assert fetched.status_code == 200
    assert sheet_calls == [
        ("sheet-id", "student", "基本情報 student"),
        ("sheet-id", "'lesson plan'", "学習計画表 lesson plan"),
    ]
    assert "基本情報 student" in fetched.text
    assert "学習計画表 lesson plan" in fetched.text


def test_monthly_report_ui_google_source_action_can_generate_preview_oob(
    monkeypatch: pytest.MonkeyPatch,
):
    os.environ["EB_AUTH_MODE"] = "mock"
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-secret")
    monkeypatch.setenv("OPENROUTER_MODEL_REPORT", "mock/google-fetch-generate-model")
    monkeypatch.setenv("EB_MONTHLY_REPORT_PROMPT_VERSION", "monthly-report-vfetch-generate.1")
    monkeypatch.setattr(
        monthly_reports_router,
        "_resolve_google_workspace_access_token",
        lambda current_user: "fake-access-token",
    )

    class FakeGoogleWorkspaceClient:
        def __init__(self, *, access_token):
            assert access_token == "fake-access-token"

        def fetch_doc(self, *, document_id: str, display_name: str | None = None):
            return GoogleWorkspaceSource(
                source_type="google_doc",
                display_name=display_name or "面談メモ",
                snapshot_text="面談本文",
                content_hash="sha256:doc-fetch-generate",
            )

        def fetch_sheet_values(
            self,
            *,
            spreadsheet_id: str,
            range_name: str,
            display_name: str | None = None,
        ):
            return GoogleWorkspaceSource(
                source_type="google_sheet",
                display_name=display_name or range_name,
                snapshot_text=f"{range_name}本文",
                content_hash=f"sha256:{range_name}:fetch-generate",
            )

    def fake_complete(self, *, messages, model=None):
        assert model == "mock/google-fetch-generate-model"
        return LLMCompletion(
            content="\n\n".join(
                [
                    "## 01 基本情報\nURL投入から生成",
                    "## 02 塾での様子\n本文",
                    "## 03 授業内容\n本文",
                    "## 04 課題とアドバイス\n本文",
                    "## 05 学習の進捗\n本文",
                    "## 07 今後の授業計画\n本文",
                ]
            ),
            resolved_model="mock/google-fetch-generate-resolved",
            input_tokens=120,
            output_tokens=80,
            finish_reason="stop",
        )

    monkeypatch.setattr(
        monthly_reports_router,
        "GoogleWorkspaceClient",
        FakeGoogleWorkspaceClient,
    )
    monkeypatch.setattr(OpenRouterMonthlyReportProvider, "complete", fake_complete)
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/monthly-reports/jobs",
        json={
            "target_month": "2026-04",
            "household_key": "google_fetch_generate_household",
            "owner_user_id": "html-google-fetch-generate-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    generated = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/google-sources",
        data={
            "csrf_token": token,
            "doc_ids": "https://docs.google.com/document/d/doc-id/edit",
            "spreadsheet_id": "https://docs.google.com/spreadsheets/d/sheet-id/edit",
            "after_fetch_action": "generate_openrouter",
        },
        headers={"HX-Request": "true"},
    )
    preview = client.get(f"/monthly-reports/jobs/{job_id}/fragments/preview")
    validation = client.get(f"/monthly-reports/jobs/{job_id}/fragments/validation")

    assert generated.status_code == 200
    assert "面談メモ" in generated.text
    assert "基本情報 student" in generated.text
    assert "学習計画表 lesson plan" in generated.text
    assert 'id="preview-panel" hx-swap-oob="innerHTML"' in generated.text
    assert 'id="status-panel" hx-swap-oob="innerHTML"' in generated.text
    assert 'id="validation-panel" hx-swap-oob="innerHTML"' in generated.text
    assert 'id="operation-log-panel" hx-swap-oob="innerHTML"' in generated.text
    assert "URL投入から生成" in generated.text
    assert "レポート生成" in generated.text
    assert "完了" in generated.text
    assert "llm" in generated.text
    assert "draft_markdown" in preview.text
    assert "URL投入から生成" in preview.text
    assert "レポートビューに生成物を反映済み" in preview.text
    assert "non_empty_markdown" in validation.text


def test_monthly_report_ui_sheet_selector_fragment_lists_sheet_names(
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

        def fetch_sheet_titles(self, *, spreadsheet_id: str):
            assert spreadsheet_id == "sheet-id"
            return ["student", "lesson plan", "月次メモ"]

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
            "household_key": "sheet_selector_household",
            "owner_user_id": "html-sheet-selector-owner",
        },
    )
    job_id = created.json()["job_id"]
    detail = client.get(f"/monthly-reports/jobs/{job_id}")
    token = _CSRF_RE.search(detail.text).group("token")

    selector = client.post(
        f"/monthly-reports/jobs/{job_id}/fragments/sheet-selector",
        data={"csrf_token": token, "spreadsheet_id": "sheet-id"},
        headers={"HX-Request": "true"},
    )

    assert selector.status_code == 200
    assert "student_sheet_name" in selector.text
    assert "lesson_plan_sheet_name" in selector.text
    assert "student" in selector.text
    assert "lesson plan" in selector.text
    assert "月次メモ" in selector.text
    assert "/api/monthly-reports" not in selector.text


def test_monthly_report_ui_google_token_resolver_skips_non_uuid_mock_user(
    monkeypatch: pytest.MonkeyPatch,
):
    os.environ["EB_AUTH_MODE"] = "mock"
    monkeypatch.delenv("EB_GOOGLE_WORKSPACE_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("EB_MONTHLY_REPORT_DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("EB_GOOGLE_TOKEN_ENCRYPTION_KEY", "not-a-real-fernet-key")

    token = monthly_reports_router._resolve_google_workspace_access_token(
        monthly_reports_router.CurrentUser(
            user_id="mock-user@tomonokai-corp.com",
            email="mock-user@tomonokai-corp.com",
            role="admin",
        )
    )

    assert token is None


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
    audit_logs = monthly_reports_router._store.list_audit_logs(job_id)
    assert [entry.action for entry in audit_logs] == [
        "monthly_report_service_owned_workflow_executed"
    ]
    assert audit_logs[0].metadata["trigger"] == "html_run"
    assert audit_logs[0].metadata["mode"] == "mock"
    assert audit_logs[0].metadata["boundary"] == "service_owned_workflow"
    assert audit_logs[0].metadata["idempotency_key_present"] is True


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
        self.sources = [
            monthly_reports_router.MockSource(
                public_id="mrs_html_rls",
                job_id=job.public_id,
                source_type="google_doc",
                display_name="RLS source",
                snapshot_text="RLS source text",
            )
        ]
        self.artifacts = [
            monthly_reports_router.MockArtifact(
                public_id="mra_html_rls",
                job_id=job.public_id,
                artifact_type="draft_markdown",
                content="## 01 基本情報\nRLS draft",
                content_hash="sha256:html-rls",
            )
        ]
        self.validations = [
            monthly_reports_router.MockValidation(
                public_id="mrv_html_rls",
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
            public_id=f"mrs_html_rls_{len(self.sources) + 1}",
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
        return []

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
            public_id=f"mrf_html_rls_{len(self.job.feedback) + 1}",
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
            public_id=f"mra_html_rls_{len(self.artifacts) + 1}",
            job_id=public_id,
            artifact_type=artifact_type,
            content=content,
            content_hash=content_hash,
        )
        self.artifacts.append(artifact)
        return artifact


class _TrackingDirectStore:
    def __init__(self, inner) -> None:
        self._inner = inner
        self.recorded_llm_calls: list[dict[str, object | None]] = []

    def record_llm_call(self, public_id: str, **kwargs):
        self.recorded_llm_calls.append({"job_id": public_id, **kwargs})
        return self._inner.record_llm_call(public_id, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


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
