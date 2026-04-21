create table if not exists public.event_outbox (
    id uuid primary key,
    event_name text not null,
    payload jsonb not null default '{}'::jsonb,
    status text not null default 'pending',
    attempts integer not null default 0,
    last_error text,
    next_attempt_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    dispatched_at timestamptz,
    sent_at timestamptz,
    constraint event_outbox_status_check
        check (status in ('pending', 'dispatching', 'sent', 'failed'))
);

create index if not exists idx_event_outbox_dispatch
    on public.event_outbox(status, next_attempt_at, created_at)
    where status in ('pending', 'dispatching');

create or replace function public.create_resource_job_and_outbox(
    p_resource jsonb,
    p_job jsonb,
    p_outbox jsonb
) returns void
language plpgsql
security definer
as $$
begin
    insert into public.rag_resources (
        id, owner_id, workspace_id, filename, mime_type,
        byte_size, storage_uri, state, error_details,
        created_at, updated_at
    ) values (
        (p_resource->>'resource_id')::uuid,
        (p_resource->>'owner_id')::uuid,
        p_resource->>'workspace_id',
        p_resource->>'filename',
        p_resource->>'mime_type',
        (p_resource->>'byte_size')::bigint,
        p_resource->>'storage_uri',
        p_resource->>'state',
        p_resource->>'error_details',
        (p_resource->>'created_at')::timestamptz,
        (p_resource->>'updated_at')::timestamptz
    );

    insert into public.rag_ingestion_jobs (
        id, resource_id, owner_id, workspace_id,
        status, stage, retries, max_retries, error_details,
        created_at, updated_at
    ) values (
        (p_job->>'job_id')::uuid,
        (p_job->>'resource_id')::uuid,
        (p_job->>'owner_id')::uuid,
        p_job->>'workspace_id',
        p_job->>'status',
        p_job->>'stage',
        (p_job->>'retries')::integer,
        (p_job->>'max_retries')::integer,
        p_job->>'error_details',
        (p_job->>'created_at')::timestamptz,
        (p_job->>'updated_at')::timestamptz
    );

    insert into public.event_outbox (
        id, event_name, payload, status, attempts,
        next_attempt_at, created_at
    ) values (
        (p_outbox->>'id')::uuid,
        p_outbox->>'event_name',
        p_outbox->'payload',
        'pending',
        0,
        (p_outbox->>'next_attempt_at')::timestamptz,
        (p_outbox->>'created_at')::timestamptz
    );
end;
$$;

drop function if exists public.create_ingestion_job_with_outbox(jsonb, jsonb);
