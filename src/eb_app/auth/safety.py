from __future__ import annotations

from eb_app.config import Settings

_PRODUCTION_ENVS = frozenset({"production", "prod", "prd"})


def assert_mock_auth_allowed(settings: Settings) -> None:
    if settings.auth_mode != "mock":
        return
    if settings.env in _PRODUCTION_ENVS:
        raise RuntimeError("Mock auth is not allowed when EB_ENV is production-like.")
