from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row


@contextmanager
def connect_as_authenticated_user(
    database_url: str,
    *,
    user_id: str,
) -> Iterator[psycopg.Connection[dict]]:
    """Open a Postgres session that evaluates Supabase RLS as one user."""
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        conn.execute("set local role authenticated")
        conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (user_id,))
        yield conn
