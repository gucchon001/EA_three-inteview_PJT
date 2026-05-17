from __future__ import annotations

import time

from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient
import jwt
import pytest

from eb_app.auth.dependencies import CurrentUser
from eb_app.auth.supabase_google import (
    SupabaseGoogleProviderTokenPayload,
    google_refresh_token_grant_from_supabase_session,
)
from eb_app.main import create_app
import eb_app.routers.auth as auth_router


def test_google_oauth_credential_api_encrypts_and_stores_refresh_token(monkeypatch):
    monkeypatch.setenv("EB_AUTH_MODE", "mock")
    monkeypatch.setenv("EB_MONTHLY_REPORT_DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("EB_GOOGLE_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("EB_GOOGLE_TOKEN_ENCRYPTION_KEY_VERSION", "v-test")

    calls: list[dict] = []

    class FakeStore:
        def __init__(self, database_url, *, cipher, encryption_key_version):
            assert database_url == "postgresql://unused"
            assert encryption_key_version == "v-test"

        def upsert_refresh_token(self, *, user_id, refresh_token, scope, provider="google"):
            calls.append(
                {
                    "user_id": user_id,
                    "refresh_token": refresh_token,
                    "scope": scope,
                    "provider": provider,
                }
            )
            return FakeRecord()

    class FakeRecord:
        public_id = "goc_demo"
        provider = "google"
        scope = "openid documents.readonly"
        encryption_key_version = "v-test"

    monkeypatch.setattr(auth_router, "PostgresGoogleOAuthCredentialStore", FakeStore)

    client = TestClient(create_app())
    response = client.post(
        "/api/auth/google-oauth/credentials",
        json={
            "provider_refresh_token": "plain-refresh-token",
            "scope": "openid documents.readonly",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "credential_id": "goc_demo",
        "provider": "google",
        "scope": "openid documents.readonly",
        "encryption_key_version": "v-test",
    }
    assert calls == [
        {
            "user_id": "mock-user@tomonokai-corp.com",
            "refresh_token": "plain-refresh-token",
            "scope": "openid documents.readonly",
            "provider": "google",
        }
    ]


def test_google_oauth_credential_api_rejects_missing_secret_config(monkeypatch):
    monkeypatch.setenv("EB_AUTH_MODE", "mock")
    monkeypatch.setenv("EB_MONTHLY_REPORT_DATABASE_URL", "postgresql://unused")
    monkeypatch.delenv("EB_GOOGLE_TOKEN_ENCRYPTION_KEY", raising=False)

    client = TestClient(create_app())
    response = client.post(
        "/api/auth/google-oauth/credentials",
        json={
            "provider_refresh_token": "plain-refresh-token",
            "scope": "openid documents.readonly",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Google OAuth credential storage is not configured"


def test_google_oauth_credential_api_requires_auth(monkeypatch):
    for key in ("EB_AUTH_MODE", "EB_MONTHLY_REPORT_DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)

    client = TestClient(create_app())
    response = client.post(
        "/api/auth/google-oauth/credentials",
        json={"provider_refresh_token": "plain-refresh-token", "scope": "openid"},
    )

    assert response.status_code == 401


def test_supabase_google_oauth_session_api_stores_matching_user_refresh_token(monkeypatch):
    monkeypatch.setenv("EB_AUTH_MODE", "mock")
    monkeypatch.setenv("EB_MONTHLY_REPORT_DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("EB_GOOGLE_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("EB_GOOGLE_TOKEN_ENCRYPTION_KEY_VERSION", "v-test")

    calls: list[dict] = []

    class FakeStore:
        def __init__(self, database_url, *, cipher, encryption_key_version):
            pass

        def upsert_refresh_token(self, *, user_id, refresh_token, scope, provider="google"):
            calls.append(
                {
                    "user_id": user_id,
                    "refresh_token": refresh_token,
                    "scope": scope,
                    "provider": provider,
                }
            )
            return FakeRecord()

    class FakeRecord:
        public_id = "goc_session"
        provider = "google"
        scope = "openid email documents.readonly"
        encryption_key_version = "v-test"

    monkeypatch.setattr(auth_router, "PostgresGoogleOAuthCredentialStore", FakeStore)

    client = TestClient(create_app())
    response = client.post(
        "/api/auth/google-oauth/supabase-session",
        json={
            "supabase_user_id": "mock-user@tomonokai-corp.com",
            "provider_refresh_token": "session-refresh-token",
            "scope": "openid email documents.readonly",
        },
    )

    assert response.status_code == 200
    assert response.json()["credential_id"] == "goc_session"
    assert calls == [
        {
            "user_id": "mock-user@tomonokai-corp.com",
            "refresh_token": "session-refresh-token",
            "scope": "openid email documents.readonly",
            "provider": "google",
        }
    ]


def test_google_auth_bridge_reports_missing_public_supabase_settings(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    client = TestClient(create_app())
    response = client.get("/auth/google")

    assert response.status_code == 200
    assert "Missing public Supabase settings." in response.text
    assert "SUPABASE_URL" in response.text
    assert "SUPABASE_ANON_KEY" in response.text


def test_google_auth_bridge_embeds_public_supabase_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-public-key")
    monkeypatch.setenv("EB_GOOGLE_OAUTH_SCOPES", "openid email drive.readonly")

    client = TestClient(create_app())
    response = client.get("/auth/callback")

    assert response.status_code == 200
    assert "https://example.supabase.co" in response.text
    assert "anon-public-key" in response.text
    assert "openid email drive.readonly" in response.text
    assert "/auth/session-cookie" in response.text
    assert "/api/auth/google-oauth/supabase-session" in response.text


def test_monthly_report_workshop_e2e_page_embeds_live_api_flow(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-public-key")

    client = TestClient(create_app())
    response = client.get("/monthly-report-workshop/e2e")

    assert response.status_code == 200
    assert "Monthly Report Workshop Live E2E" in response.text
    assert "/api/monthly-reports/jobs" in response.text
    assert "/fetch-google-sources" in response.text
    assert "/run-openrouter" in response.text
    assert "/artifacts" in response.text
    assert "/validations" in response.text
    assert "/llm-calls" in response.text


def test_auth_session_cookie_endpoint_sets_http_only_cookie(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")
    monkeypatch.setenv("EB_ENV", "production")
    token = _supabase_token(
        email="member@tomonokai-corp.com",
        sub="user-cookie-bridge-123",
        role="authenticated",
    )

    client = TestClient(create_app())
    response = client.post("/auth/session-cookie", json={"access_token": token})

    assert response.status_code == 204
    set_cookie = response.headers["set-cookie"]
    assert "eb_auth_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "samesite=lax" in set_cookie.lower()


def test_auth_session_cookie_endpoint_rejects_invalid_token_without_cookie(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-supabase-jwt-secret")

    client = TestClient(create_app())
    response = client.post("/auth/session-cookie", json={"access_token": "not-a-token"})

    assert response.status_code == 401
    assert "set-cookie" not in response.headers


def test_supabase_google_oauth_session_api_rejects_user_mismatch(monkeypatch):
    monkeypatch.setenv("EB_AUTH_MODE", "mock")
    monkeypatch.setenv("EB_MONTHLY_REPORT_DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("EB_GOOGLE_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))

    client = TestClient(create_app())
    response = client.post(
        "/api/auth/google-oauth/supabase-session",
        json={
            "supabase_user_id": "other-user",
            "provider_refresh_token": "session-refresh-token",
            "scope": "openid",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Supabase user does not match current user"


def test_supabase_google_session_adapter_accepts_matching_google_refresh_token():
    grant = google_refresh_token_grant_from_supabase_session(
        current_user=CurrentUser(
            user_id="supabase-user-123",
            email="member@tomonokai-corp.com",
            role="authenticated",
        ),
        payload=SupabaseGoogleProviderTokenPayload(
            supabase_user_id="supabase-user-123",
            provider="google",
            provider_user_id="google-sub-456",
            email="member@tomonokai-corp.com",
            provider_refresh_token="provider-refresh-secret",
            scope="openid email https://www.googleapis.com/auth/drive.readonly",
        ),
    )

    assert grant.user_id == "supabase-user-123"
    assert grant.provider == "google"
    assert grant.provider_user_id == "google-sub-456"
    assert grant.scope == "openid email https://www.googleapis.com/auth/drive.readonly"
    assert "provider-refresh-secret" not in repr(grant)


def test_supabase_google_session_adapter_rejects_missing_supabase_user_id():
    with pytest.raises(HTTPException) as exc_info:
        google_refresh_token_grant_from_supabase_session(
            current_user=CurrentUser(
                user_id="supabase-user-123",
                email="member@tomonokai-corp.com",
                role="authenticated",
            ),
            payload=SupabaseGoogleProviderTokenPayload(
                supabase_user_id=" ",
                provider_refresh_token="provider-refresh-secret",
                scope="openid",
            ),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Supabase user id is required"


def test_supabase_google_session_adapter_rejects_provider_or_email_mismatch():
    current_user = CurrentUser(
        user_id="supabase-user-123",
        email="member@tomonokai-corp.com",
        role="authenticated",
    )

    with pytest.raises(HTTPException) as provider_exc:
        google_refresh_token_grant_from_supabase_session(
            current_user=current_user,
            payload=SupabaseGoogleProviderTokenPayload(
                supabase_user_id="supabase-user-123",
                provider="github",
                provider_refresh_token="provider-refresh-secret",
                scope="openid",
            ),
        )

    with pytest.raises(HTTPException) as email_exc:
        google_refresh_token_grant_from_supabase_session(
            current_user=current_user,
            payload=SupabaseGoogleProviderTokenPayload(
                supabase_user_id="supabase-user-123",
                email="other@tomonokai-corp.com",
                provider_refresh_token="provider-refresh-secret",
                scope="openid",
            ),
        )

    assert provider_exc.value.status_code == 422
    assert provider_exc.value.detail == "Google provider payload is required"
    assert email_exc.value.status_code == 403
    assert email_exc.value.detail == "Supabase provider email does not match current user"


def _supabase_token(
    *,
    email: str,
    sub: str,
    role: str,
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
