import pytest

from eb_app.monthly_reports.prompt_versions import (
    PromptVersionMetadata,
    PromptVersionRegistry,
    parse_prompt_version,
    validate_prompt_version,
)


def test_validate_prompt_version_accepts_monthly_report_date_revision_format():
    assert validate_prompt_version("monthly-report-v20260513.1") == (
        "monthly-report-v20260513.1"
    )
    parsed = parse_prompt_version("monthly-report-v20260513.12")

    assert parsed.value == "monthly-report-v20260513.12"
    assert parsed.date == "20260513"
    assert parsed.revision == 12


@pytest.mark.parametrize(
    "value",
    [
        "",
        "monthly-report-vtest.1",
        "monthly-report-v20260513",
        "monthly-report-v2026051.1",
        "monthly-report-v202605130.1",
        "monthly-report-v20260513.0",
        "monthly-report-v20260513.01",
        "monthly-report-v20260513.a",
        "monthly-report-v20260230.1",
        "monthly_report_v20260513.1",
        " monthly-report-v20260513.1",
        "monthly-report-v20260513.1 ",
    ],
)
def test_validate_prompt_version_rejects_invalid_values(value):
    with pytest.raises(ValueError, match="prompt_version"):
        validate_prompt_version(value)


def test_prompt_version_metadata_maps_recipe_hashes_and_app_version():
    metadata = PromptVersionMetadata(
        prompt_version="monthly-report-v20260517.1",
        static_recipe_id="economics-multistudent-scope-v1",
        template_hash="sha256:template",
        git_sha="abc123",
        app_version="app-20260517",
    )

    assert metadata.prompt_version == "monthly-report-v20260517.1"
    assert metadata.static_recipe_id == "economics-multistudent-scope-v1"
    assert metadata.template_hash == "sha256:template"
    assert metadata.git_sha == "abc123"
    assert metadata.app_version == "app-20260517"


def test_prompt_version_registry_returns_records_by_version():
    record = PromptVersionMetadata(
        prompt_version="monthly-report-v20260517.1",
        static_recipe_id="economics-multistudent-scope-v1",
        template_hash="sha256:template",
        git_sha="abc123",
        app_version="app-20260517",
    )
    registry = PromptVersionRegistry([record])

    assert registry.get("monthly-report-v20260517.1") == record
    assert registry.get("monthly-report-v20260517.2") is None


def test_prompt_version_registry_rejects_duplicate_versions():
    record = PromptVersionMetadata(
        prompt_version="monthly-report-v20260517.1",
        static_recipe_id="recipe-a",
    )

    with pytest.raises(ValueError, match="duplicate prompt_version"):
        PromptVersionRegistry([record, record])
