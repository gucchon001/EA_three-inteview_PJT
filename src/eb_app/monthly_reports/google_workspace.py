from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from urllib.parse import parse_qs, quote, urlparse

import httpx

from eb_app.monthly_reports.jobs import MockJobStore, MockSource
from eb_app.monthly_reports.postgres_store import PostgresJobStore


JobStore = MockJobStore | PostgresJobStore


@dataclass(frozen=True)
class GoogleWorkspaceSource:
    source_type: str
    display_name: str
    snapshot_text: str
    content_hash: str


class GoogleWorkspaceFetchError(RuntimeError):
    pass


class GoogleWorkspaceSourceClient:
    def fetch_doc(
        self,
        *,
        document_id: str,
        display_name: str | None = None,
    ) -> GoogleWorkspaceSource:
        raise NotImplementedError

    def fetch_sheet_values(
        self,
        *,
        spreadsheet_id: str,
        range_name: str,
        display_name: str | None = None,
    ) -> GoogleWorkspaceSource:
        raise NotImplementedError


class GoogleWorkspaceClient:
    def __init__(
        self,
        *,
        access_token: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._access_token = access_token
        self._client = http_client or httpx.Client(timeout=30.0)

    def fetch_doc(self, *, document_id: str, display_name: str | None = None) -> GoogleWorkspaceSource:
        doc_id = extract_google_file_id(document_id)
        body = self._get_json(f"https://docs.googleapis.com/v1/documents/{doc_id}")
        title = display_name or body.get("title") or doc_id
        text = _google_doc_to_plain_text(body)
        return GoogleWorkspaceSource(
            source_type="google_doc",
            display_name=title,
            snapshot_text=text,
            content_hash=_hash_text(text),
        )

    def fetch_sheet_values(
        self,
        *,
        spreadsheet_id: str,
        range_name: str,
        display_name: str | None = None,
    ) -> GoogleWorkspaceSource:
        sheet_id = extract_google_file_id(spreadsheet_id)
        encoded_range = quote(range_name, safe="")
        body = self._get_json(
            f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{encoded_range}"
        )
        snapshot_text = json.dumps(
            {
                "range": body.get("range") or range_name,
                "values": body.get("values") or [],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return GoogleWorkspaceSource(
            source_type="google_sheet",
            display_name=display_name or body.get("range") or range_name,
            snapshot_text=snapshot_text,
            content_hash=_hash_text(snapshot_text),
        )

    def _get_json(self, url: str) -> dict:
        try:
            response = self._client.get(
                url,
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            response = getattr(exc, "response", None)
            status = response.status_code if response is not None else "unknown"
            raise GoogleWorkspaceFetchError(
                f"Google Workspace fetch failed with status {status}"
            ) from exc
        return response.json()


def extract_google_file_id(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise ValueError("Google file id is required")
    if "://" not in candidate:
        return candidate

    parsed = urlparse(candidate)
    query_id = parse_qs(parsed.query).get("id")
    if query_id and query_id[0]:
        return query_id[0]

    match = re.search(r"/d/([^/]+)", parsed.path)
    if match:
        return match.group(1)
    raise ValueError("could not extract Google file id")


def _google_doc_to_plain_text(body: dict) -> str:
    parts: list[str] = []
    for block in ((body.get("body") or {}).get("content") or []):
        paragraph = block.get("paragraph") or {}
        for element in paragraph.get("elements") or []:
            text_run = element.get("textRun") or {}
            content = text_run.get("content")
            if content:
                parts.append(content)
    return "".join(parts).strip()


def _hash_text(text: str) -> str:
    return f"sha256:{sha256(text.encode('utf-8')).hexdigest()}"


def fetch_google_workspace_sources_for_job(
    store: JobStore,
    job_id: str,
    *,
    client: GoogleWorkspaceSourceClient,
    doc_ids: list[str],
    sheet_ranges: list[dict[str, str]],
) -> list[MockSource]:
    recorded: list[MockSource] = []
    for document_id in doc_ids:
        source = client.fetch_doc(document_id=document_id)
        recorded.append(_record_source(store, job_id, source))
    for sheet_range in sheet_ranges:
        source = client.fetch_sheet_values(
            spreadsheet_id=sheet_range["spreadsheet_id"],
            range_name=sheet_range["range_name"],
            display_name=sheet_range.get("display_name"),
        )
        recorded.append(_record_source(store, job_id, source))
    return recorded


def _record_source(
    store: JobStore,
    job_id: str,
    source: GoogleWorkspaceSource,
) -> MockSource:
    return store.record_source(
        job_id,
        source_type=source.source_type,
        display_name=source.display_name,
        snapshot_text=source.snapshot_text,
        content_hash=source.content_hash,
    )
