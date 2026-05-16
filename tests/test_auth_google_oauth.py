from __future__ import annotations

from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient
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
    assert "/api/auth/google-oauth/supabase-session" in response.text


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
