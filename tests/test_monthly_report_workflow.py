from pathlib import Path

import httpx
import pytest

from eb_app.monthly_reports.jobs import JobStatus, MockJobStore
from eb_app.monthly_reports.workflow import (
    OpenRouterMonthlyReportProvider,
    ProviderCallError,
    StaticMonthlyReportProvider,
    run_claimed_monthly_report_job,
    run_monthly_report_job,
)


def test_run_monthly_report_job_builds_messages_calls_provider_validates_and_persists(
    tmp_path: Path,
):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    tone = tmp_path / "tone.md"
    tone.write_text("FAMILY TONE", encoding="utf-8")
    store = MockJobStore(
        id_factory=_ids(["mrj_demo", "mrs_demo", "llm_demo", "mrv_demo", "mra_demo"])
    )
    job = store.create_job(
        target_month="2026-04",
        household_key="demo",
        prompt_scope_notes="対象は平林様 Economics のみ",
        model_report="mock/report-model",
        resolved_model_report="mock/report-model",
    )
    store.record_source(
        job.public_id,
        source_type="doc",
        display_name="面談メモ",
        snapshot_text="4月は需要曲線の読み取りを扱った。",
        content_hash="sha256:source-demo",
    )
    provider = StaticMonthlyReportProvider("# 4月度 月次レポート\n\n本文です。")

    result = run_monthly_report_job(
        store,
        job.public_id,
        provider=provider,
        template_path=template,
        rules_excerpt_path=tone,
    )

    assert result.status == JobStatus.SUCCEEDED
    artifacts = store.list_artifacts(job.public_id)
    assert len(artifacts) == 1
    assert artifacts[0].artifact_type == "draft_markdown"
    assert artifacts[0].content == "# 4月度 月次レポート\n\n本文です。"
    validations = store.list_validations(job.public_id)
    assert [(v.rule_id, v.severity) for v in validations] == [
        ("non_empty_markdown", "info")
    ]
    assert "対象は平林様 Economics のみ" in provider.last_messages[1]["content"]
    assert "4月は需要曲線" in provider.last_messages[1]["content"]
    llm_calls = store.list_llm_calls(job.public_id)
    assert len(llm_calls) == 1
    assert llm_calls[0].public_id == "llm_demo"
    assert llm_calls[0].prompt_kind == "report"
    assert llm_calls[0].provider == "openrouter"
    assert llm_calls[0].requested_model == "mock/report-model"
    assert llm_calls[0].resolved_model == "mock/report-model"
    assert llm_calls[0].request_hash.startswith("sha256:")
    assert llm_calls[0].response_hash.startswith("sha256:")
    assert llm_calls[0].error_type is None


def test_run_claimed_monthly_report_job_does_not_start_job_twice(tmp_path: Path):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = MockJobStore()
    job = store.create_job(target_month="2026-04", household_key="demo")
    claimed = store.claim_next_queued_job()

    assert claimed is not None
    result = run_claimed_monthly_report_job(
        store,
        claimed.public_id,
        provider=StaticMonthlyReportProvider("# claimed draft"),
        template_path=template,
    )

    assert result.status == JobStatus.SUCCEEDED
    assert result.completed_stages == [
        "fetch_sources",
        "bundle",
        "build_messages",
        "call_llm",
        "validate",
        "persist",
    ]
    assert store.list_artifacts(job.public_id)[0].content == "# claimed draft"


def test_run_monthly_report_job_records_validation_error_and_fails_empty_draft(
    tmp_path: Path,
):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = MockJobStore(id_factory=_ids(["mrj_demo", "llm_demo", "mrv_demo", "mra_demo"]))
    job = store.create_job(target_month="2026-04", household_key="demo")
    provider = StaticMonthlyReportProvider("  ")

    result = run_monthly_report_job(
        store,
        job.public_id,
        provider=provider,
        template_path=template,
    )

    assert result.status == JobStatus.FAILED
    assert result.current_stage == "validate"
    assert result.error_type == "validation_failed"
    assert result.error_message == "draft markdown is empty"
    validations = store.list_validations(job.public_id)
    assert [(v.rule_id, v.severity, v.message) for v in validations] == [
        ("non_empty_markdown", "error", "draft markdown is empty")
    ]
    assert store.list_llm_calls(job.public_id)[0].public_id == "llm_demo"
    assert store.list_llm_calls(job.public_id)[0].error_type is None
    assert store.list_artifacts(job.public_id) == []


def test_run_monthly_report_job_fails_when_draft_mentions_excluded_student_from_scope(
    tmp_path: Path,
):
    fixture_dir = Path("tests/fixtures/monthly_reports/economics_multistudent_scope")
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = MockJobStore(
        id_factory=_ids(["mrj_demo", "mrs_demo", "llm_demo", "mrv_demo", "mra_demo"])
    )
    job = store.create_job(
        target_month="2026-04",
        household_key="demo",
        prompt_scope_notes=(fixture_dir / "expected_prompt_scope_notes.txt").read_text(
            encoding="utf-8"
        ),
    )
    store.record_source(
        job.public_id,
        source_type="doc",
        display_name="面談メモ",
        snapshot_text=(fixture_dir / "_gws_doc_teacher_MTG_gemini.txt").read_text(
            encoding="utf-8"
        ),
        content_hash="sha256:source-demo",
    )
    provider = StaticMonthlyReportProvider(
        "# 4月度 月次レポート\n\n対象外生徒B様は試験対策が順調でした。"
    )

    result = run_monthly_report_job(
        store,
        job.public_id,
        provider=provider,
        template_path=template,
    )

    assert result.status == JobStatus.FAILED
    assert result.current_stage == "validate"
    assert result.error_type == "validation_failed"
    validations = store.list_validations(job.public_id)
    assert [(v.rule_id, v.severity, v.message) for v in validations] == [
        ("multistudent_scope_exclusion", "error", "draft mentions excluded scope: 対象外生徒B様")
    ]
    assert store.list_artifacts(job.public_id) == []


def test_run_monthly_report_job_fails_when_required_heading_is_missing(
    tmp_path: Path,
):
    template = tmp_path / "template.md"
    template.write_text(
        "\n".join(
            [
                "## 01 基本情報",
                "## 02 塾での様子",
                "## 03 授業内容",
            ]
        ),
        encoding="utf-8",
    )
    store = MockJobStore(id_factory=_ids(["mrj_demo", "llm_demo", "mrv_demo", "mra_demo"]))
    job = store.create_job(target_month="2026-04", household_key="demo")
    provider = StaticMonthlyReportProvider(
        "\n".join(
            [
                "## 01 基本情報",
                "本文",
                "## 03 授業内容",
                "本文",
            ]
        )
    )

    result = run_monthly_report_job(
        store,
        job.public_id,
        provider=provider,
        template_path=template,
    )

    assert result.status == JobStatus.FAILED
    assert result.current_stage == "validate"
    assert result.error_type == "validation_failed"
    validations = store.list_validations(job.public_id)
    assert [(v.rule_id, v.severity, v.message) for v in validations] == [
        ("required_headings", "error", "draft is missing required headings: ## 02 塾での様子")
    ]
    assert store.list_artifacts(job.public_id) == []


def test_run_monthly_report_job_fails_when_forbidden_distribution_term_is_present(
    tmp_path: Path,
):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = MockJobStore(id_factory=_ids(["mrj_demo", "llm_demo", "mrv_demo", "mra_demo"]))
    job = store.create_job(target_month="2026-04", household_key="demo")
    provider = StaticMonthlyReportProvider(
        "# 4月度 月次レポート\n\n担当CAとの打合せ内容をもとにしています。"
    )

    result = run_monthly_report_job(
        store,
        job.public_id,
        provider=provider,
        template_path=template,
    )

    assert result.status == JobStatus.FAILED
    assert result.current_stage == "validate"
    assert result.error_type == "validation_failed"
    validations = store.list_validations(job.public_id)
    assert [(v.rule_id, v.severity, v.message) for v in validations] == [
        ("forbidden_terms", "error", "draft contains forbidden terms: 担当CA")
    ]
    assert store.list_artifacts(job.public_id) == []


def test_run_monthly_report_job_records_provider_failure_without_persisting_artifact(
    tmp_path: Path,
):
    template = tmp_path / "template.md"
    template.write_text("PATTERN B CONTRACT", encoding="utf-8")
    store = MockJobStore(id_factory=_ids(["mrj_demo", "llm_demo"]))
    job = store.create_job(target_month="2026-04", household_key="demo")

    result = run_monthly_report_job(
        store,
        job.public_id,
        provider=FailingProvider(),
        template_path=template,
    )

    assert result.status == JobStatus.FAILED
    assert result.current_stage == "call_llm"
    assert result.error_type == "provider_call_failed"
    assert result.error_message == "OpenRouter call failed with status 502"
    llm_calls = store.list_llm_calls(job.public_id)
    assert len(llm_calls) == 1
    assert llm_calls[0].public_id == "llm_demo"
    assert llm_calls[0].prompt_kind == "report"
    assert llm_calls[0].error_type == "provider_call_failed"
    assert store.list_artifacts(job.public_id) == []


def test_openrouter_provider_posts_chat_completion_and_returns_resolved_model():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "model": "anthropic/claude-sonnet-4.6",
                "choices": [{"message": {"content": "# draft"}}],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenRouterMonthlyReportProvider(
        api_key="sk-test-secret",
        model="openrouter/auto",
        client=client,
        max_tokens=64,
    )

    completion = provider.complete(
        messages=[{"role": "user", "content": "hello"}],
    )

    assert completion.content == "# draft"
    assert completion.resolved_model == "anthropic/claude-sonnet-4.6"
    assert len(requests) == 1
    assert requests[0].url == "https://openrouter.ai/api/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer sk-test-secret"
    assert requests[0].read() == (
        b'{"model":"openrouter/auto","messages":[{"role":"user","content":"hello"}],'
        b'"temperature":0.1,"max_tokens":64}'
    )


def test_openrouter_provider_error_message_does_not_include_api_key():
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(502, text="bad"))
    )
    provider = OpenRouterMonthlyReportProvider(
        api_key="sk-test-secret",
        model="mock/model",
        client=client,
    )

    with pytest.raises(ProviderCallError) as exc_info:
        provider.complete(messages=[{"role": "user", "content": "hello"}])

    assert "502" in str(exc_info.value)
    assert "sk-test-secret" not in str(exc_info.value)


def test_openrouter_provider_connection_error_uses_unknown_status():
    def raise_connect_error(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("socket denied")

    client = httpx.Client(transport=httpx.MockTransport(raise_connect_error))
    provider = OpenRouterMonthlyReportProvider(
        api_key="sk-test-secret",
        model="mock/model",
        client=client,
    )

    with pytest.raises(ProviderCallError) as exc_info:
        provider.complete(messages=[{"role": "user", "content": "hello"}])

    assert str(exc_info.value) == "OpenRouter call failed with status unknown"
    assert "socket denied" not in str(exc_info.value)
    assert "sk-test-secret" not in str(exc_info.value)


def _ids(values: list[str]):
    iterator = iter(values)

    def next_id(_prefix: str) -> str:
        return next(iterator)

    return next_id


class FailingProvider:
    def complete(self, *, messages: list[dict[str, str]], model: str | None = None):
        raise ProviderCallError("OpenRouter call failed with status 502")
