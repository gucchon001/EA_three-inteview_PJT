from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Annotated

import jwt
from jwt import InvalidTokenError, PyJWKClient
from fastapi import Header, HTTPException, Request

from eb_app.auth.mock import get_mock_user
from eb_app.auth.safety import assert_mock_auth_allowed
from eb_app.auth.session_cookie import get_auth_session_token
from eb_app.config import get_settings

_ASYMMETRIC_ALGORITHMS = frozenset({"ES256", "RS256"})
_jwks_clients: dict[str, PyJWKClient] = {}


def _get_jwks_client(supabase_url: str) -> PyJWKClient:
    client = _jwks_clients.get(supabase_url)
    if client is None:
        client = PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")
        _jwks_clients[supabase_url] = client
    return client


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    email: str
    role: str
    access_token: str | None = None


def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    settings = get_settings()
    if settings.auth_mode == "mock":
        assert_mock_auth_allowed(settings)
        email = os.environ.get("EB_MOCK_USER_EMAIL", "y-haraguchi@tomonokai-corp.com")
        user = get_mock_user(email)
        user_id = os.environ.get("EB_MOCK_USER_ID", "").strip() or user["email"]
        return CurrentUser(
            user_id=user_id,
            email=user["email"],
            role=user["role"],
        )

    session_token = get_auth_session_token(request)
    if not authorization and not session_token:
        raise HTTPException(status_code=401, detail="authentication required")

    if authorization:
        return _current_user_from_supabase_token(authorization, settings)
    return _current_user_from_supabase_token(f"Bearer {session_token}", settings)


def _current_user_from_supabase_token(authorization: str, settings) -> CurrentUser:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="invalid authorization header")

    try:
        header = jwt.get_unverified_header(token)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid authentication token")
    alg = str(header.get("alg") or "").upper()

    try:
        if alg in _ASYMMETRIC_ALGORITHMS:
            if not settings.supabase_url:
                raise HTTPException(
                    status_code=503,
                    detail="Supabase Auth verification is not configured",
                )
            signing_key = _get_jwks_client(settings.supabase_url).get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=[alg],
                audience=settings.supabase_jwt_audience,
            )
        else:
            if not settings.supabase_jwt_secret:
                raise HTTPException(
                    status_code=503,
                    detail="Supabase Auth verification is not configured",
                )
            claims = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience=settings.supabase_jwt_audience,
            )
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid authentication token")

    email = str(claims.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="authentication token missing email")
    if not email.endswith(f"@{settings.allowed_email_domain.lower()}"):
        raise HTTPException(status_code=403, detail="email domain is not allowed")

    user_id = str(claims.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="authentication token missing subject")

    role = str(claims.get("role") or "authenticated").strip() or "authenticated"
    return CurrentUser(user_id=user_id, email=email, role=role, access_token=token)
