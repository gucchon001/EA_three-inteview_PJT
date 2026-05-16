from __future__ import annotations

import json

import httpx

from eb_app.monthly_reports.google_workspace import (
    GoogleWorkspaceClient,
    GoogleWorkspaceFetchError,
    GoogleWorkspaceSource,
    extract_google_file_id,
    fetch_google_workspace_sources_for_job,
)
from eb_app.monthly_reports.jobs import MockJobStore


def test_extract_google_file_id_accepts_id_and_google_urls():
    raw_id = "1abcDEF_ghi-1234567890"

    assert extract_google_file_id(raw_id) == raw_id
    assert (
        extract_google_file_id(f"https://docs.google.com/document/d/{raw_id}/edit")
        == raw_id
    )
    assert (
        extract_google_file_id(
            f"https://docs.google.com/spreadsheets/d/{raw_id}/edit#gid=0"
        )
        == raw_id
    )
    assert extract_google_file_id(f"https://drive.google.com/open?id={raw_id}") == raw_id


def test_google_workspace_client_fetches_doc_as_plain_text():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer access-token"
        return httpx.Response(
            200,
            json={
                "title": "教師MTG",
                "body": {
                    "content": [
                        {
                            "paragraph": {
                                "elements": [
                                    {"textRun": {"content": "対象生徒A様の振り返り\n"}}
                                ]
                            }
                        },
                        {
                            "paragraph": {
                                "elements": [{"textRun": {"content": "Economics\n"}}]
                            }
                        },
                    ]
                },
            },
        )

    client = GoogleWorkspaceClient(
        access_token="access-token",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    source = client.fetch_doc(document_id="doc-id")

    assert source.source_type == "google_doc"
    assert source.display_name == "教師MTG"
    assert source.snapshot_text == "対象生徒A様の振り返り\nEconomics"
    assert source.content_hash.startswith("sha256:")
    assert requests[0].url == "https://docs.googleapis.com/v1/documents/doc-id"


def test_google_workspace_client_fetches_sheet_values_as_json_snapshot():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer access-token"
        return httpx.Response(
            200,
            json={
                "range": "student!A1:B2",
                "values": [["生徒氏名", "対象生徒A"], ["科目", "Economics"]],
            },
        )

    client = GoogleWorkspaceClient(
        access_token="access-token",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    source = client.fetch_sheet_values(
        spreadsheet_id="sheet-id",
        range_name="student!A1:B2",
        display_name="学習計画表 student",
    )

    assert source.source_type == "google_sheet"
    assert source.display_name == "学習計画表 student"
    assert json.loads(source.snapshot_text) == {
        "range": "student!A1:B2",
        "values": [["生徒氏名", "対象生徒A"], ["科目", "Economics"]],
    }
    assert source.content_hash.startswith("sha256:")
    assert (
        str(requests[0].url)
        == "https://sheets.googleapis.com/v4/spreadsheets/sheet-id/values/student%21A1%3AB2"
    )


def test_google_workspace_fetch_error_does_not_include_access_token_or_body():
    client = GoogleWorkspaceClient(
        access_token="secret-access-token",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(403, text="private google body")
            )
        ),
    )

    try:
        client.fetch_doc(document_id="doc-id")
    except GoogleWorkspaceFetchError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected GoogleWorkspaceFetchError")

    assert message == "Google Workspace fetch failed with status 403"
    assert "secret-access-token" not in message
    assert "private google body" not in message


def test_fetch_google_workspace_sources_for_job_records_docs_and_sheets():
    class FakeClient:
        def fetch_doc(self, *, document_id: str, display_name: str | None = None):
            assert document_id == "doc-id"
            return GoogleWorkspaceSource(
                source_type="google_doc",
                display_name=display_name or "doc",
                snapshot_text="doc text",
                content_hash="sha256:doc",
            )

        def fetch_sheet_values(
            self,
            *,
            spreadsheet_id: str,
            range_name: str,
            display_name: str | None = None,
        ):
            assert spreadsheet_id == "sheet-id"
            assert range_name == "student!A1:B2"
            return GoogleWorkspaceSource(
                source_type="google_sheet",
                display_name=display_name or "sheet",
                snapshot_text="sheet text",
                content_hash="sha256:sheet",
            )

    store = MockJobStore(id_factory=_ids(["mrj_demo", "mrs_doc", "mrs_sheet"]))
    job = store.create_job(target_month="2026-04", household_key="demo")

    sources = fetch_google_workspace_sources_for_job(
        store,
        job.public_id,
        client=FakeClient(),
        doc_ids=["doc-id"],
        sheet_ranges=[
            {
                "spreadsheet_id": "sheet-id",
                "range_name": "student!A1:B2",
                "display_name": "student sheet",
            }
        ],
    )

    assert [source.public_id for source in sources] == ["mrs_doc", "mrs_sheet"]
    assert [(source.source_type, source.display_name) for source in store.list_sources(job.public_id)] == [
        ("google_doc", "doc"),
        ("google_sheet", "student sheet"),
    ]


def _ids(values: list[str]):
    iterator = iter(values)

    def next_id(_prefix: str) -> str:
        return next(iterator)

    return next_id
