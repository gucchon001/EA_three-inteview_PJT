from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import HTTPException

from eb_app.auth.dependencies import CurrentUser


@dataclass(frozen=True)
class SupabaseGoogleProviderTokenPayload:
    supabase_user_id: str | None
    provider_refresh_token: str | None
    scope: str | None
    provider: str | None = "google"
    provider_user_id: str | None = None
    email: str | None = None


@dataclass(frozen=True)
class GoogleRefreshTokenGrant:
    user_id: str
    scope: str
    provider: str
    refresh_token: str = field(repr=False)
    provider_user_id: str | None = None


def google_refresh_token_grant_from_supabase_session(
    *,
    current_user: CurrentUser,
    payload: SupabaseGoogleProviderTokenPayload,
) -> GoogleRefreshTokenGrant:
    supabase_user_id = _clean(payload.supabase_user_id)
    if not supabase_user_id:
        raise HTTPException(status_code=422, detail="Supabase user id is required")
    if supabase_user_id != current_user.user_id:
        raise HTTPException(
            status_code=403,
            detail="Supabase user does not match current user",
        )

    provider = _clean(payload.provider) or "google"
    if provider != "google":
        raise HTTPException(status_code=422, detail="Google provider payload is required")

    email = _clean(payload.email).lower()
    if email and email != current_user.email.lower():
        raise HTTPException(
            status_code=403,
            detail="Supabase provider email does not match current user",
        )

    refresh_token = _clean(payload.provider_refresh_token)
    if not refresh_token:
        raise HTTPException(status_code=422, detail="Google refresh token is required")

    scope = _clean(payload.scope)
    if not scope:
        raise HTTPException(status_code=422, detail="Google OAuth scope is required")

    return GoogleRefreshTokenGrant(
        user_id=current_user.user_id,
        refresh_token=refresh_token,
        scope=scope,
        provider=provider,
        provider_user_id=_clean(payload.provider_user_id) or None,
    )


def _clean(value: str | None) -> str:
    return (value or "").strip()
