create extension if not exists pgcrypto with schema extensions;

create table public.monthly_report_jobs (
    id uuid primary key default gen_random_uuid(),
    public_id text not null unique,
    created_by text not null,
    target_month text not null,
    household_key text not null,
    status text not null default 'queued',
    current_stage text,
    prompt_version text,
    template_key text,
    template_hash text,
    model_report text,
    model_light text,
    resolved_model_report text,
    source_bundle_hash text,
    app_version text,
    retention_until timestamptz,
    deleted_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.monthly_report_sources (
    id uuid primary key default gen_random_uuid(),
    public_id text not null unique,
    job_id uuid not null references public.monthly_report_jobs(id) on delete cascade,
    source_type text not null,
    external_id text,
    url text,
    display_name text,
    snapshot_text text,
    snapshot_json jsonb,
    storage_path text,
    content_hash text,
    size_bytes integer,
    truncated boolean not null default false,
    fetch_status text not null default 'succeeded',
    error_type text,
    retention_until timestamptz,
    deleted_at timestamptz,
    fetched_at timestamptz,
    created_at timestamptz not null default now()
);

create table public.monthly_report_artifacts (
    id uuid primary key default gen_random_uuid(),
    public_id text not null unique,
    job_id uuid not null references public.monthly_report_jobs(id) on delete cascade,
    artifact_type text not null,
    content text,
    content_hash text,
    storage_path text,
    retention_until timestamptz,
    deleted_at timestamptz,
    created_at timestamptz not null default now()
);

create table public.monthly_report_validations (
    id uuid primary key default gen_random_uuid(),
    public_id text not null unique,
    job_id uuid not null references public.monthly_report_jobs(id) on delete cascade,
    artifact_id uuid references public.monthly_report_artifacts(id) on delete set null,
    rule_id text not null,
    severity text not null,
    message text not null,
    path text,
    details jsonb,
    created_at timestamptz not null default now()
);

create table public.monthly_report_feedback (
    id uuid primary key default gen_random_uuid(),
    public_id text not null unique,
    job_id uuid not null references public.monthly_report_jobs(id) on delete cascade,
    created_by text not null,
    category text,
    comment text,
    final_artifact_id uuid references public.monthly_report_artifacts(id) on delete set null,
    created_at timestamptz not null default now()
);

create table public.llm_call_logs (
    id uuid primary key default gen_random_uuid(),
    public_id text not null unique,
    job_id uuid references public.monthly_report_jobs(id) on delete set null,
    prompt_kind text not null,
    provider text not null default 'openrouter',
    requested_model text,
    resolved_model text,
    prompt_version text,
    request_hash text,
    response_hash text,
    latency_ms integer,
    input_tokens integer,
    output_tokens integer,
    finish_reason text,
    error_type text,
    created_at timestamptz not null default now()
);

create table public.google_oauth_credentials (
    id uuid primary key default gen_random_uuid(),
    public_id text not null unique,
    user_id uuid not null references auth.users(id) on delete cascade,
    provider text not null default 'google',
    encrypted_provider_refresh_token text not null,
    encryption_key_version text not null,
    scope text not null,
    expires_at timestamptz,
    revoked_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, provider)
);

create table public.audit_logs (
    id uuid primary key default gen_random_uuid(),
    public_id text not null unique,
    actor_id text,
    action text not null,
    target_type text not null,
    target_id text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index monthly_report_sources_job_id_idx on public.monthly_report_sources(job_id);
create index monthly_report_artifacts_job_id_idx on public.monthly_report_artifacts(job_id);
create index monthly_report_validations_job_id_idx on public.monthly_report_validations(job_id);
create index monthly_report_feedback_job_id_idx on public.monthly_report_feedback(job_id);
create index llm_call_logs_job_id_idx on public.llm_call_logs(job_id);
create index audit_logs_target_idx on public.audit_logs(target_type, target_id);
