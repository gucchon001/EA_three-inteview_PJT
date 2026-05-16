from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Annotated

import jwt
from jwt import InvalidTokenError
from fastapi import Header, HTTPException

from eb_app.auth.mock import get_mock_user
from eb_app.auth.safety import assert_mock_auth_allowed
from eb_app.config import get_settings


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    email: str
    role: str


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    settings = get_settings()
    if settings.auth_mode == "mock":
        assert_mock_auth_allowed(settings)
        email = os.environ.get("EB_MOCK_USER_EMAIL", "mock-user@tomonokai-corp.com")
        user = get_mock_user(email)
        return CurrentUser(
            user_id=user["email"],
            email=user["email"],
            role=user["role"],
        )

    if not authorization:
        raise HTTPException(status_code=401, detail="authentication required")

    return _current_user_from_supabase_token(authorization, settings)


def _current_user_from_supabase_token(authorization: str, settings) -> CurrentUser:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="invalid authorization header")
    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=503,
            detail="Supabase Auth verification is not configured",
        )

    try:
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
    return CurrentUser(user_id=user_id, email=email, role=role)
