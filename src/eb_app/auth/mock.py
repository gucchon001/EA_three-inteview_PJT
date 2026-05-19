from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

MockUser = Mapping[str, str]

_MOCK_USERS: tuple[dict[str, str], ...] = (
    {
        "email": "mock-admin@tomonokai-corp.com",
        "role": "admin",
    },
    {
        "email": "mock-user@tomonokai-corp.com",
        "role": "user",
    },
    {
        "email": "y-haraguchi@tomonokai-corp.com",
        "role": "admin",
    },
)

_MOCK_USERS_BY_EMAIL: Mapping[str, MockUser] = MappingProxyType(
    {user["email"]: MappingProxyType(user) for user in _MOCK_USERS}
)


def list_mock_users() -> tuple[MockUser, ...]:
    return tuple(_MOCK_USERS_BY_EMAIL[user["email"]] for user in _MOCK_USERS)


def get_mock_user(email: str) -> MockUser:
    return _MOCK_USERS_BY_EMAIL[email.strip().lower()]
