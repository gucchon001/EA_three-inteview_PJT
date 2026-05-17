create table public.monthly_report_idempotency_keys (
    id uuid primary key default gen_random_uuid(),
    owner_user_id text not null,
    operation text not null,
    idempotency_key text not null,
    job_id uuid references public.monthly_report_jobs(id) on delete set null,
    response_json jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (owner_user_id, operation, idempotency_key)
);

create index monthly_report_idempotency_keys_job_id_idx
    on public.monthly_report_idempotency_keys(job_id);

alter table public.monthly_report_idempotency_keys enable row level security;

create policy monthly_report_idempotency_keys_no_client_access
    on public.monthly_report_idempotency_keys
    for all
    to authenticated
    using (false)
    with check (false);
