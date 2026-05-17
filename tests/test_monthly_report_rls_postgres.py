from __future__ import annotations

import os
from uuid import uuid4

import pytest

psycopg = pytest.importorskip("psycopg")

from eb_app.monthly_reports.rls import connect_as_authenticated_user


DATABASE_URL = os.environ.get("EB_MONTHLY_REPORT_DATABASE_URL")


pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="EB_MONTHLY_REPORT_DATABASE_URL is not set",
)


def test_monthly_report_rls_filters_jobs_and_child_rows_by_authenticated_user():
    assert DATABASE_URL is not None
    user_a = str(uuid4())
    user_b = str(uuid4())

    with psycopg.connect(DATABASE_URL) as admin_conn:
        admin_conn.execute(
            """
            insert into public.monthly_report_jobs
                (public_id, created_by, target_month, household_key, status)
            values
                (%s, %s, '2026-04', 'rls_user_a', 'queued'),
                (%s, %s, '2026-04', 'rls_user_b', 'queued')
            """,
            ("mrj_rls_user_a", user_a, "mrj_rls_user_b", user_b),
        )
        admin_conn.execute(
            """
            insert into public.monthly_report_sources
                (public_id, job_id, source_type, display_name, snapshot_text)
            select 'mrs_rls_user_a', id, 'doc', 'user a source', 'user a text'
            from public.monthly_report_jobs
            where public_id = 'mrj_rls_user_a'
            union all
            select 'mrs_rls_user_b', id, 'doc', 'user b source', 'user b text'
            from public.monthly_report_jobs
            where public_id = 'mrj_rls_user_b'
            """
        )

    try:
        with connect_as_authenticated_user(DATABASE_URL, user_id=user_a) as user_conn:
            visible_jobs = user_conn.execute(
                "select public_id from public.monthly_report_jobs order by public_id"
            ).fetchall()
            visible_sources = user_conn.execute(
                "select public_id from public.monthly_report_sources order by public_id"
            ).fetchall()

        assert [row["public_id"] for row in visible_jobs] == ["mrj_rls_user_a"]
        assert [row["public_id"] for row in visible_sources] == ["mrs_rls_user_a"]
    finally:
        with psycopg.connect(DATABASE_URL) as admin_conn:
            admin_conn.execute(
                "delete from public.monthly_report_jobs where public_id in (%s, %s)",
                ("mrj_rls_user_a", "mrj_rls_user_b"),
            )


def test_monthly_report_rls_blocks_client_audit_log_access():
    assert DATABASE_URL is not None
    user_id = str(uuid4())

    with psycopg.connect(DATABASE_URL) as admin_conn:
        admin_conn.execute(
            """
            insert into public.audit_logs
                (public_id, actor_id, action, target_type, target_id)
            values (%s, %s, 'rls_probe', 'monthly_report_job', 'mrj_rls_probe')
            """,
            ("aud_rls_probe", user_id),
        )

    try:
        with connect_as_authenticated_user(DATABASE_URL, user_id=user_id) as user_conn:
            rows = user_conn.execute(
                "select public_id from public.audit_logs where public_id = 'aud_rls_probe'"
            ).fetchall()

        assert rows == []
    finally:
        with psycopg.connect(DATABASE_URL) as admin_conn:
            admin_conn.execute(
                "delete from public.audit_logs where public_id = 'aud_rls_probe'"
            )


def test_monthly_report_rls_allows_only_own_job_insert_for_authenticated_user():
    assert DATABASE_URL is not None
    user_id = str(uuid4())
    other_user_id = str(uuid4())

    try:
        with connect_as_authenticated_user(DATABASE_URL, user_id=user_id) as user_conn:
            own_row = user_conn.execute(
                """
                insert into public.monthly_report_jobs
                    (public_id, created_by, target_month, household_key, status)
                values (%s, %s, '2026-04', 'rls_own_insert', 'queued')
                returning public_id
                """,
                ("mrj_rls_own_insert", user_id),
            ).fetchone()
            assert own_row["public_id"] == "mrj_rls_own_insert"

            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                user_conn.execute(
                    """
                    insert into public.monthly_report_jobs
                        (public_id, created_by, target_month, household_key, status)
                    values (%s, %s, '2026-04', 'rls_spoof_insert', 'queued')
                    """,
                    ("mrj_rls_spoof_insert", other_user_id),
                )
    finally:
        with psycopg.connect(DATABASE_URL) as admin_conn:
            admin_conn.execute(
                "delete from public.monthly_report_jobs where public_id in (%s, %s)",
                ("mrj_rls_own_insert", "mrj_rls_spoof_insert"),
            )
