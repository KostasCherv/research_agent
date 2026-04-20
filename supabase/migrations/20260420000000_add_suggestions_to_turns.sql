alter table public.conversation_turns
    add column if not exists suggestions jsonb not null default '[]'::jsonb;
