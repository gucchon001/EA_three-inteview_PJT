from __future__ import annotations

import pytest

from base_app.auth import assert_mock_auth_allowed
from base_app.config import Settings


@pytest.mark.parametrize("env_name", ["production", "prod", "prd"])
def test_mock_auth_is_blocked_in_production_like_env(env_name: str):
    settings = Settings(APP_ENV=env_name, APP_AUTH_MODE="mock")

    with pytest.raises(RuntimeError, match="Mock auth is not allowed"):
        assert_mock_auth_allowed(settings)


def test_mock_auth_is_allowed_locally():
    settings = Settings(APP_ENV="local", APP_AUTH_MODE="mock")

    assert_mock_auth_allowed(settings)

