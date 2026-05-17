from __future__ import annotations

import os
import time

from cryptography.hazmat.primitives.asymmetric import ec, rsa
import jwt
import pytest

import eb_app.auth.dependencies as auth_dependencies
from eb_app.auth.mock import get_mock_user, list_mock_users
from eb_app.auth.safety import assert_mock_auth_allowed
from eb_app.main import create_app
from eb_app.config import Settings
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clean_auth_env():
    keys = (
        "EB_AUTH_MODE",
        "EB_ENV",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL_REPORT",
        "OPENROUTER_MODEL",
        "OPENROUTER_TIMEOUT",
        "OPENROUTER_MAX_TOKENS",
        "SUPABASE_JWT_SECRET",
        "SUPABASE_JWT_AUDIENCE",
        "SUPABASE_URL",
        "EB_ALLOWED_EMAIL_DOMAIN",
        "EB_AUTH_SESSION_COOKIE_NAME",
    )
    old = {key: os.environ.get(key) for key in keys}
    for key in keys:
        os.environ.pop(key, None)
    yield
    for key, value in old.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_auth_mode_defaults_to_supabase():
    settings = Settings.from_env()

    assert settings.auth_mode == "supabase"


def test_openrouter_settings_read_from_environment():
    os.environ["OPENROUTER_API_KEY"] = "sk-test-secret"
    os.environ["OPENROUTER_MODEL_REPORT"] = "anthropic/claude-sonnet-4.6"
    os.environ["OPENROUTER_MODEL"] = "fallback/model"

    settings = Settings.from_env()

    assert settings.openrouter_api_key == "sk-test-secret"
    assert settings.openrouter_model_report == "anthropic/claude-sonnet-4.6"


def test_openrouter_model_report_falls_back_to_legacy_model_env():
    os.environ.pop("OPENROUTER_MODEL_REPORT", None)
    os.environ["OPENROUTER_MODEL"] = "fallback/model"

    settings = Settings.from_env()

    assert settings.openrouter_model_report == "fallback/model"


def test_mock_auth_exposes_admin_and_user_accounts():
    users = list_mock_users()

    assert users == (
        {
            "email": "mock-admin@tomonokai-corp.com",
            "role": "admin",
        },
        {
            "email": "mock-user@tomonokai-corp.com",
            "role": "user",
        },
    )
    assert get_mock_user("mock-admin@tomonokai-corp.com")["role"] == "admin"
    assert get_mock_user("mock-user@tomonokai-corp.com")["role"] == "user"


def test_unknown_mock_user_is_rejected():
    with pytest.raises(KeyError):
        get_mock_user("other@tomonokai-corp.com")


@pytest.mark.parametrize("env_name", ["production", "prod", "prd"])
def test_mock_auth_is_rejected_for_production_like_env(env_name: str):
    os.environ["EB_AUTH_MODE"] = "mock"
    os.environ["EB_ENV"] = env_name

    settings = Settings.from_env()

    with pytest.raises(RuntimeError, match="Mock auth is not allowed"):
        assert_mock_auth_allowed(settings)


def test_mock_auth_is_allowed_for_local_env():
    os.environ["EB_AUTH_MODE"] = "mock"
    os.environ["EB_ENV"] = "local"

    assert_mock_auth_allowed(Settings.from_env())


def test_monthly_report_api_requires_auth_when_not_in_mock_mode():
    client = TestClient(create_app())

    response = client.get("/api/monthly-reports/jobs")

    assert response.status_code == 401


def test_monthly_report_api_accepts_supabase_jwt_user():
    os.environ["SUPABASE_JWT_SECRET"] = "test-supabase-jwt-secret"
    token = _supabase_token(
        email="member@tomonokai-corp.com",
        sub="user-123",
        role="authenticated",
    )

    client = TestClient(create_app())
    response = client.get(
        "/api/monthly-reports/jobs",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


def test_monthly_report_api_accepts_supabase_jwt_from_auth_cookie():
    os.environ["SUPABASE_JWT_SECRET"] = "test-supabase-jwt-secret"
    token = _supabase_token(
        email="member@tomonokai-corp.com",
        sub="user-cookie-123",
        role="authenticated",
    )

    client = TestClient(create_app())
    client.cookies.set("eb_auth_session", token)
    response = client.get("/api/monthly-reports/jobs")

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("algorithm", "private_key"),
    [
        ("ES256", ec.generate_private_key(ec.SECP256R1())),
        ("RS256", rsa.generate_private_key(public_exponent=65537, key_size=2048)),
    ],
)
def test_monthly_report_api_accepts_supabase_jwks_token(
    monkeypatch: pytest.MonkeyPatch,
    algorithm: str,
    private_key,
):
    os.environ["SUPABASE_URL"] = "https://example.supabase.co"
    token = _supabase_asymmetric_token(
        email="member@tomonokai-corp.com",
        sub="user-jwks-123",
        role="authenticated",
        private_key=private_key,
        algorithm=algorithm,
    )

    class FakeSigningKey:
        key = private_key.public_key()

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, jwt_token: str):
            assert jwt_token == token
            return FakeSigningKey()

    monkeypatch.setattr(
        auth_dependencies,
        "_get_jwks_client",
        lambda supabase_url: FakeJwksClient(),
    )

    client = TestClient(create_app())
    response = client.get(
        "/api/monthly-reports/jobs",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


def test_monthly_report_api_requires_supabase_url_for_jwks_token():
    private_key = ec.generate_private_key(ec.SECP256R1())
    token = _supabase_asymmetric_token(
        email="member@tomonokai-corp.com",
        sub="user-jwks-123",
        role="authenticated",
        private_key=private_key,
        algorithm="ES256",
    )

    client = TestClient(create_app())
    response = client.get(
        "/api/monthly-reports/jobs",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Supabase Auth verification is not configured"


def test_monthly_report_api_rejects_supabase_jwt_wrong_domain():
    os.environ["SUPABASE_JWT_SECRET"] = "test-supabase-jwt-secret"
    token = _supabase_token(
        email="member@example.com",
        sub="user-123",
        role="authenticated",
    )

    client = TestClient(create_app())
    response = client.get(
        "/api/monthly-reports/jobs",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "email domain is not allowed"


def test_monthly_report_api_rejects_invalid_supabase_jwt():
    os.environ["SUPABASE_JWT_SECRET"] = "test-supabase-jwt-secret"

    client = TestClient(create_app())
    response = client.get(
        "/api/monthly-reports/jobs",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid authentication token"


def test_monthly_report_api_requires_supabase_jwt_secret_when_token_is_present():
    token = _supabase_token(
        email="member@tomonokai-corp.com",
        sub="user-123",
        role="authenticated",
    )

    client = TestClient(create_app())
    response = client.get(
        "/api/monthly-reports/jobs",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Supabase Auth verification is not configured"


def test_monthly_report_api_accepts_mock_auth_user():
    os.environ["EB_AUTH_MODE"] = "mock"
    client = TestClient(create_app())

    response = client.get("/api/monthly-reports/jobs")

    assert response.status_code == 200


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


def _supabase_asymmetric_token(
    *,
    email: str,
    sub: str,
    role: str,
    private_key,
    algorithm: str,
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
        private_key,
        algorithm=algorithm,
        headers={"kid": "test-key"},
    )
