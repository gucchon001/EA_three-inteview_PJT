alter table public.monthly_report_jobs
    add column if not exists prompt_scope_notes text;
