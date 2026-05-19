from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from eb_app.fixtures.mock_screens import MOCK_INDEX


MONTHLY_REPORT_STANDALONE_NAV = [
    "月次レポートMVP",
    "レポートビュー",
    "新規読み込み",
    "ジョブ一覧",
    "生成ステータス",
    "検証結果",
    "ソース確認",
    "成果物保存",
    "簡易差分",
    "HTMLエクスポート",
    "送付エクスポート",
    "チューニング",
]


def assert_monthly_report_standalone_shell(html: str) -> None:
    assert "EB 指導管理" not in html
    for label in MONTHLY_REPORT_STANDALONE_NAV:
        assert label in html


def test_mock_disabled_returns_404_for_mock_paths():
    os.environ.pop("EB_ENABLE_MOCK_UI", None)
    from eb_app.main import create_app

    app = create_app()
    client = TestClient(app)
    r = client.get("/mock/")
    assert r.status_code == 404


def test_mock_enabled_serves_index_dashboard_and_fragment():
    os.environ["EB_ENABLE_MOCK_UI"] = "1"
    from eb_app.main import create_app

    app = create_app()
    client = TestClient(app)
    idx = client.get("/mock/")
    assert idx.status_code == 200
    assert "モック索引" in idx.text

    dash = client.get("/mock/dashboard/admin")
    assert dash.status_code == 200
    assert "管理者" in dash.text

    frag = client.get("/mock/fragments/admin-alerts")
    assert frag.status_code == 200
    assert "充足率" in frag.text


def test_mock_enabled_serves_monthly_report_workshop_flow():
    os.environ["EB_ENABLE_MOCK_UI"] = "1"
    from eb_app.main import create_app

    app = create_app()
    client = TestClient(app)

    home = client.get("/mock/monthly-report-workshop")
    assert home.status_code == 200
    assert "月次レポート生成ツール" in home.text
    assert "単体MVP" in home.text
    assert "静的モック画面です" in home.text
    assert "/monthly-reports/jobs" in home.text
    assert "実装本体を開く" in home.text
    assert "/mock/monthly-report-workshop/jobs/new" in home.text
    assert "/mock/monthly-report-workshop/jobs" in home.text
    assert_monthly_report_standalone_shell(home.text)

    jobs = client.get("/mock/monthly-report-workshop/jobs")
    assert jobs.status_code == 200
    assert "レポート工房" in jobs.text
    assert "実装本体で新規読み込み" in jobs.text
    assert "mrj_demo_001" in jobs.text
    assert "高藤 泰次郎" in jobs.text
    assert "鈴木 謙吾" in jobs.text
    assert "十倉 未希" in jobs.text
    assert_monthly_report_standalone_shell(jobs.text)

    new_job = client.get("/mock/monthly-report-workshop/jobs/new")
    assert new_job.status_code == 200
    assert "ソース指定" in new_job.text
    assert "Spreadsheet URL" in new_job.text
    assert "Google取得やOpenRouter生成は実行しません" in new_job.text
    assert "/monthly-reports/jobs/new" in new_job.text
    assert_monthly_report_standalone_shell(new_job.text)

    detail = client.get("/mock/monthly-report-workshop/jobs/mrj_demo_001")
    assert detail.status_code == 200
    assert "生成パイプライン" in detail.text
    assert "prompt_version" in detail.text
    assert_monthly_report_standalone_shell(detail.text)

    editor = client.get("/mock/monthly-report-workshop/jobs/mrj_demo_001/edit")
    assert editor.status_code == 200
    assert "HTML全文エディタ" in editor.text
    assert "サンプルレポートを読み込めませんでした" not in editor.text
    assert "LLM本文生成を実行中" in editor.text
    assert_monthly_report_standalone_shell(editor.text)
    assert "編集枠直上は" in editor.text
    assert "frame-wrap" in editor.text
    assert "editor-frame-toolbar" in editor.text
    assert "report-canvas .page" in editor.text
    assert "report-canvas .page-header" in editor.text
    assert "report-canvas .title-block" in editor.text
    assert "section-heading" in editor.text
    assert "pw-out-box" in editor.text
    assert "送付エクスポート" in editor.text
    assert "id=\"validation-panel\"" in editor.text
    assert "id=\"source-panel\"" in editor.text
    assert "id=\"artifact-panel\"" in editor.text
    assert "id=\"diff-panel\"" in editor.text
    assert "id=\"tuning-panel\"" in editor.text
    assert "検証結果" in editor.text
    assert "ソース確認" in editor.text
    assert "成果物保存" in editor.text
    assert "簡易差分" in editor.text
    assert "チューニング" in editor.text
    assert "app_version" in editor.text

    status_fragment = client.get(
        "/mock/monthly-report-workshop/jobs/mrj_demo_001/fragments/status"
    )
    assert status_fragment.status_code == 200
    assert "running" in status_fragment.text


@pytest.mark.parametrize(
    ("job_id", "household"),
    [
        ("mrj_demo_001", "高藤 泰次郎"),
        ("mrj_demo_suzuki", "鈴木 謙吾"),
        ("mrj_demo_tokura", "十倉 未希"),
    ],
)
def test_mock_monthly_report_workshop_demo_job_routes(job_id: str, household: str):
    os.environ["EB_ENABLE_MOCK_UI"] = "1"
    from eb_app.main import create_app

    app = create_app()
    client = TestClient(app)

    detail = client.get(f"/mock/monthly-report-workshop/jobs/{job_id}")
    assert detail.status_code == 200
    assert household in detail.text
    assert job_id in detail.text

    editor = client.get(f"/mock/monthly-report-workshop/jobs/{job_id}/edit")
    assert editor.status_code == 200
    assert household in editor.text
    assert "HTML全文エディタ" in editor.text
    assert "サンプルレポートを読み込めませんでした" not in editor.text


@pytest.mark.parametrize(
    "path",
    [m.path for m in MOCK_INDEX],
)
def test_mock_enabled_all_catalog_paths_ok(path: str):
    os.environ["EB_ENABLE_MOCK_UI"] = "1"
    from eb_app.main import create_app

    app = create_app()
    client = TestClient(app)
    r = client.get(path)
    assert r.status_code == 200, path
