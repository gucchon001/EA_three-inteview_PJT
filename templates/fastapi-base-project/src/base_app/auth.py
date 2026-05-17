from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException

from base_app.config import Settings, get_settings


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    email: str
    role: str
    access_token: str | None = None


def assert_mock_auth_allowed(settings: Settings) -> None:
    if settings.auth_mode.strip().lower() == "mock" and settings.is_production_like:
        raise RuntimeError("Mock auth is not allowed in production-like environments")


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    settings = get_settings()
    mode = settings.auth_mode.strip().lower()

    if mode == "mock":
        assert_mock_auth_allowed(settings)
        return CurrentUser(
            user_id="local-user",
            email=f"local-user@{settings.allowed_email_domain}",
            role="admin",
        )

    if not authorization:
        raise HTTPException(status_code=401, detail="authentication required")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="invalid authorization header")

    # Replace this with Supabase JWT verification and domain checks.
    return CurrentUser(
        user_id="api-user",
        email=f"api-user@{settings.allowed_email_domain}",
        role="authenticated",
        access_token=token,
    )

