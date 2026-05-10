from __future__ import annotations

import os
from dataclasses import dataclass


def _truthy(raw: str | None) -> bool:
    if raw is None or raw.strip() == "":
        return False
    return raw.strip().lower() in frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True)
class Settings:
    """環境変数から読む実行時設定（import 時ではなく create_app ごとに読み直す）。"""

    enable_mock_ui: bool

    @classmethod
    def from_env(cls) -> Settings:
        return cls(enable_mock_ui=_truthy(os.environ.get("EB_ENABLE_MOCK_UI")))


def get_settings() -> Settings:
    return Settings.from_env()
