alter table if exists public.research_sessions
add column if not exists title text not null default 'New session';

create index if not exists idx_research_sessions_user_created
on public.research_sessions(user_id, created_at desc);
