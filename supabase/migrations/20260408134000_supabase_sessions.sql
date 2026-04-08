create table if not exists public.research_sessions (
    id uuid primary key,
    user_id uuid not null,
    created_at timestamptz not null default now()
);

create table if not exists public.session_runs (
    id uuid primary key,
    session_id uuid not null references public.research_sessions(id) on delete cascade,
    user_id uuid not null,
    query text not null,
    source_urls jsonb not null default '[]'::jsonb,
    report text not null default '',
    created_at timestamptz not null default now()
);

create table if not exists public.conversation_turns (
    id uuid primary key,
    session_id uuid not null references public.research_sessions(id) on delete cascade,
    run_id uuid null references public.session_runs(id) on delete set null,
    user_id uuid not null,
    role text not null check (role in ('user', 'assistant')),
    content text not null,
    citations jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_research_sessions_user_id
    on public.research_sessions(user_id);

create index if not exists idx_session_runs_user_session
    on public.session_runs(user_id, session_id);

create index if not exists idx_session_runs_session_created_at
    on public.session_runs(session_id, created_at);

create index if not exists idx_conversation_turns_user_session
    on public.conversation_turns(user_id, session_id);

create index if not exists idx_conversation_turns_session_created_at
    on public.conversation_turns(session_id, created_at);
