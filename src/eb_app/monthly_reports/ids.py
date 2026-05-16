from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4


_PUBLIC_ID_RE = re.compile(r"^[a-z]{3}_[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
class PublicIdPrefixes:
    job: str = "mrj"
    source: str = "mrs"
    artifact: str = "mra"
    validation: str = "mrv"
    llm_call: str = "llm"
    google_oauth_credential: str = "goc"


PUBLIC_ID_PREFIXES = PublicIdPrefixes()


def new_public_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def new_job_id() -> str:
    return new_public_id(PUBLIC_ID_PREFIXES.job)


def new_source_id() -> str:
    return new_public_id(PUBLIC_ID_PREFIXES.source)


def new_artifact_id() -> str:
    return new_public_id(PUBLIC_ID_PREFIXES.artifact)


def new_validation_id() -> str:
    return new_public_id(PUBLIC_ID_PREFIXES.validation)


def new_llm_call_id() -> str:
    return new_public_id(PUBLIC_ID_PREFIXES.llm_call)


def new_google_oauth_credential_id() -> str:
    return new_public_id(PUBLIC_ID_PREFIXES.google_oauth_credential)


def has_public_id_prefix(public_id: str, prefix: str) -> bool:
    return public_id.startswith(f"{prefix}_")


def validate_public_id(public_id: str, prefix: str) -> str:
    if not has_public_id_prefix(public_id, prefix) or not _PUBLIC_ID_RE.match(public_id):
        raise ValueError(f"expected public id with {prefix}_ prefix")
    return public_id
