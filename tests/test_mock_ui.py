from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from eb_app.fixtures.mock_screens import MOCK_INDEX


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
