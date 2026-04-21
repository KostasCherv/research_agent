create table if not exists public.rag_sidecar_artifacts (
    resource_id uuid primary key references public.rag_resources(id) on delete cascade,
    owner_id uuid not null,
    workspace_id text not null,
    source_locator text not null,
    chunks jsonb not null default '[]'::jsonb,
    updated_at timestamptz not null default now()
);

create index if not exists idx_rag_sidecar_artifacts_owner_workspace
    on public.rag_sidecar_artifacts(owner_id, workspace_id);
