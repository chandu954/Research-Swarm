-- ResearchSwarm persistence schema
-- Prefix `rs_` keeps the local dev database isolated from other local apps.

-- ============================================================
-- 1. Profiles (bridged from FastAPI JWT users, Phase 3)
-- ============================================================
create table if not exists public.rs_profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  legacy_user_id text unique,
  email text unique not null,
  name text not null default '',
  avatar_url text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ============================================================
-- 2. Research sessions
-- ============================================================
create table if not exists public.rs_research_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  title text not null default 'Untitled research',
  prompt text not null,
  mode text not null default 'quick',
  debate_enabled boolean not null default false,
  status text not null default 'planning'
    check (status in ('planning', 'searching', 'documents', 'ranking', 'writing', 'completed', 'failed')),
  sources_total integer not null default 0,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists rs_sessions_user_updated_idx
  on public.rs_research_sessions (user_id, updated_at desc);

-- ============================================================
-- 3. Messages (chat history per session)
-- ============================================================
create table if not exists public.rs_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.rs_research_sessions (id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null default '',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists rs_messages_session_idx
  on public.rs_messages (session_id, created_at);

-- ============================================================
-- 4. Reports
-- ============================================================
create table if not exists public.rs_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  session_id uuid references public.rs_research_sessions (id) on delete set null,
  title text not null,
  content_md text not null default '',
  format text not null default 'markdown' check (format in ('markdown', 'pdf', 'html')),
  status text not null default 'draft' check (status in ('draft', 'generating', 'ready', 'failed')),
  is_pinned boolean not null default false,
  is_favorite boolean not null default false,
  storage_path text,
  sources jsonb not null default '[]'::jsonb,
  metrics jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists rs_reports_user_updated_idx
  on public.rs_reports (user_id, updated_at desc);

-- ============================================================
-- 5. Documents (uploaded PDFs, markdown, images)
-- ============================================================
create table if not exists public.rs_documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  name text not null,
  storage_path text not null,
  mime_type text not null default 'application/pdf',
  size_bytes bigint not null default 0,
  status text not null default 'indexing'
    check (status in ('indexing', 'ready', 'failed')),
  pages integer,
  chunks integer,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists rs_documents_user_idx
  on public.rs_documents (user_id, created_at desc);

-- ============================================================
-- 6. Collections + items (reports and documents inside folders)
-- ============================================================
create table if not exists public.rs_collections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  name text not null,
  description text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, name)
);

create table if not exists public.rs_collection_items (
  collection_id uuid not null references public.rs_collections (id) on delete cascade,
  report_id uuid references public.rs_reports (id) on delete cascade,
  document_id uuid references public.rs_documents (id) on delete cascade,
  created_at timestamptz not null default now(),
  check (report_id is not null or document_id is not null),
  primary key (collection_id, report_id, document_id)
);

-- ============================================================
-- 7. Saved prompts
-- ============================================================
create table if not exists public.rs_saved_prompts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  label text not null,
  prompt text not null,
  usage_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ============================================================
-- 8. Recent searches
-- ============================================================
create table if not exists public.rs_recent_searches (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  query text not null,
  created_at timestamptz not null default now()
);

create index if not exists rs_searches_user_idx
  on public.rs_recent_searches (user_id, created_at desc);

-- ============================================================
-- 9. Activity log
-- ============================================================
create table if not exists public.rs_activity_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  action text not null,
  entity_type text not null default 'research',
  entity_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists rs_activity_user_idx
  on public.rs_activity_logs (user_id, created_at desc);

-- ============================================================
-- 10. Settings
-- ============================================================
create table if not exists public.rs_settings (
  user_id uuid primary key references auth.users (id) on delete cascade,
  preferences jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- ============================================================
-- 11. Agent runs (per session, workflow panel)
-- ============================================================
create table if not exists public.rs_agent_runs (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.rs_research_sessions (id) on delete cascade,
  agent_key text not null,
  status text not null default 'pending'
    check (status in ('pending', 'running', 'completed', 'failed', 'skipped')),
  model text,
  latency_ms integer,
  tokens integer,
  sources integer,
  documents integer,
  output jsonb,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists rs_agent_runs_session_idx
  on public.rs_agent_runs (session_id, created_at);

-- ============================================================
-- 12. Run metrics (per session)
-- ============================================================
create table if not exists public.rs_run_metrics (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.rs_research_sessions (id) on delete cascade,
  execution_time_ms integer,
  sources_found integer not null default 0,
  relevant_sources integer not null default 0,
  documents integer not null default 0,
  chunks integer not null default 0,
  prompt_tokens integer not null default 0,
  completion_tokens integer not null default 0,
  total_tokens integer not null default 0,
  estimated_cost numeric(12, 6) not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists rs_run_metrics_session_idx
  on public.rs_run_metrics (session_id, created_at desc);

-- ============================================================
-- updated_at helper
-- ============================================================
create or replace function public.rs_set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

do $$
declare t text;
begin
  foreach t in array array['rs_profiles', 'rs_research_sessions', 'rs_reports', 'rs_documents', 'rs_collections', 'rs_saved_prompts', 'rs_settings']
  loop
    execute format('create or replace trigger rs_%s_updated_at before update on public.%I for each row execute function public.rs_set_updated_at()', t, t);
  end loop;
end $$;

-- ============================================================
-- Auto-profile on native Supabase signup
-- ============================================================
create or replace function public.rs_handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.rs_profiles (id, email, name, avatar_url)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'name', split_part(new.email, '@', 1), ''),
    new.raw_user_meta_data ->> 'avatar_url'
  )
  on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists rs_on_auth_user_created on auth.users;
create trigger rs_on_auth_user_created
  after insert on auth.users
  for each row execute function public.rs_handle_new_user();

-- ============================================================
-- Row Level Security
-- ============================================================
alter table public.rs_profiles enable row level security;
alter table public.rs_research_sessions enable row level security;
alter table public.rs_messages enable row level security;
alter table public.rs_reports enable row level security;
alter table public.rs_documents enable row level security;
alter table public.rs_collections enable row level security;
alter table public.rs_collection_items enable row level security;
alter table public.rs_saved_prompts enable row level security;
alter table public.rs_recent_searches enable row level security;
alter table public.rs_activity_logs enable row level security;
alter table public.rs_settings enable row level security;
alter table public.rs_agent_runs enable row level security;
alter table public.rs_run_metrics enable row level security;

drop policy if exists "own profile" on public.rs_profiles;
create policy "own profile"
  on public.rs_profiles for all
  using (id = auth.uid()) with check (id = auth.uid());

drop policy if exists "own sessions" on public.rs_research_sessions;
create policy "own sessions"
  on public.rs_research_sessions for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "own session messages" on public.rs_messages;
create policy "own session messages"
  on public.rs_messages for all
  using (
    exists (
      select 1 from public.rs_research_sessions s
      where s.id = session_id and s.user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.rs_research_sessions s
      where s.id = session_id and s.user_id = auth.uid()
    )
  );

drop policy if exists "own reports" on public.rs_reports;
create policy "own reports"
  on public.rs_reports for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "own documents" on public.rs_documents;
create policy "own documents"
  on public.rs_documents for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "own collections" on public.rs_collections;
create policy "own collections"
  on public.rs_collections for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "own collection items" on public.rs_collection_items;
create policy "own collection items"
  on public.rs_collection_items for all
  using (
    exists (
      select 1 from public.rs_collections c
      where c.id = collection_id and c.user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.rs_collections c
      where c.id = collection_id and c.user_id = auth.uid()
    )
  );

drop policy if exists "own saved prompts" on public.rs_saved_prompts;
create policy "own saved prompts"
  on public.rs_saved_prompts for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "own recent searches" on public.rs_recent_searches;
create policy "own recent searches"
  on public.rs_recent_searches for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "own activity" on public.rs_activity_logs;
create policy "own activity"
  on public.rs_activity_logs for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "own settings" on public.rs_settings;
create policy "own settings"
  on public.rs_settings for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "own session agent runs" on public.rs_agent_runs;
create policy "own session agent runs"
  on public.rs_agent_runs for all
  using (
    exists (
      select 1 from public.rs_research_sessions s
      where s.id = session_id and s.user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.rs_research_sessions s
      where s.id = session_id and s.user_id = auth.uid()
    )
  );

drop policy if exists "own session metrics" on public.rs_run_metrics;
create policy "own session metrics"
  on public.rs_run_metrics for all
  using (
    exists (
      select 1 from public.rs_research_sessions s
      where s.id = session_id and s.user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.rs_research_sessions s
      where s.id = session_id and s.user_id = auth.uid()
    )
  );

-- ============================================================
-- Storage buckets
-- ============================================================
insert into storage.buckets (id, name, public)
values
  ('rs_documents', 'rs_documents', false),
  ('rs_reports', 'rs_reports', false),
  ('rs_avatars', 'rs_avatars', false)
on conflict (id) do nothing;

drop policy if exists "own documents files" on storage.objects;
create policy "own documents files"
  on storage.objects for all
  using (bucket_id = 'rs_documents' and (storage.foldername(name))[1] = auth.uid()::text)
  with check (bucket_id = 'rs_documents' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "own report files" on storage.objects;
create policy "own report files"
  on storage.objects for all
  using (bucket_id = 'rs_reports' and (storage.foldername(name))[1] = auth.uid()::text)
  with check (bucket_id = 'rs_reports' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "own avatars" on storage.objects;
create policy "own avatars"
  on storage.objects for all
  using (bucket_id = 'rs_avatars' and (storage.foldername(name))[1] = auth.uid()::text)
  with check (bucket_id = 'rs_avatars' and (storage.foldername(name))[1] = auth.uid()::text);

-- ============================================================
-- Realtime
-- ============================================================
alter publication supabase_realtime add table public.rs_research_sessions;
alter publication supabase_realtime add table public.rs_messages;
alter publication supabase_realtime add table public.rs_agent_runs;
alter publication supabase_realtime add table public.rs_run_metrics;
alter publication supabase_realtime add table public.rs_reports;
alter publication supabase_realtime add table public.rs_documents;
alter publication supabase_realtime add table public.rs_activity_logs;
