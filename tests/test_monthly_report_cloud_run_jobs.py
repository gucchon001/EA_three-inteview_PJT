from __future__ import annotations

import httpx
import pytest

from eb_app.monthly_reports.cloud_run_jobs import (
    CloudRunJobExecutor,
    CloudRunJobTriggerError,
    MetadataServerAccessTokenProvider,
)


class _StaticTokenProvider:
    def __init__(self, token: str) -> None:
        self.token = token

    def get_access_token(self) -> str:
        return self.token


def test_metadata_server_access_token_provider_prefers_env_token():
    provider = MetadataServerAccessTokenProvider(env_access_token="env-token")

    assert provider.get_access_token() == "env-token"


def test_metadata_server_access_token_provider_reads_metadata_server():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Metadata-Flavor"] == "Google"
        return httpx.Response(200, json={"access_token": "metadata-token"})

    provider = MetadataServerAccessTokenProvider(
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert provider.get_access_token() == "metadata-token"


def test_cloud_run_job_executor_runs_job_with_env_overrides():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["Authorization"]
        captured["body"] = request.content.decode("utf-8")
        return httpx.Response(200, json={"name": "operations/run-123"})

    executor = CloudRunJobExecutor(
        project_id="project-id",
        region="asia-northeast1",
        job_name="monthly-report-worker-staging",
        token_provider=_StaticTokenProvider("ya29.test-token"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    response = executor.run(env_vars={"EB_WORKER_JOB_ID": "mrj_targeted"})

    assert response["name"] == "operations/run-123"
    assert captured["url"] == (
        "https://run.googleapis.com/v2/projects/project-id/locations/asia-northeast1/jobs/monthly-report-worker-staging:run"
    )
    assert captured["auth"] == "Bearer ya29.test-token"
    assert "EB_WORKER_JOB_ID" in str(captured["body"])
    assert "mrj_targeted" in str(captured["body"])


def test_cloud_run_job_executor_raises_pii_safe_error_on_http_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "private details"}})

    executor = CloudRunJobExecutor(
        project_id="project-id",
        region="asia-northeast1",
        job_name="monthly-report-worker-staging",
        token_provider=_StaticTokenProvider("ya29.test-token"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(CloudRunJobTriggerError) as exc_info:
        executor.run(env_vars={"EB_WORKER_JOB_ID": "mrj_targeted"})

    assert "status 403" in str(exc_info.value)
    assert "private details" not in str(exc_info.value)
