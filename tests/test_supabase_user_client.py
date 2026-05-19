from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi import HTTPException

from eb_app.auth.dependencies import CurrentUser
from eb_app.auth.supabase_client import create_supabase_user_client
from eb_app.config import Settings


class FakePostgrest:
    def __init__(self) -> None:
        self.token: str | None = None

    def auth(self, token: str) -> None:
        self.token = token


class FakeSupabaseClient:
    def __init__(self) -> None:
        self.postgrest = FakePostgrest()


def test_create_supabase_user_client_attaches_current_user_jwt(monkeypatch):
    captured: dict[str, str] = {}
    fake_client = FakeSupabaseClient()

    def fake_create_client(url: str, key: str):
        captured["url"] = url
        captured["key"] = key
        return fake_client

    monkeypatch.setattr("eb_app.auth.supabase_client.create_client", fake_create_client)

    client = create_supabase_user_client(
        _settings(),
        CurrentUser(
            user_id="user-id",
            email="user@tomonokai-corp.com",
            role="authenticated",
            access_token="jwt-token",
        ),
    )

    assert client is fake_client
    assert captured == {
        "url": "http://127.0.0.1:56321",
        "key": "anon-key",
    }
    assert fake_client.postgrest.token == "jwt-token"


def test_create_supabase_user_client_requires_public_supabase_settings():
    with pytest.raises(HTTPException) as exc:
        create_supabase_user_client(
            replace(_settings(), supabase_url=None),
            CurrentUser(
                user_id="user-id",
                email="user@tomonokai-corp.com",
                role="authenticated",
                access_token="jwt-token",
            ),
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "Supabase user client is not configured"


def test_create_supabase_user_client_requires_user_access_token():
    with pytest.raises(HTTPException) as exc:
        create_supabase_user_client(
            _settings(),
            CurrentUser(
                user_id="user-id",
                email="user@tomonokai-corp.com",
                role="authenticated",
            ),
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Supabase user JWT is required for RLS access"


def _settings() -> Settings:
    return Settings(
        enable_mock_ui=False,
        auth_mode="supabase",
        env="local",
        monthly_report_database_url="postgresql://postgres:postgres@127.0.0.1:56322/postgres",
        monthly_report_prompt_version="monthly-report-v20260517.1",
        app_version="test",
        openrouter_api_key=None,
        openrouter_model_report="anthropic/claude-sonnet-4.6",
        openrouter_model_light=None,
        openrouter_timeout_seconds=120,
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
        google_token_encryption_key_version="local-v1",
        supabase_url="http://127.0.0.1:56321",
        supabase_anon_key="anon-key",
        google_oauth_scopes="openid email profile",
        supabase_jwt_secret="jwt-secret",
        supabase_jwt_audience="authenticated",
        allowed_email_domain="tomonokai-corp.com",
    )
