alter table if exists public.session_runs
    add column if not exists status text not null default 'completed';

alter table if exists public.session_runs
    add column if not exists error_details text null;

alter table if exists public.session_runs
    drop constraint if exists session_runs_status_check;

alter table if exists public.session_runs
    add constraint session_runs_status_check
    check (status in ('running', 'completed', 'failed'));
