create table if not exists public.rag_resources (
    id uuid primary key,
    owner_id uuid not null,
    workspace_id text not null,
    filename text not null,
    mime_type text not null,
    byte_size bigint not null check (byte_size >= 0),
    storage_uri text not null,
    state text not null default 'uploaded' check (state in ('uploaded', 'processing', 'ready', 'failed')),
    error_details text null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.rag_ingestion_jobs (
    id uuid primary key,
    resource_id uuid not null references public.rag_resources(id) on delete cascade,
    owner_id uuid not null,
    workspace_id text not null,
    status text not null default 'queued' check (status in ('queued', 'running', 'succeeded', 'failed')),
    stage text not null default 'queued',
    retries int not null default 0,
    max_retries int not null default 2,
    error_details text null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.rag_agents (
    id uuid primary key,
    owner_id uuid not null,
    workspace_id text not null,
    name text not null,
    description text not null default '',
    system_instructions text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.rag_agent_resources (
    agent_id uuid not null references public.rag_agents(id) on delete cascade,
    resource_id uuid not null references public.rag_resources(id) on delete cascade,
    owner_id uuid not null,
    workspace_id text not null,
    created_at timestamptz not null default now(),
    primary key (agent_id, resource_id)
);

create table if not exists public.rag_chat_sessions (
    id uuid primary key,
    owner_id uuid not null,
    workspace_id text not null,
    agent_id uuid not null references public.rag_agents(id) on delete cascade,
    created_at timestamptz not null default now()
);

create table if not exists public.rag_chat_messages (
    id uuid primary key,
    session_id uuid not null references public.rag_chat_sessions(id) on delete cascade,
    agent_id uuid not null references public.rag_agents(id) on delete cascade,
    owner_id uuid not null,
    role text not null check (role in ('user', 'assistant')),
    content text not null,
    citations jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_rag_resources_owner_workspace
    on public.rag_resources(owner_id, workspace_id, created_at desc);

create index if not exists idx_rag_ingestion_jobs_resource_created
    on public.rag_ingestion_jobs(resource_id, created_at desc);

create index if not exists idx_rag_agents_owner_workspace
    on public.rag_agents(owner_id, workspace_id, created_at desc);

create index if not exists idx_rag_agent_resources_owner_workspace
    on public.rag_agent_resources(owner_id, workspace_id, agent_id);

create index if not exists idx_rag_chat_sessions_owner_agent
    on public.rag_chat_sessions(owner_id, agent_id, created_at desc);

create index if not exists idx_rag_chat_messages_session_created
    on public.rag_chat_messages(session_id, created_at asc);
