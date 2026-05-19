from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx


class CloudRunJobTriggerError(RuntimeError):
    pass


class AccessTokenProvider(Protocol):
    def get_access_token(self) -> str: ...


@dataclass(frozen=True)
class MetadataServerAccessTokenProvider:
    env_access_token: str | None = None
    timeout_seconds: float = 10.0
    http_client: httpx.Client | None = None

    def get_access_token(self) -> str:
        if self.env_access_token:
            return self.env_access_token
        client = self.http_client or httpx.Client(timeout=self.timeout_seconds)
        try:
            response = client.get(
                "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
                headers={"Metadata-Flavor": "Google"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            response = getattr(exc, "response", None)
            status = response.status_code if response is not None else "unknown"
            raise CloudRunJobTriggerError(
                f"metadata server access token fetch failed with status {status}"
            ) from exc
        access_token = str(response.json().get("access_token") or "").strip()
        if not access_token:
            raise CloudRunJobTriggerError("metadata server returned empty access token")
        return access_token


@dataclass(frozen=True)
class CloudRunJobExecutor:
    project_id: str
    region: str
    job_name: str
    token_provider: AccessTokenProvider
    timeout_seconds: float = 15.0
    http_client: httpx.Client | None = None

    def run(
        self,
        *,
        env_vars: dict[str, str] | None = None,
    ) -> dict:
        payload: dict[str, object] = {}
        if env_vars:
            payload["overrides"] = {
                "containerOverrides": [
                    {
                        "env": [
                            {"name": key, "value": value}
                            for key, value in sorted(env_vars.items())
                        ]
                    }
                ]
            }
        client = self.http_client or httpx.Client(timeout=self.timeout_seconds)
        access_token = self.token_provider.get_access_token()
        try:
            response = client.post(
                f"https://run.googleapis.com/v2/projects/{self.project_id}/locations/{self.region}/jobs/{self.job_name}:run",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            response = getattr(exc, "response", None)
            status = response.status_code if response is not None else "unknown"
            raise CloudRunJobTriggerError(
                f"cloud run worker trigger failed with status {status}"
            ) from exc
        body = response.json()
        if not isinstance(body, dict):
            raise CloudRunJobTriggerError("cloud run worker trigger returned invalid response")
        return body
