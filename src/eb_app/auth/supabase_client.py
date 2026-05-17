from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from eb_app.auth.dependencies import CurrentUser
from eb_app.config import Settings

create_client: Any | None = None


def create_supabase_user_client(settings: Settings, current_user: CurrentUser) -> Any:
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(
            status_code=503,
            detail="Supabase user client is not configured",
        )
    if not current_user.access_token:
        raise HTTPException(
            status_code=401,
            detail="Supabase user JWT is required for RLS access",
        )

    client_factory = create_client or _load_create_client()
    client = client_factory(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(current_user.access_token)
    return client


def _load_create_client() -> Any:
    try:
        from supabase import create_client as supabase_create_client
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="supabase-py is not installed",
        ) from exc
    return supabase_create_client
