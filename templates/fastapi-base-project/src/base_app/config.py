from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="FastAPI Base", alias="APP_NAME")
    app_version: str = Field(default="local", alias="APP_VERSION")
    env: str = Field(default="local", alias="APP_ENV")
    auth_mode: str = Field(default="mock", alias="APP_AUTH_MODE")
    allowed_email_domain: str = Field(default="example.com", alias="APP_ALLOWED_EMAIL_DOMAIN")

    @property
    def is_production_like(self) -> bool:
        return self.env.strip().lower() in {"production", "prod", "prd"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()

