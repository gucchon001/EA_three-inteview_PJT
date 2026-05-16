alter table public.monthly_report_jobs enable row level security;
alter table public.monthly_report_sources enable row level security;
alter table public.monthly_report_artifacts enable row level security;
alter table public.monthly_report_validations enable row level security;
alter table public.monthly_report_feedback enable row level security;
alter table public.llm_call_logs enable row level security;
alter table public.google_oauth_credentials enable row level security;
alter table public.audit_logs enable row level security;

create policy monthly_report_jobs_owner_select
    on public.monthly_report_jobs
    for select
    to authenticated
    using (created_by = auth.uid()::text);

create policy monthly_report_jobs_owner_insert
    on public.monthly_report_jobs
    for insert
    to authenticated
    with check (created_by = auth.uid()::text);

create policy monthly_report_jobs_owner_update
    on public.monthly_report_jobs
    for update
    to authenticated
    using (created_by = auth.uid()::text)
    with check (created_by = auth.uid()::text);

create policy monthly_report_sources_owner_select
    on public.monthly_report_sources
    for select
    to authenticated
    using (
        exists (
            select 1
            from public.monthly_report_jobs j
            where j.id = monthly_report_sources.job_id
              and j.created_by = auth.uid()::text
        )
    );

create policy monthly_report_sources_owner_insert
    on public.monthly_report_sources
    for insert
    to authenticated
    with check (
        exists (
            select 1
            from public.monthly_report_jobs j
            where j.id = monthly_report_sources.job_id
              and j.created_by = auth.uid()::text
        )
    );

create policy monthly_report_artifacts_owner_select
    on public.monthly_report_artifacts
    for select
    to authenticated
    using (
        exists (
            select 1
            from public.monthly_report_jobs j
            where j.id = monthly_report_artifacts.job_id
              and j.created_by = auth.uid()::text
        )
    );

create policy monthly_report_artifacts_owner_insert
    on public.monthly_report_artifacts
    for insert
    to authenticated
    with check (
        exists (
            select 1
            from public.monthly_report_jobs j
            where j.id = monthly_report_artifacts.job_id
              and j.created_by = auth.uid()::text
        )
    );

create policy monthly_report_validations_owner_select
    on public.monthly_report_validations
    for select
    to authenticated
    using (
        exists (
            select 1
            from public.monthly_report_jobs j
            where j.id = monthly_report_validations.job_id
              and j.created_by = auth.uid()::text
        )
    );

create policy monthly_report_validations_owner_insert
    on public.monthly_report_validations
    for insert
    to authenticated
    with check (
        exists (
            select 1
            from public.monthly_report_jobs j
            where j.id = monthly_report_validations.job_id
              and j.created_by = auth.uid()::text
        )
    );

create policy monthly_report_feedback_owner_select
    on public.monthly_report_feedback
    for select
    to authenticated
    using (
        exists (
            select 1
            from public.monthly_report_jobs j
            where j.id = monthly_report_feedback.job_id
              and j.created_by = auth.uid()::text
        )
    );

create policy monthly_report_feedback_owner_insert
    on public.monthly_report_feedback
    for insert
    to authenticated
    with check (
        created_by = auth.uid()::text
        and exists (
            select 1
            from public.monthly_report_jobs j
            where j.id = monthly_report_feedback.job_id
              and j.created_by = auth.uid()::text
        )
    );

create policy llm_call_logs_owner_select
    on public.llm_call_logs
    for select
    to authenticated
    using (
        exists (
            select 1
            from public.monthly_report_jobs j
            where j.id = llm_call_logs.job_id
              and j.created_by = auth.uid()::text
        )
    );

create policy google_oauth_credentials_owner_all
    on public.google_oauth_credentials
    for all
    to authenticated
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

create policy audit_logs_no_client_access
    on public.audit_logs
    for all
    to authenticated
    using (false)
    with check (false);
