from __future__ import annotations

from fastapi.testclient import TestClient

from base_app.config import clear_settings_cache
from base_app.main import create_app


def test_home_page_renders_with_mock_user(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_AUTH_MODE", "mock")
    monkeypatch.setenv("APP_ALLOWED_EMAIL_DOMAIN", "example.com")
    clear_settings_cache()

    client = TestClient(create_app())
    response = client.get("/")

    assert response.status_code == 200
    assert "local-user@example.com" in response.text
    assert "Refresh summary" in response.text


def test_summary_fragment_renders_with_mock_user(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_AUTH_MODE", "mock")
    clear_settings_cache()

    client = TestClient(create_app())
    response = client.get("/fragments/summary")

    assert response.status_code == 200
    assert "HTMX fragment rendered" in response.text


def test_page_requires_auth_when_not_mock(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_AUTH_MODE", "supabase")
    clear_settings_cache()

    client = TestClient(create_app())
    response = client.get("/")

    assert response.status_code == 401

