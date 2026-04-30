alter table public.rag_chat_sessions
add column if not exists title text not null default 'New chat';

create index if not exists idx_rag_chat_sessions_owner_agent_title
    on public.rag_chat_sessions(owner_id, agent_id, title);
