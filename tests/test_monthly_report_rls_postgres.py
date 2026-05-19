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


def test_monthly_report_rls_allows_only_owner_feedback_insert():
    assert DATABASE_URL is not None
    user_a = str(uuid4())
    user_b = str(uuid4())
    suffix = uuid4().hex[:8]
    job_public_id = f"mrj_rls_feedback_{suffix}"
    owner_feedback_id = f"mrf_rls_owner_{suffix}"
    other_feedback_id = f"mrf_rls_other_{suffix}"

    with psycopg.connect(DATABASE_URL) as admin_conn:
        job_id = admin_conn.execute(
            """
            insert into public.monthly_report_jobs
                (public_id, created_by, target_month, household_key, status)
            values (%s, %s, '2026-04', 'rls_feedback', 'queued')
            returning id
            """,
            (job_public_id, user_a),
        ).fetchone()[0]

    try:
        with connect_as_authenticated_user(DATABASE_URL, user_id=user_a) as user_conn:
            inserted = user_conn.execute(
                """
                insert into public.monthly_report_feedback
                    (public_id, job_id, created_by, category, comment)
                values (%s, %s, %s, 'tone', 'owner feedback')
                returning public_id
                """,
                (owner_feedback_id, job_id, user_a),
            ).fetchone()
            assert inserted["public_id"] == owner_feedback_id

        with connect_as_authenticated_user(DATABASE_URL, user_id=user_b) as user_conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                user_conn.execute(
                    """
                    insert into public.monthly_report_feedback
                        (public_id, job_id, created_by, category, comment)
                    values (%s, %s, %s, 'tone', 'other feedback')
                    """,
                    (other_feedback_id, job_id, user_b),
                )
        with connect_as_authenticated_user(DATABASE_URL, user_id=user_b) as user_conn:
            visible_feedback = user_conn.execute(
                """
                select public_id
                from public.monthly_report_feedback
                where job_id = %s
                """,
                (job_id,),
            ).fetchall()
            assert visible_feedback == []
    finally:
        with psycopg.connect(DATABASE_URL) as admin_conn:
            admin_conn.execute(
                "delete from public.monthly_report_jobs where public_id = %s",
                (job_public_id,),
            )


@pytest.mark.parametrize(
    ("table_name", "public_id_prefix", "insert_sql", "insert_params_factory"),
    [
        (
            "monthly_report_sources",
            "mrs",
            """
            insert into public.monthly_report_sources
                (public_id, job_id, source_type, display_name, snapshot_text)
            values (%s, %s, 'doc', 'owner source', 'owner snapshot')
            returning public_id
            """,
            lambda public_id, job_id: (public_id, job_id),
        ),
        (
            "monthly_report_artifacts",
            "mra",
            """
            insert into public.monthly_report_artifacts
                (public_id, job_id, artifact_type, content)
            values (%s, %s, 'draft_markdown', '# owner artifact')
            returning public_id
            """,
            lambda public_id, job_id: (public_id, job_id),
        ),
    ],
)
def test_monthly_report_rls_allows_only_owner_source_and_artifact_insert(
    table_name: str,
    public_id_prefix: str,
    insert_sql: str,
    insert_params_factory,
):
    assert DATABASE_URL is not None
    user_a = str(uuid4())
    user_b = str(uuid4())
    suffix = uuid4().hex[:8]
    job_public_id = f"mrj_rls_{public_id_prefix}_{suffix}"
    owner_row_id = f"{public_id_prefix}_rls_owner_{suffix}"
    other_row_id = f"{public_id_prefix}_rls_other_{suffix}"

    with psycopg.connect(DATABASE_URL) as admin_conn:
        job_id = admin_conn.execute(
            """
            insert into public.monthly_report_jobs
                (public_id, created_by, target_month, household_key, status)
            values (%s, %s, '2026-04', 'rls_child_write', 'queued')
            returning id
            """,
            (job_public_id, user_a),
        ).fetchone()[0]

    try:
        with connect_as_authenticated_user(DATABASE_URL, user_id=user_a) as user_conn:
            inserted = user_conn.execute(
                insert_sql,
                insert_params_factory(owner_row_id, job_id),
            ).fetchone()
            assert inserted["public_id"] == owner_row_id

        with connect_as_authenticated_user(DATABASE_URL, user_id=user_b) as user_conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                user_conn.execute(
                    insert_sql,
                    insert_params_factory(other_row_id, job_id),
                )

        with connect_as_authenticated_user(DATABASE_URL, user_id=user_b) as user_conn:
            visible_rows = user_conn.execute(
                f"select public_id from public.{table_name} where job_id = %s",
                (job_id,),
            ).fetchall()
            assert visible_rows == []
    finally:
        with psycopg.connect(DATABASE_URL) as admin_conn:
            admin_conn.execute(
                "delete from public.monthly_report_jobs where public_id = %s",
                (job_public_id,),
            )


def test_monthly_report_rls_allows_only_owner_validation_insert():
    assert DATABASE_URL is not None
    user_a = str(uuid4())
    user_b = str(uuid4())
    suffix = uuid4().hex[:8]
    job_public_id = f"mrj_rls_validation_{suffix}"
    owner_validation_id = f"mrv_rls_owner_{suffix}"
    other_validation_id = f"mrv_rls_other_{suffix}"

    with psycopg.connect(DATABASE_URL) as admin_conn:
        job_id = admin_conn.execute(
            """
            insert into public.monthly_report_jobs
                (public_id, created_by, target_month, household_key, status)
            values (%s, %s, '2026-04', 'rls_validation', 'queued')
            returning id
            """,
            (job_public_id, user_a),
        ).fetchone()[0]

    try:
        with connect_as_authenticated_user(DATABASE_URL, user_id=user_a) as user_conn:
            inserted = user_conn.execute(
                """
                insert into public.monthly_report_validations
                    (public_id, job_id, rule_id, severity, message)
                values (%s, %s, 'required-heading', 'info', 'owner validation')
                returning public_id
                """,
                (owner_validation_id, job_id),
            ).fetchone()
            assert inserted["public_id"] == owner_validation_id

        with connect_as_authenticated_user(DATABASE_URL, user_id=user_b) as user_conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                user_conn.execute(
                    """
                    insert into public.monthly_report_validations
                        (public_id, job_id, rule_id, severity, message)
                    values (%s, %s, 'required-heading', 'info', 'other validation')
                    """,
                    (other_validation_id, job_id),
                )

        with connect_as_authenticated_user(DATABASE_URL, user_id=user_b) as user_conn:
            visible_validations = user_conn.execute(
                """
                select public_id
                from public.monthly_report_validations
                where job_id = %s
                """,
                (job_id,),
            ).fetchall()
            assert visible_validations == []
    finally:
        with psycopg.connect(DATABASE_URL) as admin_conn:
            admin_conn.execute(
                "delete from public.monthly_report_jobs where public_id = %s",
                (job_public_id,),
            )
