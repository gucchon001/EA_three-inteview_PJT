alter table public.monthly_report_jobs
    add column if not exists error_type text,
    add column if not exists error_message text;
