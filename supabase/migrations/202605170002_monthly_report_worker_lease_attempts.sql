alter table public.monthly_report_jobs
    add column if not exists worker_attempts integer not null default 0,
    add column if not exists max_worker_attempts integer not null default 3,
    add column if not exists worker_last_claimed_at timestamptz;

create index if not exists monthly_report_jobs_worker_runnable_idx
    on public.monthly_report_jobs(status, current_stage, updated_at, created_at)
    where deleted_at is null;
