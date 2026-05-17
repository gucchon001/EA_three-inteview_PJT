from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
import re


PROMPT_VERSION_FORMAT = "monthly-report-vYYYYMMDD.N"
PROMPT_VERSION_PATTERN = re.compile(
    r"^monthly-report-v(?P<date>\d{8})\.(?P<revision>[1-9]\d*)$"
)


@dataclass(frozen=True)
class ParsedPromptVersion:
    value: str
    date: str
    revision: int


@dataclass(frozen=True)
class PromptVersionMetadata:
    prompt_version: str
    static_recipe_id: str | None = None
    template_hash: str | None = None
    git_sha: str | None = None
    app_version: str | None = None

    def __post_init__(self) -> None:
        validate_prompt_version(self.prompt_version)


class PromptVersionRegistry:
    def __init__(self, records: Iterable[PromptVersionMetadata] = ()) -> None:
        self._records: dict[str, PromptVersionMetadata] = {}
        for record in records:
            self.add(record)

    def add(self, record: PromptVersionMetadata) -> None:
        if record.prompt_version in self._records:
            raise ValueError(f"duplicate prompt_version: {record.prompt_version}")
        self._records[record.prompt_version] = record

    def get(self, prompt_version: str) -> PromptVersionMetadata | None:
        validate_prompt_version(prompt_version)
        return self._records.get(prompt_version)


def parse_prompt_version(value: str) -> ParsedPromptVersion:
    match = PROMPT_VERSION_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(
            f"prompt_version must match {PROMPT_VERSION_FORMAT}: {value!r}"
        )
    date = match.group("date")
    try:
        datetime.strptime(date, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(
            f"prompt_version date must be a valid YYYYMMDD date: {value!r}"
        ) from exc
    return ParsedPromptVersion(
        value=value,
        date=date,
        revision=int(match.group("revision")),
    )


def validate_prompt_version(value: str) -> str:
    return parse_prompt_version(value).value
