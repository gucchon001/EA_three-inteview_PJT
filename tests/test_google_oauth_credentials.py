from __future__ import annotations

import httpx
import os
import uuid
from cryptography.fernet import Fernet
import pytest

from eb_app.monthly_reports.oauth_credentials import (
    FernetTokenCipher,
    GoogleOAuthTokenRefreshError,
    GoogleOAuthTokenRefresher,
    GoogleOAuthAccessToken,
    InMemoryGoogleOAuthCredentialStore,
    PostgresGoogleOAuthCredentialStore,
    resolve_google_access_token,
)


def test_in_memory_google_oauth_credential_store_encrypts_refresh_token():
    cipher = FernetTokenCipher(key=Fernet.generate_key().decode("ascii"))
    store = InMemoryGoogleOAuthCredentialStore(cipher=cipher, encryption_key_version="v1")

    store.upsert_refresh_token(
        user_id="user-1",
        refresh_token="plain-refresh-token",
        scope="openid documents.readonly",
    )

    raw = store.raw_record("user-1")
    assert raw is not None
    assert raw.encrypted_provider_refresh_token != "plain-refresh-token"
    assert raw.encryption_key_version == "v1"
    assert raw.scope == "openid documents.readonly"
    assert store.get_refresh_token("user-1") == "plain-refresh-token"


def test_google_oauth_token_refresher_exchanges_refresh_token_without_leaking_secret():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"access_token": "new-access-token", "expires_in": 3600},
        )

    refresher = GoogleOAuthTokenRefresher(
        client_id="client-id",
        client_secret="client-secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    token = refresher.refresh_access_token("refresh-token")

    assert token.access_token == "new-access-token"
    assert token.expires_in == 3600
    assert len(requests) == 1
    assert requests[0].url == "https://oauth2.googleapis.com/token"
    assert requests[0].headers["content-type"] == "application/x-www-form-urlencoded"
    assert requests[0].read() == (
        b"client_id=client-id&client_secret=client-secret&refresh_token=refresh-token"
        b"&grant_type=refresh_token"
    )


def test_google_oauth_token_refresh_error_does_not_include_secrets_or_body():
    refresher = GoogleOAuthTokenRefresher(
        client_id="client-id",
        client_secret="client-secret",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(400, text="private token body")
            )
        ),
    )

    try:
        refresher.refresh_access_token("secret-refresh-token")
    except GoogleOAuthTokenRefreshError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected GoogleOAuthTokenRefreshError")

    assert message == "Google OAuth token refresh failed with status 400"
    assert "client-secret" not in message
    assert "secret-refresh-token" not in message
    assert "private token body" not in message


def test_resolve_google_access_token_prefers_configured_access_token():
    class Store:
        def get_refresh_token(self, user_id: str):
            raise AssertionError("refresh token should not be read")

    class Refresher:
        def refresh_access_token(self, refresh_token: str):
            raise AssertionError("refresh should not be called")

    assert (
        resolve_google_access_token(
            user_id="user-1",
            configured_access_token="configured-access-token",
            credential_store=Store(),
            refresher=Refresher(),
        )
        == "configured-access-token"
    )


def test_resolve_google_access_token_refreshes_from_stored_refresh_token():
    class Store:
        def get_refresh_token(self, user_id: str):
            assert user_id == "user-1"
            return "stored-refresh-token"

    class Refresher:
        def refresh_access_token(self, refresh_token: str):
            assert refresh_token == "stored-refresh-token"
            return GoogleOAuthAccessToken(access_token="refreshed-access-token")

    assert (
        resolve_google_access_token(
            user_id="user-1",
            configured_access_token=None,
            credential_store=Store(),
            refresher=Refresher(),
        )
        == "refreshed-access-token"
    )


def test_postgres_google_oauth_credential_store_upserts_encrypted_refresh_token():
    database_url = os.environ.get("EB_MONTHLY_REPORT_DATABASE_URL")
    if not database_url:
        pytest.skip("EB_MONTHLY_REPORT_DATABASE_URL is not set")

    user_id = str(uuid.uuid4())
    cipher = FernetTokenCipher(key=Fernet.generate_key().decode("ascii"))
    store = PostgresGoogleOAuthCredentialStore(
        database_url,
        cipher=cipher,
        encryption_key_version="v1",
        id_factory=_ids(["goc_demo_001", "goc_demo_002"]),
    )
    store.ensure_test_auth_user(user_id, email=f"{user_id}@tomonokai-corp.com")

    try:
        first = store.upsert_refresh_token(
            user_id=user_id,
            refresh_token="first-refresh-token",
            scope="openid documents.readonly",
        )
        second = store.upsert_refresh_token(
            user_id=user_id,
            refresh_token="second-refresh-token",
            scope="openid documents.readonly spreadsheets.readonly",
        )

        assert first.public_id == "goc_demo_001"
        assert second.public_id == "goc_demo_001"
        raw = store.raw_record(user_id)
        assert raw is not None
        assert raw.encrypted_provider_refresh_token != "second-refresh-token"
        assert raw.scope == "openid documents.readonly spreadsheets.readonly"
        assert store.get_refresh_token(user_id) == "second-refresh-token"
    finally:
        store.delete_test_auth_user(user_id)


def _ids(values: list[str]):
    iterator = iter(values)

    def next_id(_prefix: str) -> str:
        return next(iterator)

    return next_id
