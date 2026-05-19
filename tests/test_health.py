from __future__ import annotations

from fastapi.testclient import TestClient

from eb_app.main import create_app


def test_healthz_is_public_minimal_and_cache_safe(monkeypatch):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret")
    monkeypatch.setenv("EB_MONTHLY_REPORT_DATABASE_URL", "postgresql://secret-host/db")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-secret")
    monkeypatch.setenv("EB_GOOGLE_WORKSPACE_ACCESS_TOKEN", "google-secret")

    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert "application/json" in response.headers["content-type"]
    assert "secret" not in response.text
    assert "postgresql://" not in response.text


def test_health_is_cloud_run_safe_alias(monkeypatch):
    monkeypatch.setenv("EB_AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret")

    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
