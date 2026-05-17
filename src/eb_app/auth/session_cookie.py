from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import Response

AUTH_SESSION_COOKIE_NAME = "eb_auth_session"
AUTH_SESSION_COOKIE_MAX_AGE_SECONDS = 60 * 60


@dataclass(frozen=True)
class AuthSessionCookieSettings:
    name: str
    max_age_seconds: int


def get_auth_session_cookie_settings() -> AuthSessionCookieSettings:
    return AuthSessionCookieSettings(
        name=(
            os.environ.get("EB_AUTH_SESSION_COOKIE_NAME", "").strip()
            or AUTH_SESSION_COOKIE_NAME
        ),
        max_age_seconds=_positive_int(
            os.environ.get("EB_AUTH_SESSION_COOKIE_MAX_AGE_SECONDS"),
            default=AUTH_SESSION_COOKIE_MAX_AGE_SECONDS,
        ),
    )


def get_auth_session_token(request: Request) -> str | None:
    return request.cookies.get(get_auth_session_cookie_settings().name)


def set_auth_session_cookie(response: Response, request: Request, token: str) -> None:
    settings = get_auth_session_cookie_settings()
    env = os.environ.get("EB_ENV", "local").strip().lower() or "local"
    response.set_cookie(
        settings.name,
        token,
        max_age=settings.max_age_seconds,
        httponly=True,
        secure=request.url.scheme == "https" or env not in {"local", "dev", "test"},
        samesite="lax",
        path="/",
    )


def _positive_int(raw: str | None, *, default: int) -> int:
    if raw is None or raw.strip() == "":
        return default
    value = int(raw.strip())
    return value if value > 0 else default
