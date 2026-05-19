from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import os
import re
import socket
import threading
import time

import pytest

import eb_app.routers.monthly_reports as monthly_reports_router
from eb_app.main import create_app
from eb_app.monthly_reports.jobs import MockJobStore


def _assert_no_new_failed_responses(failed_responses: Sequence[str], before: int) -> None:
    assert list(failed_responses[before:]) == []


def _goto_detail_page(page, target_url: str) -> None:
    page.goto(target_url, wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_timeout(2_500)


def _open_details_summary(page, label: str) -> None:
    summary = page.locator("summary", has_text=label).first
    if summary.count() and summary.is_visible():
        if not summary.evaluate("el => el.parentElement && el.parentElement.open"):
            summary.click()


def _assert_detail_shell(page) -> None:
    assert page.locator("h1").first.inner_text().startswith("ジョブ詳細")
    assert page.locator(".htmx-busy-overlay").count() == 1
    assert page.get_by_label("レポート工房メニュー").count() == 1
    assert page.get_by_text("新規ジョブ登録").count() == 1
    assert page.locator(".side-nav a", has_text="データソース登録").count() == 1
    assert page.get_by_text("まず確認すること").count() == 1
    assert page.get_by_text("生成操作・進捗").count() == 1
    assert page.get_by_role("heading", name="データソース登録・確認").count() == 1
    assert page.get_by_role("heading", name="プレビュー / 編集").count() == 1
    assert page.get_by_role("heading", name="検証結果").count() == 1
    assert page.get_by_role("heading", name="承認・エクスポート").count() == 1
    assert page.get_by_text("チューニング用フィードバック").count() == 1
    assert page.get_by_text("再現性メタ").count() >= 1


def _assert_pipeline_controls(page) -> None:
    assert page.locator('button:has-text("生成開始")').count() == 1
    assert page.locator('button:has-text("モック生成")').count() == 1
    assert page.locator('button:has-text("OpenRouter生成")').count() == 1
    assert page.locator('button:has-text("再生成")').count() == 1

    if page.get_by_text("queued のジョブだけ生成開始できます").count():
        disabled_run_count = (
            page.locator('button:has-text("生成開始"):disabled').count()
            + page.locator('button:has-text("モック生成"):disabled').count()
            + page.locator('button:has-text("OpenRouter生成"):disabled').count()
        )
        assert disabled_run_count == 3


def _assert_source_controls(page) -> None:
    _open_details_summary(page, "Google Docs / Sheets を投入する")
    assert page.locator('textarea[name="snapshot_text"][required]').count() == 1
    assert page.locator('textarea[name="doc_ids"]').count() == 1
    assert page.locator('input[name="spreadsheet_id"]').count() == 1
    assert page.locator('button:has-text("シート名を確認")').count() == 1
    assert page.locator('button:has-text("Googleからソース取得")').count() == 1
    assert page.locator('button:has-text("取得内容を要約")').count() == 1

    if page.get_by_text("google_doc").count() or page.get_by_text("google_sheet").count():
        assert page.get_by_text("google_doc").count() >= 1
        assert page.get_by_text("google_sheet").count() >= 1


def _assert_preview_and_feedback_controls(page) -> None:
    assert page.locator('textarea[name="edited_markdown"][required]').count() == 1
    assert page.locator('input[name="base_content_hash"]').count() == 1
    assert page.locator('textarea[name="comment"][required]').count() == 1
    assert page.locator('input[name="category"]').count() == 1


def _assert_approval_export_controls(page) -> None:
    assert page.locator("#approval-panel").count() == 1
    assert page.locator("#export-panel").count() == 1


def _assert_sheet_selector_empty_submit_is_client_side_only(page, failed_responses: Sequence[str]) -> None:
    before = len(failed_responses)
    page.locator('button:has-text("シート名を確認")').click()
    page.wait_for_timeout(800)
    _assert_no_new_failed_responses(failed_responses, before)
    assert page.locator('button:has-text("シート名を確認"):not(:disabled)').count() == 1


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _local_monthly_report_server(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mock_user_email: str | None = None,
):
    uvicorn = pytest.importorskip("uvicorn")

    monkeypatch.setenv("EB_AUTH_MODE", "mock")
    if mock_user_email:
        monkeypatch.setenv("EB_MOCK_USER_EMAIL", mock_user_email)
    monkeypatch.delenv("EB_MONTHLY_REPORT_DATABASE_URL", raising=False)
    old_store = monthly_reports_router._store
    monthly_reports_router._store = MockJobStore()
    app = create_app()
    port = _free_tcp_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="off",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    try:
        while not server.started:
            if time.time() > deadline:
                pytest.skip("local FastAPI smoke server did not start")
            time.sleep(0.05)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        monthly_reports_router._store = old_store


def _install_local_htmx_route(page) -> None:
    page.route(
        "https://unpkg.com/htmx.org@2.0.4",
        lambda route: route.fulfill(
            status=200,
            content_type="application/javascript",
            body=r"""
(() => {
  async function requestInto(el, method, url, submitter) {
    const targetSelector = el.getAttribute("hx-target");
    const target = targetSelector ? document.querySelector(targetSelector) : el;
    const options = { method, headers: { "HX-Request": "true" }, credentials: "same-origin" };
    let body = null;
    let requestUrl = url;
    if (method === "POST") {
      let form = el.tagName === "FORM" ? el : el.closest("form");
      if (form) {
        body = new FormData(form);
        if (submitter && submitter.name) body.set(submitter.name, submitter.value || "");
        if (el.name) body.set(el.name, el.value || "");
      }
      options.body = body;
    } else if (method === "GET" && el.tagName === "FORM") {
      const formData = new FormData(el);
      const params = new URLSearchParams();
      for (const [key, value] of formData.entries()) params.set(key, value);
      const query = params.toString();
      if (query) requestUrl = url + (url.includes("?") ? "&" : "?") + query;
    }
    const response = await fetch(requestUrl, options);
    const html = await response.text();
    if (target && (el.getAttribute("hx-swap") || "innerHTML") === "innerHTML") {
      target.innerHTML = html;
      process(target);
    }
    if (response.ok && (el.getAttribute("hx-on::after-request") || "").includes("monthly-report-refresh")) {
      document.body.dispatchEvent(new Event("monthly-report-refresh"));
    }
  }
  function process(root) {
    root.querySelectorAll("[hx-get]").forEach((el) => {
      const trigger = el.getAttribute("hx-trigger") || "";
      if (!el.dataset.htmxLoaded && trigger.includes("load")) {
        el.dataset.htmxLoaded = "true";
        requestInto(el, "GET", el.getAttribute("hx-get"));
      }
      if (!el.dataset.htmxEvery && trigger.includes("every")) {
        el.dataset.htmxEvery = "true";
        window.setInterval(() => {
          if (document.activeElement && el.contains(document.activeElement)) return;
          requestInto(el, "GET", el.getAttribute("hx-get"));
        }, 500);
      }
      if (!el.dataset.htmxRefresh && trigger.includes("monthly-report-refresh")) {
        el.dataset.htmxRefresh = "true";
        document.body.addEventListener("monthly-report-refresh", () => {
          if (document.activeElement && el.contains(document.activeElement)) return;
          requestInto(el, "GET", el.getAttribute("hx-get"));
        });
      }
    });
    root.querySelectorAll("form[hx-post]").forEach((el) => {
      if (el.dataset.htmxBound) return;
      el.dataset.htmxBound = "true";
      el.addEventListener("submit", (event) => {
        event.preventDefault();
        requestInto(el, "POST", el.getAttribute("hx-post"), event.submitter);
      });
    });
    root.querySelectorAll("form[hx-get]").forEach((el) => {
      if (el.dataset.htmxBound) return;
      el.dataset.htmxBound = "true";
      el.addEventListener("submit", (event) => {
        event.preventDefault();
        requestInto(el, "GET", el.getAttribute("hx-get"), event.submitter);
      });
    });
    root.querySelectorAll("button[hx-post]").forEach((el) => {
      if (el.dataset.htmxBound) return;
      el.dataset.htmxBound = "true";
      el.addEventListener("click", (event) => {
        event.preventDefault();
        const input = el.form && el.form.elements["spreadsheet_id"];
        if (input && !input.value.trim()) {
          input.setCustomValidity("Google Sheets ID / URLを入力してください");
          input.reportValidity();
          setTimeout(() => input.setCustomValidity(""), 0);
          return;
        }
        requestInto(el, "POST", el.getAttribute("hx-post"));
      });
    });
  }
  window.htmx = { process };
  document.addEventListener("DOMContentLoaded", () => process(document));
})();
""",
        ),
    )


def _create_local_job(page, base_url: str) -> str:
    response = page.request.post(
        f"{base_url}/api/monthly-reports/jobs",
        data={
            "target_month": "2026-04",
            "household_key": "playwright-local-household",
            "owner_user_id": "playwright-local-owner",
        },
    )
    assert response.ok
    return response.json()["job_id"]


def _assert_no_json_dom_dependency(page) -> None:
    for selector in ("#sources-panel", "#preview-panel", "#approval-panel", "#export-panel"):
        assert page.locator(selector).count() == 1
        html = page.locator(selector).inner_html().lstrip()
        if html:
            assert html.startswith("<div")


def _env_multiline(name: str) -> str:
    return "\n".join(
        value.strip()
        for value in re.split(r"[\n,]+", os.environ.get(name, ""))
        if value.strip()
    )


def test_monthly_report_detail_local_playwright_smoke():
    if os.environ.get("MONTHLY_REPORT_PLAYWRIGHT_SMOKE") != "1":
        pytest.skip("set MONTHLY_REPORT_PLAYWRIGHT_SMOKE=1 to run local browser smoke")
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - exercised only without optional dep
        pytest.skip(f"playwright is not installed: {exc}")

    base_url = os.environ.get("MONTHLY_REPORT_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    job_id = os.environ.get("MONTHLY_REPORT_JOB_ID", "").strip()
    if not job_id:
        pytest.skip("set MONTHLY_REPORT_JOB_ID for the local detail page smoke")
    sheet_url = os.environ.get("MONTHLY_REPORT_SHEET_URL", "").strip()
    target_url = f"{base_url}/monthly-reports/jobs/{job_id}"
    failed_responses: list[str] = []
    console_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1365, "height": 900})
        page.on(
            "response",
            lambda response: failed_responses.append(f"{response.status} {response.url}")
            if response.status >= 400
            else None,
        )
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )

        _goto_detail_page(page, target_url)
        _assert_detail_shell(page)
        _assert_pipeline_controls(page)
        _assert_source_controls(page)
        _assert_preview_and_feedback_controls(page)
        _assert_approval_export_controls(page)
        _assert_sheet_selector_empty_submit_is_client_side_only(page, failed_responses)

        if sheet_url:
            page.locator('input[name="spreadsheet_id"]').fill(sheet_url)
            before = len(failed_responses)
            page.locator('button:has-text("シート名を確認")').click()
            try:
                page.wait_for_selector('select[name="student_sheet_name"]', timeout=15_000)
            except PlaywrightTimeoutError as exc:
                raise AssertionError("sheet selector did not render") from exc
            _assert_no_new_failed_responses(failed_responses, before)

        browser.close()

    assert failed_responses == []
    assert [
        error for error in console_errors if "409 (Conflict)" not in error
    ] == []


def test_monthly_report_detail_live_google_sources_optional_smoke():
    if os.environ.get("MONTHLY_REPORT_PLAYWRIGHT_SMOKE") != "1":
        pytest.skip("set MONTHLY_REPORT_PLAYWRIGHT_SMOKE=1 to run browser smoke")
    if os.environ.get("MONTHLY_REPORT_LIVE_GOOGLE_E2E") != "1":
        pytest.skip("set MONTHLY_REPORT_LIVE_GOOGLE_E2E=1 to fetch live Google sources")
    try:
        from playwright.sync_api import expect
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - exercised only without optional dep
        pytest.skip(f"playwright is not installed: {exc}")

    base_url = os.environ.get("MONTHLY_REPORT_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    job_id = os.environ.get("MONTHLY_REPORT_JOB_ID", "").strip()
    if not job_id:
        pytest.skip("set MONTHLY_REPORT_JOB_ID for the live Google sources smoke")
    doc_ids = _env_multiline("MONTHLY_REPORT_GOOGLE_DOC_IDS")
    sheet_url = os.environ.get("MONTHLY_REPORT_SHEET_URL", "").strip()
    if not doc_ids and not sheet_url:
        pytest.skip("set MONTHLY_REPORT_GOOGLE_DOC_IDS or MONTHLY_REPORT_SHEET_URL")
    run_source_summary = os.environ.get("MONTHLY_REPORT_LIVE_SOURCE_SUMMARY") == "1"

    failed_responses: list[str] = []
    console_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1365, "height": 900})
        page.on(
            "response",
            lambda response: failed_responses.append(f"{response.status} {response.url}")
            if response.status >= 400
            else None,
        )
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )

        _goto_detail_page(page, f"{base_url}/monthly-reports/jobs/{job_id}")
        _assert_detail_shell(page)
        _open_details_summary(page, "Google Docs / Sheets を投入する")
        if doc_ids:
            page.locator('textarea[name="doc_ids"]').fill(doc_ids)
        if sheet_url:
            page.locator('input[name="spreadsheet_id"]').fill(sheet_url)
        page.locator('#google-sources-form button:has-text("Googleからソース取得")').click()
        expect(page.locator("#sources-panel")).to_contain_text("google_", timeout=30_000)
        _assert_no_json_dom_dependency(page)

        if run_source_summary:
            page.locator('button:has-text("取得内容を要約")').click()
            expect(page.locator("#source-summary-panel")).to_contain_text("取得内容サマリー", timeout=60_000)
            expect(page.locator("#source-summary-panel")).to_contain_text("source_summary_markdown")

        browser.close()

    assert failed_responses == []
    assert [
        error for error in console_errors if "409 (Conflict)" not in error
    ] == []


def test_monthly_report_detail_manual_source_to_export_local_ui_flow(monkeypatch: pytest.MonkeyPatch):
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import expect
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - exercised only without optional dep
        pytest.skip(f"playwright is not installed: {exc}")

    failed_responses: list[str] = []
    console_errors: list[str] = []

    with _local_monthly_report_server(monkeypatch) as base_url:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"playwright chromium is not available: {exc}")
            page = browser.new_page(viewport={"width": 1365, "height": 900})
            _install_local_htmx_route(page)
            page.on(
                "response",
                lambda response: failed_responses.append(f"{response.status} {response.url}")
                if response.status >= 400
                else None,
            )
            page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error"
                else None,
            )

            job_id = _create_local_job(page, base_url)
            _goto_detail_page(page, f"{base_url}/monthly-reports/jobs/{job_id}")
            _assert_detail_shell(page)

            expect(page.locator("#sources-panel")).to_contain_text("保存済みソースはまだありません")
            _open_details_summary(page, "手入力でソースを保存する")
            page.locator('input[name="display_name"]').fill("Playwright面談メモ")
            page.locator('textarea[name="snapshot_text"]').fill(
                "4月は既習範囲の確認を進めました。宿題への取り組みも安定しています。"
            )
            page.locator('button:has-text("手入力ソースを保存")').click()
            expect(page.locator("#sources-panel")).to_contain_text("Playwright面談メモ")
            expect(page.locator("#sources-panel")).to_contain_text("宿題への取り組み")

            page.locator('button:has-text("モック生成")').click()
            expect(page.locator("#status-panel")).to_contain_text("status: succeeded")
            expect(page.locator("#preview-panel")).to_contain_text("draft_markdown")

            final_markdown = "\n\n".join(
                [
                    "## 01 基本情報\n- 対象月: 2026-04",
                    "## 02 塾での様子\n集中して取り組めています。",
                    "## 05 学習の進捗\n基礎の定着が見られます。",
                ]
            )
            page.locator('textarea[name="edited_markdown"]').fill(final_markdown)
            expect(page.get_by_text("未保存の変更")).to_be_visible()
            page.locator('button:has-text("生成Markdownを保存")').click()
            expect(page.locator("#preview-panel")).to_contain_text("final_markdown")
            expect(page.locator("#preview-panel")).to_contain_text("基礎の定着が見られます")
            expect(page.locator("#diff-panel")).to_contain_text("final ")

            expect(page.locator("#approval-panel")).to_contain_text("送付前チェックは通過しています")
            expect(page.locator("#approval-panel")).to_contain_text("final_markdown")
            page.locator('input[name="confirm_ready"]').check()
            page.locator('textarea[name="approval_comment"]').fill("Playwright smoke approval")
            page.locator('button:has-text("承認する")').click()
            expect(page.locator("#approval-panel")).to_contain_text("送付前承認を保存しました")
            expect(page.locator("#export-panel")).to_contain_text(
                "承認済みartifactからHTMLエクスポートを作成できます"
            )

            page.locator('button:has-text("HTMLエクスポート作成")').click()
            expect(page.locator("#export-panel")).to_contain_text("export_html")
            expect(page.locator("#distribution-panel")).to_contain_text("承認済みHTMLを手動送付用に固定できます")

            page.reload(wait_until="domcontentloaded")
            _assert_detail_shell(page)
            expect(page.locator("#status-panel")).to_contain_text("status: succeeded")
            expect(page.locator("#preview-panel")).to_contain_text("final_markdown")
            expect(page.locator('textarea[name="edited_markdown"]')).to_have_value(final_markdown)
            expect(page.locator("#approval-panel")).to_contain_text("承認済み")
            expect(page.locator("#export-panel")).to_contain_text("export_html")
            expect(page.locator("#distribution-panel")).to_contain_text("承認済みHTMLを手動送付用に固定できます")

            _open_details_summary(page, "HTMLソース・送付用パッケージを確認する")
            page.locator('button:has-text("送付用に固定")').click()
            expect(page.locator("#distribution-panel")).to_contain_text("ready_for_manual_distribution")

            compare_job_response = page.request.post(
                f"{base_url}/api/monthly-reports/jobs",
                data={
                    "target_month": "2026-04",
                    "household_key": "playwright-local-household",
                    "owner_user_id": "playwright-local-owner",
                    "prompt_version": "monthly-report-v20260517.playwright-compare",
                    "model_report": "mock/playwright-compare-model",
                },
            )
            assert compare_job_response.ok
            compare_job_id = compare_job_response.json()["job_id"]
            compare_artifact_response = page.request.post(
                f"{base_url}/api/monthly-reports/jobs/{compare_job_id}/artifacts",
                data={
                    "artifact_type": "draft_markdown",
                    "content": "## 01 基本情報\n- 対象月: 2026-04\n\n## 02 塾での様子\n比較ジョブの本文です。",
                    "content_hash": "sha256:playwright-compare-draft",
                },
                headers={"Idempotency-Key": "playwright-compare-artifact"},
            )
            assert compare_artifact_response.ok
            _open_details_summary(page, "差分・再生成比較を確認する")
            page.locator('#rerun-comparison-panel input[name="compare_job_id"]').fill(compare_job_id)
            page.locator('#rerun-comparison-panel button:has-text("比較")').click()
            expect(page.locator("#rerun-comparison-panel")).to_contain_text("monthly-report-v20260517.playwright-compare")
            expect(page.locator("#rerun-comparison-panel")).to_contain_text("changed")
            page.locator('#rerun-diff-panel input[name="compare_job_id"]').fill(compare_job_id)
            page.locator('#rerun-diff-panel button:has-text("本文差分")').click()
            expect(page.locator("#rerun-diff-panel")).to_contain_text("再生成本文差分")
            expect(page.locator("#rerun-diff-panel")).to_contain_text("比較ジョブの本文です")
            expect(page.locator("#rerun-diff-panel")).to_contain_text("sha256:playwright-compare-draft")
            _assert_no_json_dom_dependency(page)
            browser.close()

    assert failed_responses == []
    assert [
        error for error in console_errors if "409 (Conflict)" not in error
    ] == []


def test_monthly_report_detail_rejects_stale_multi_tab_edit_local_ui_flow(monkeypatch: pytest.MonkeyPatch):
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import expect
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - exercised only without optional dep
        pytest.skip(f"playwright is not installed: {exc}")

    failed_responses: list[str] = []
    console_errors: list[str] = []

    with _local_monthly_report_server(monkeypatch) as base_url:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"playwright chromium is not available: {exc}")
            page_a = browser.new_page(viewport={"width": 1365, "height": 900})
            page_b = browser.new_page(viewport={"width": 1365, "height": 900})
            _install_local_htmx_route(page_a)
            _install_local_htmx_route(page_b)
            for page in (page_a, page_b):
                page.on(
                    "response",
                    lambda response: failed_responses.append(f"{response.status} {response.url}")
                    if response.status >= 400
                    else None,
                )
                page.on(
                    "console",
                    lambda message: console_errors.append(message.text)
                    if message.type == "error"
                    else None,
                )

            job_id = _create_local_job(page_a, base_url)
            target_url = f"{base_url}/monthly-reports/jobs/{job_id}"
            _goto_detail_page(page_a, target_url)
            _open_details_summary(page_a, "手入力でソースを保存する")
            page_a.locator('input[name="display_name"]').fill("Playwright multi-tab source")
            page_a.locator('textarea[name="snapshot_text"]').fill("複数タブ編集の競合確認用ソースです。")
            page_a.locator('button:has-text("手入力ソースを保存")').click()
            expect(page_a.locator("#sources-panel")).to_contain_text("Playwright multi-tab source")
            page_a.locator('button:has-text("モック生成")').click()
            expect(page_a.locator("#preview-panel")).to_contain_text("draft_markdown")

            _goto_detail_page(page_a, target_url)
            _goto_detail_page(page_b, target_url)
            expect(page_a.locator('input[name="base_content_hash"]')).not_to_have_value("")
            expect(page_b.locator('input[name="base_content_hash"]')).to_have_value(
                page_a.locator('input[name="base_content_hash"]').input_value()
            )

            page_a.locator('textarea[name="edited_markdown"]').fill("## 01 基本情報\nAタブの保存")
            page_a.locator('button:has-text("生成Markdownを保存")').click()
            expect(page_a.locator("#preview-panel")).to_contain_text("final_markdown")

            page_b.locator('textarea[name="edited_markdown"]').fill("## 01 基本情報\nBタブの古い保存")
            page_b.locator('button:has-text("生成Markdownを保存")').click()
            expect(page_b.locator("#preview-panel")).to_contain_text("Aタブの保存")
            expect(page_b.locator("#preview-panel")).not_to_contain_text("Bタブの古い保存")
            browser.close()

    assert [
        error for error in console_errors if "409 (Conflict)" not in error
    ] == []
    conflict_responses = [
        response for response in failed_responses if "409 " in response and "/fragments/edited-markdown" in response
    ]
    assert len(conflict_responses) == 1
    assert len(failed_responses) == 1


def test_monthly_report_detail_shows_running_recovery_guidance_local_ui_flow(
    monkeypatch: pytest.MonkeyPatch,
):
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import expect
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - exercised only without optional dep
        pytest.skip(f"playwright is not installed: {exc}")

    failed_responses: list[str] = []
    console_errors: list[str] = []

    with _local_monthly_report_server(monkeypatch) as base_url:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"playwright chromium is not available: {exc}")
            page = browser.new_page(viewport={"width": 1365, "height": 900})
            _install_local_htmx_route(page)
            page.on(
                "response",
                lambda response: failed_responses.append(f"{response.status} {response.url}")
                if response.status >= 400
                else None,
            )
            page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error"
                else None,
            )

            job_id = _create_local_job(page, base_url)
            job = monthly_reports_router._store.claim_next_runnable_job(
                owner_user_id="playwright-local-owner"
            )
            assert job is not None

            _goto_detail_page(page, f"{base_url}/monthly-reports/jobs/{job_id}")
            expect(page.locator("#status-panel")).to_contain_text("処理中です")
            expect(page.locator("#status-panel")).to_contain_text("ページを閉じても処理は継続します")

            job.current_stage = "call_llm"
            job.worker_last_claimed_at = datetime.now(timezone.utc) - timedelta(minutes=31)
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(1_500)
            expect(page.locator("#status-panel")).to_contain_text("長時間更新がありません")
            expect(page.locator("#status-panel")).to_contain_text("worker runbook")
            browser.close()

    assert failed_responses == []
    assert [
        error for error in console_errors if "409 (Conflict)" not in error
    ] == []


def test_monthly_report_detail_shows_admin_tuning_only_for_admin_local_ui_flow(
    monkeypatch: pytest.MonkeyPatch,
):
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import expect
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - exercised only without optional dep
        pytest.skip(f"playwright is not installed: {exc}")

    failed_responses: list[str] = []
    console_errors: list[str] = []

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError as exc:
            pytest.skip(f"playwright chromium is not available: {exc}")

        with _local_monthly_report_server(
            monkeypatch,
            mock_user_email="mock-admin@tomonokai-corp.com",
        ) as admin_base_url:
            admin_page = browser.new_page(viewport={"width": 1365, "height": 900})
            _install_local_htmx_route(admin_page)
            admin_page.on(
                "response",
                lambda response: failed_responses.append(f"{response.status} {response.url}")
                if response.status >= 400
                else None,
            )
            admin_page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error"
                else None,
            )

            admin_page.goto(
                f"{admin_base_url}/monthly-reports/jobs/new",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            expect(admin_page.get_by_text("管理者チューニング")).to_be_visible()
            expect(admin_page.locator('input[name="prompt_version"]')).to_be_visible()
            expect(admin_page.locator('input[name="model_report"]')).to_be_visible()
            expect(admin_page.locator('input[name="model_light"]')).to_be_visible()

            admin_job_id = _create_local_job(admin_page, admin_base_url)
            _goto_detail_page(admin_page, f"{admin_base_url}/monthly-reports/jobs/{admin_job_id}")
            expect(admin_page.get_by_text("再生成チューニング")).to_be_visible()
            expect(admin_page.locator('input[name="rerun_prompt_version"]')).to_be_visible()
            expect(admin_page.locator('input[name="rerun_model_report"]')).to_be_visible()
            expect(admin_page.locator('input[name="rerun_model_light"]')).to_be_visible()
            admin_page.close()

        with _local_monthly_report_server(
            monkeypatch,
            mock_user_email="mock-user@tomonokai-corp.com",
        ) as user_base_url:
            user_page = browser.new_page(viewport={"width": 1365, "height": 900})
            _install_local_htmx_route(user_page)
            user_page.on(
                "response",
                lambda response: failed_responses.append(f"{response.status} {response.url}")
                if response.status >= 400
                else None,
            )
            user_page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error"
                else None,
            )

            user_page.goto(
                f"{user_base_url}/monthly-reports/jobs/new",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            expect(user_page.get_by_text("新規読み込みの流れ")).to_be_visible()
            expect(user_page.get_by_text("管理者チューニング")).to_have_count(0)
            expect(user_page.locator('input[name="prompt_version"]')).to_have_count(0)
            expect(user_page.locator('input[name="model_report"]')).to_have_count(0)
            expect(user_page.locator('input[name="model_light"]')).to_have_count(0)

            user_job_id = _create_local_job(user_page, user_base_url)
            _goto_detail_page(user_page, f"{user_base_url}/monthly-reports/jobs/{user_job_id}")
            expect(user_page.get_by_text("再生成チューニング")).to_have_count(0)
            expect(user_page.locator('input[name="rerun_prompt_version"]')).to_have_count(0)
            expect(user_page.locator('input[name="rerun_model_report"]')).to_have_count(0)
            expect(user_page.locator('input[name="rerun_model_light"]')).to_have_count(0)
            user_page.close()

        browser.close()

    assert failed_responses == []
    assert [
        error for error in console_errors if "409 (Conflict)" not in error
    ] == []


def test_monthly_report_detail_continuous_ui_review_local_flow(
    monkeypatch: pytest.MonkeyPatch,
):
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import expect
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - exercised only without optional dep
        pytest.skip(f"playwright is not installed: {exc}")

    failed_responses: list[str] = []
    console_errors: list[str] = []

    with _local_monthly_report_server(monkeypatch) as base_url:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"playwright chromium is not available: {exc}")
            page = browser.new_page(viewport={"width": 1365, "height": 900})
            _install_local_htmx_route(page)
            page.on(
                "response",
                lambda response: failed_responses.append(f"{response.status} {response.url}")
                if response.status >= 400
                else None,
            )
            page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error"
                else None,
            )

            job_id = _create_local_job(page, base_url)
            _goto_detail_page(page, f"{base_url}/monthly-reports/jobs/{job_id}")
            _assert_detail_shell(page)

            expect(page.locator(".workflow-board")).to_be_visible()
            expect(page.locator(".summary .summary-item")).to_have_count(6)
            expect(page.locator(".quick-nav a")).to_have_count(7)
            expect(page.locator("#operation-log-panel")).to_contain_text("ジョブ作成")
            expect(page.locator("#sources-panel")).to_contain_text("保存済みソースはまだありません")
            expect(page.locator("#preview-panel")).to_contain_text("まだレポートビューに表示できる生成物はありません")
            expect(page.locator("#validation-panel")).to_contain_text("検証結果はまだありません")
            expect(page.locator("#approval-panel")).to_contain_text("承認状態")
            expect(page.locator("#export-panel")).to_contain_text("HTML export")

            for anchor, heading in [
                ("#sources-panel", "データソース登録・確認"),
                ("#preview-section", "プレビュー / 編集"),
                ("#validation-section", "検証結果"),
                ("#approval-panel", "承認・エクスポート"),
            ]:
                page.locator(f'.quick-nav a[href="{anchor}"]').click()
                page.wait_for_timeout(300)
                expect(page.get_by_role("heading", name=heading)).to_be_visible()

            _open_details_summary(page, "Google Docs / Sheets を投入する")
            expect(page.locator("#google-sources-form")).to_be_visible()
            _open_details_summary(page, "手入力でソースを保存する")
            expect(page.locator('textarea[name="snapshot_text"]')).to_be_visible()
            _open_details_summary(page, "差分・再生成比較を確認する")
            expect(page.locator("#diff-panel")).to_be_visible()
            expect(page.locator("#rerun-comparison-panel")).to_be_visible()
            expect(page.locator("#rerun-diff-panel")).to_be_visible()
            _open_details_summary(page, "HTMLソース・送付用パッケージを確認する")
            expect(page.locator("#html-source-panel")).to_be_visible()
            expect(page.locator("#distribution-panel")).to_be_visible()

            page.reload(wait_until="domcontentloaded")
            _assert_detail_shell(page)
            expect(page.locator(".workflow-board")).to_be_visible()
            expect(page.locator("#operation-log-panel")).to_contain_text("ジョブ作成")
            expect(page.locator("#approval-panel")).to_contain_text("承認状態")
            _assert_no_json_dom_dependency(page)
            browser.close()

    assert failed_responses == []
    assert [
        error for error in console_errors if "409 (Conflict)" not in error
    ] == []
