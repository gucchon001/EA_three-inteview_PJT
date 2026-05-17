from __future__ import annotations

from fastapi.testclient import TestClient

from base_app.config import clear_settings_cache
from base_app.main import create_app


def test_healthz(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_AUTH_MODE", "mock")
    clear_settings_cache()

    client = TestClient(create_app())
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["env"] == "test"

