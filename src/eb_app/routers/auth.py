from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from eb_app.auth.dependencies import CurrentUser, get_current_user
from eb_app.auth.supabase_google import (
    SupabaseGoogleProviderTokenPayload,
    google_refresh_token_grant_from_supabase_session,
)
from eb_app.config import get_settings
from eb_app.monthly_reports.oauth_credentials import (
    FernetTokenCipher,
    PostgresGoogleOAuthCredentialStore,
)

router = APIRouter()


class StoreGoogleOAuthCredentialRequest(BaseModel):
    provider_refresh_token: str = Field(min_length=1)
    scope: str = Field(min_length=1)


class StoreSupabaseGoogleOAuthSessionRequest(StoreGoogleOAuthCredentialRequest):
    supabase_user_id: str = Field(min_length=1)
    provider: str | None = None
    provider_user_id: str | None = None
    email: str | None = None


def _store_google_refresh_token(
    *,
    user_id: str,
    refresh_token: str,
    scope: str,
) -> dict[str, Any]:
    settings = get_settings()
    if not (
        settings.monthly_report_database_url
        and settings.google_token_encryption_key
        and settings.google_token_encryption_key_version
    ):
        raise HTTPException(
            status_code=503,
            detail="Google OAuth credential storage is not configured",
        )

    record = PostgresGoogleOAuthCredentialStore(
        settings.monthly_report_database_url,
        cipher=FernetTokenCipher(key=settings.google_token_encryption_key),
        encryption_key_version=settings.google_token_encryption_key_version,
    ).upsert_refresh_token(
        user_id=user_id,
        refresh_token=refresh_token,
        scope=scope,
    )
    return {
        "credential_id": record.public_id,
        "provider": record.provider,
        "scope": record.scope,
        "encryption_key_version": record.encryption_key_version,
    }


@router.post("/google-oauth/credentials")
def store_google_oauth_credential(
    payload: StoreGoogleOAuthCredentialRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    return _store_google_refresh_token(
        user_id=current_user.user_id,
        refresh_token=payload.provider_refresh_token,
        scope=payload.scope,
    )


@router.post("/google-oauth/supabase-session")
def store_supabase_google_oauth_session(
    payload: StoreSupabaseGoogleOAuthSessionRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    grant = google_refresh_token_grant_from_supabase_session(
        current_user=current_user,
        payload=SupabaseGoogleProviderTokenPayload(
            supabase_user_id=payload.supabase_user_id,
            provider_refresh_token=payload.provider_refresh_token,
            scope=payload.scope,
            provider=payload.provider,
            provider_user_id=payload.provider_user_id,
            email=payload.email,
        ),
    )
    return _store_google_refresh_token(
        user_id=grant.user_id,
        refresh_token=grant.refresh_token,
        scope=grant.scope,
    )
