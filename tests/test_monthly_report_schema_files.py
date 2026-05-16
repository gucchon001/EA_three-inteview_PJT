from pathlib import Path


MIGRATION = Path("supabase/migrations/202605130001_initial_monthly_report_workshop.sql")
MIGRATIONS_DIR = Path("supabase/migrations")


def test_initial_monthly_report_migration_exists():
    assert MIGRATION.exists()


def test_initial_monthly_report_migration_defines_core_tables_and_columns():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    for table in [
        "monthly_report_jobs",
        "monthly_report_sources",
        "monthly_report_artifacts",
        "monthly_report_validations",
        "monthly_report_feedback",
        "llm_call_logs",
        "google_oauth_credentials",
        "audit_logs",
    ]:
        assert f"create table public.{table}" in sql

    for column in [
        "id uuid primary key",
        "public_id text not null unique",
        "storage_path text",
        "retention_until timestamptz",
        "deleted_at timestamptz",
        "created_at timestamptz not null default now()",
        "encrypted_provider_refresh_token text not null",
        "metadata jsonb not null default '{}'::jsonb",
    ]:
        assert column in sql

    assert "job_id uuid not null references public.monthly_report_jobs(id)" in sql
    assert "unique (user_id, provider)" in sql


def test_monthly_report_jobs_has_explicit_failure_columns():
    sql = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in sorted(MIGRATIONS_DIR.glob("*.sql"))
    )

    assert "monthly_report_jobs" in sql
    assert "error_type text" in sql
    assert "error_message text" in sql


def test_monthly_report_jobs_has_prompt_scope_notes_column():
    sql = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in sorted(MIGRATIONS_DIR.glob("*.sql"))
    )

    assert "monthly_report_jobs" in sql
    assert "prompt_scope_notes text" in sql


def test_monthly_report_tables_enable_rls_and_owner_policies():
    sql = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in sorted(MIGRATIONS_DIR.glob("*.sql"))
    )

    for table in [
        "monthly_report_jobs",
        "monthly_report_sources",
        "monthly_report_artifacts",
        "monthly_report_validations",
        "monthly_report_feedback",
        "llm_call_logs",
        "google_oauth_credentials",
        "audit_logs",
    ]:
        assert f"alter table public.{table} enable row level security" in sql

    assert "create policy monthly_report_jobs_owner_select" in sql
    assert "created_by = auth.uid()::text" in sql
    assert "public.monthly_report_jobs j" in sql
    assert "j.created_by = auth.uid()::text" in sql
    assert "create policy google_oauth_credentials_owner_all" in sql
    assert "user_id = auth.uid()" in sql
    assert "create policy audit_logs_no_client_access" in sql
