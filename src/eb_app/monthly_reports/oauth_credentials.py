from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from cryptography.fernet import Fernet
import httpx
import psycopg
from psycopg.rows import dict_row

from eb_app.monthly_reports.ids import PUBLIC_ID_PREFIXES, new_public_id

@dataclass(frozen=True)
class GoogleOAuthCredentialRecord:
    public_id: str
    user_id: str
    provider: str
    encrypted_provider_refresh_token: str
    encryption_key_version: str
    scope: str


@dataclass(frozen=True)
class GoogleOAuthAccessToken:
    access_token: str
    expires_in: int | None = None


class TokenCipher(Protocol):
    def encrypt(self, value: str) -> str:
        pass

    def decrypt(self, value: str) -> str:
        pass


class RefreshTokenStore(Protocol):
    def get_refresh_token(self, user_id: str) -> str | None:
        pass


class AccessTokenRefresher(Protocol):
    def refresh_access_token(self, refresh_token: str) -> GoogleOAuthAccessToken:
        pass


class FernetTokenCipher:
    def __init__(self, *, key: str) -> None:
        self._fernet = Fernet(key.encode("ascii"))

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")


class GoogleOAuthTokenRefreshError(RuntimeError):
    pass


class InMemoryGoogleOAuthCredentialStore:
    def __init__(
        self,
        *,
        cipher: TokenCipher,
        encryption_key_version: str,
    ) -> None:
        self._cipher = cipher
        self._encryption_key_version = encryption_key_version
        self._records: dict[str, GoogleOAuthCredentialRecord] = {}

    def upsert_refresh_token(
        self,
        *,
        user_id: str,
        refresh_token: str,
        scope: str,
        provider: str = "google",
    ) -> GoogleOAuthCredentialRecord:
        record = GoogleOAuthCredentialRecord(
            public_id=f"goc_{user_id}",
            user_id=user_id,
            provider=provider,
            encrypted_provider_refresh_token=self._cipher.encrypt(refresh_token),
            encryption_key_version=self._encryption_key_version,
            scope=scope,
        )
        self._records[user_id] = record
        return record

    def get_refresh_token(self, user_id: str) -> str | None:
        record = self._records.get(user_id)
        if record is None:
            return None
        return self._cipher.decrypt(record.encrypted_provider_refresh_token)

    def raw_record(self, user_id: str) -> GoogleOAuthCredentialRecord | None:
        return self._records.get(user_id)


class PostgresGoogleOAuthCredentialStore:
    def __init__(
        self,
        database_url: str,
        *,
        cipher: TokenCipher,
        encryption_key_version: str,
        id_factory=new_public_id,
    ) -> None:
        self._database_url = database_url
        self._cipher = cipher
        self._encryption_key_version = encryption_key_version
        self._id_factory = id_factory

    def upsert_refresh_token(
        self,
        *,
        user_id: str,
        refresh_token: str,
        scope: str,
        provider: str = "google",
    ) -> GoogleOAuthCredentialRecord:
        encrypted = self._cipher.encrypt(refresh_token)
        with self._connect() as conn:
            existing = conn.execute(
                """
                select public_id
                from public.google_oauth_credentials
                where user_id = %s and provider = %s
                """,
                (user_id, provider),
            ).fetchone()
            public_id = (
                existing["public_id"]
                if existing is not None
                else self._id_factory(PUBLIC_ID_PREFIXES.google_oauth_credential)
            )
            row = conn.execute(
                """
                insert into public.google_oauth_credentials
                    (
                        public_id,
                        user_id,
                        provider,
                        encrypted_provider_refresh_token,
                        encryption_key_version,
                        scope,
                        updated_at
                    )
                values (%s, %s, %s, %s, %s, %s, now())
                on conflict (user_id, provider) do update set
                    encrypted_provider_refresh_token = excluded.encrypted_provider_refresh_token,
                    encryption_key_version = excluded.encryption_key_version,
                    scope = excluded.scope,
                    updated_at = now()
                returning public_id, user_id::text, provider, encrypted_provider_refresh_token,
                    encryption_key_version, scope
                """,
                (
                    public_id,
                    user_id,
                    provider,
                    encrypted,
                    self._encryption_key_version,
                    scope,
                ),
            ).fetchone()
            assert row is not None
            return self._row_to_record(row)

    def get_refresh_token(self, user_id: str, provider: str = "google") -> str | None:
        record = self.raw_record(user_id, provider=provider)
        if record is None:
            return None
        return self._cipher.decrypt(record.encrypted_provider_refresh_token)

    def raw_record(
        self,
        user_id: str,
        *,
        provider: str = "google",
    ) -> GoogleOAuthCredentialRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                select public_id, user_id::text, provider, encrypted_provider_refresh_token,
                    encryption_key_version, scope
                from public.google_oauth_credentials
                where user_id = %s and provider = %s
                """,
                (user_id, provider),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_record(row)

    def ensure_test_auth_user(self, user_id: str, *, email: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into auth.users
                    (id, aud, role, email, is_sso_user, is_anonymous, created_at, updated_at)
                values (%s, 'authenticated', 'authenticated', %s, false, false, now(), now())
                on conflict (id) do nothing
                """,
                (user_id, email),
            )

    def delete_test_auth_user(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute("delete from auth.users where id = %s", (user_id,))

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._database_url, row_factory=dict_row)

    def _row_to_record(self, row: dict) -> GoogleOAuthCredentialRecord:
        return GoogleOAuthCredentialRecord(
            public_id=row["public_id"],
            user_id=row["user_id"],
            provider=row["provider"],
            encrypted_provider_refresh_token=row["encrypted_provider_refresh_token"],
            encryption_key_version=row["encryption_key_version"],
            scope=row["scope"],
        )


class GoogleOAuthTokenRefresher:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._client = http_client or httpx.Client(timeout=30.0)

    def refresh_access_token(self, refresh_token: str) -> GoogleOAuthAccessToken:
        try:
            response = self._client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            response = getattr(exc, "response", None)
            status = response.status_code if response is not None else "unknown"
            raise GoogleOAuthTokenRefreshError(
                f"Google OAuth token refresh failed with status {status}"
            ) from exc

        body = response.json()
        return GoogleOAuthAccessToken(
            access_token=body["access_token"],
            expires_in=body.get("expires_in"),
        )


def resolve_google_access_token(
    *,
    user_id: str,
    configured_access_token: str | None,
    credential_store: RefreshTokenStore,
    refresher: AccessTokenRefresher,
) -> str | None:
    if configured_access_token:
        return configured_access_token
    refresh_token = credential_store.get_refresh_token(user_id)
    if not refresh_token:
        return None
    return refresher.refresh_access_token(refresh_token).access_token
