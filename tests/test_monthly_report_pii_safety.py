from __future__ import annotations

from pathlib import Path

import httpx

from eb_app.monthly_reports.google_workspace import (
    GoogleWorkspaceClient,
    GoogleWorkspaceFetchError,
)
from eb_app.monthly_reports.jobs import JobStatus, MockJobStore
from eb_app.monthly_reports.oauth_credentials import (
    GoogleOAuthTokenRefreshError,
    GoogleOAuthTokenRefresher,
)
from eb_app.monthly_reports.workflow import (
    OpenRouterMonthlyReportProvider,
    ProviderCallError,
    StaticMonthlyReportProvider,
    run_monthly_report_job,
)


def test_openrouter_provider_error_does_not_include_key_prompt_or_response_body():
    api_key = "sk-pii-secret"
    prompt_pii = "生徒Aの電話番号 090-0000-0000"
    response_pii = "upstream echoed 090-1111-2222 and sk-pii-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {api_key}"
        return httpx.Response(500, text=response_pii)

    provider = OpenRouterMonthlyReportProvider(
        api_key=api_key,
        model="test/model",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        provider.complete(messages=[{"role": "user", "content": prompt_pii}])
    except ProviderCallError as exc:
        message = str(exc)
    else:
        raise AssertionError("ProviderCallError was not raised")

    assert "OpenRouter call failed with status 500" == message
    assert api_key not in message
    assert prompt_pii not in message
    assert response_pii not in message


def test_google_workspace_fetch_error_does_not_include_token_or_response_body():
    access_token = "ya29.pii-access-token"
    response_pii = "Google body includes 生徒A and token ya29.pii-access-token"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {access_token}"
        return httpx.Response(403, text=response_pii)

    client = GoogleWorkspaceClient(
        access_token=access_token,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        client.fetch_doc(document_id="doc-with-pii")
    except GoogleWorkspaceFetchError as exc:
        message = str(exc)
    else:
        raise AssertionError("GoogleWorkspaceFetchError was not raised")

    assert message == "Google Workspace fetch failed with status 403"
    assert access_token not in message
    assert response_pii not in message


def test_google_oauth_refresh_error_does_not_include_secrets_or_response_body():
    client_secret = "google-client-secret-pii"
    refresh_token = "google-refresh-token-pii"
    response_pii = "invalid refresh token google-refresh-token-pii"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text=response_pii)

    refresher = GoogleOAuthTokenRefresher(
        client_id="client-id",
        client_secret=client_secret,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        refresher.refresh_access_token(refresh_token)
    except GoogleOAuthTokenRefreshError as exc:
        message = str(exc)
    else:
        raise AssertionError("GoogleOAuthTokenRefreshError was not raised")

    assert message == "Google OAuth token refresh failed with status 400"
    assert client_secret not in message
    assert refresh_token not in message
    assert response_pii not in message


def test_validation_failure_error_message_does_not_include_draft_body_pii():
    store = MockJobStore()
    job = store.create_job(
        target_month="2026-04",
        household_key="household-pii",
        owner_user_id="mock-user@tomonokai-corp.com",
    )
    pii_draft = "生徒Aの電話番号 090-3333-4444。本文はあるが必須見出しはない。"
    provider = StaticMonthlyReportProvider(content=pii_draft)

    failed = run_monthly_report_job(
        store,
        job.public_id,
        provider=provider,
        template_path=Path("docs/samples/monthly-reports/monthly_pattern_b_content.template.md"),
    )

    assert failed.status == JobStatus.FAILED
    assert failed.error_type == "validation_failed"
    assert failed.error_message is not None
    assert pii_draft not in failed.error_message
    assert "090-3333-4444" not in failed.error_message
