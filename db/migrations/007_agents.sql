begin;
-- One discussion thread per stock per trading date (plus on-demand threads).
create table threads (
  id              uuid primary key default gen_random_uuid(),
  symbol          text not null,
  exchange        text not null default 'NSE',
  thread_date     date not null,                 -- the trading date the analysis is "as of"
  kind            text not null default 'daily' check (kind in ('daily','on_demand')),
  status          text not null default 'queued'
                  check (status in ('queued','running','completed','failed','budget_exhausted','skipped')),
  data_cutoff_ts  timestamptz not null,          -- NO data after this moment may be used
  run_id          uuid,
  llm_provider    text,
  llm_model       text,
  prompt_version  text not null,
  config          jsonb not null default '{}'::jsonb,   -- snapshot of agents.yaml and llm.yaml settings used
  failure_reason  text,
  created_at      timestamptz not null default now(),
  started_at      timestamptz,
  finished_at     timestamptz
);
create unique index threads_daily_uq
  on threads (symbol, exchange, thread_date) where kind = 'daily';
create index threads_symbol_idx on threads (symbol, thread_date desc);

-- The exact evidence the agents were given, frozen for reproducibility.
create table evidence_packs (
  thread_id   uuid primary key references threads(id) on delete cascade,
  pack        jsonb not null,
  pack_hash   text not null,
  built_at    timestamptz not null default now()
);

-- Messages in a thread: agents, the user, and system notes.
create table messages (
  id                    bigserial primary key,
  thread_id             uuid not null references threads(id) on delete cascade,
  seq                   integer not null,
  reply_to              bigint references messages(id),
  author_role           text not null,   -- technical_analyst, news_analyst, bull, bear, risk_manager,
                                         -- summariser, research_assistant, user, system, verifier
  author_type           text not null check (author_type in ('agent','user','system')),
  round                 integer,
  content_md            text not null,
  stance                text check (stance in ('bullish','bearish','neutral','mixed')),
  confidence            text check (confidence in ('low','medium','high')),
  claims                jsonb not null default '[]'::jsonb,     -- structured claims (see 8.2)
  evidence              jsonb not null default '[]'::jsonb,     -- evidence references (see 8.1)
  verification_status   text not null default 'pending'
                        check (verification_status in
                          ('pending','verified','partial','unverified','not_applicable')),
  verification_notes    jsonb not null default '[]'::jsonb,
  event_ids             bigint[] not null default '{}',         -- agent_events ids (LLM and tool calls) behind this message
  llm_model             text,
  tokens_in             integer,
  tokens_out            integer,
  created_at            timestamptz not null default now(),
  unique (thread_id, seq)
);
create index messages_thread_idx on messages (thread_id, seq);

-- The final structured report of a thread.
create table analysis_reports (
  id                    uuid primary key default gen_random_uuid(),
  thread_id             uuid not null unique references threads(id) on delete cascade,
  symbol                text not null,
  exchange              text not null default 'NSE',
  as_of_date            date not null,
  stance                text not null check (stance in ('bullish','bearish','neutral','mixed')),
  confidence            text not null check (confidence in ('low','medium','high')),
  horizon_days          integer not null,        -- the period the stance refers to
  summary_md            text not null,
  key_points            jsonb not null,
  risks                 jsonb not null,
  invalidation          jsonb not null,          -- what observations would change this view
  what_changed          jsonb,                   -- difference versus the previous report
  evidence_strength     text not null check (evidence_strength in ('none','weak','moderate','strong')),
  evidence_strength_why jsonb not null,          -- the code's reasoning (which stats it used)
  data_quality_notes    jsonb not null default '[]'::jsonb,
  verification_summary  jsonb not null,          -- counts of verified / partial / unverified messages and claims
  disclaimer            text not null,
  created_at            timestamptz not null default now()
);
create index analysis_reports_symbol_idx on analysis_reports (symbol, as_of_date desc);

-- Requests that the dashboard (user) sends to the agent worker.
create table analysis_requests (
  id             bigserial primary key,
  kind           text not null check (kind in ('analysis','question')),
  symbol         text,
  thread_id      uuid references threads(id),
  question_text  text,
  status         text not null default 'pending'
                 check (status in ('pending','running','done','failed','rejected')),
  requested_at   timestamptz not null default now(),
  picked_up_at   timestamptz,
  finished_at    timestamptz,
  error          text
);
create index analysis_requests_status_idx on analysis_requests (status, requested_at);

-- How each report's stance actually turned out (filled by backtest grade-reports).
create table report_outcomes (
  report_id         uuid not null references analysis_reports(id) on delete cascade,
  horizon_days      integer not null,
  entry_date        date,
  exit_date         date,
  realized_return   numeric,
  benchmark_return  numeric,
  excess_return     numeric,
  directional_hit   boolean,       -- bullish and excess > 0, or bearish and excess < 0; null for neutral/mixed
  graded_at         timestamptz not null default now(),
  primary key (report_id, horizon_days)
);

-- A single explicitly provisioned account. Never authorize using user-editable metadata.
create schema if not exists private;
create table private.research_owner (
 singleton boolean primary key default true check(singleton),
 user_id uuid not null unique references auth.users(id) on delete cascade
);
alter table private.research_owner enable row level security;
grant usage on schema private to authenticated,service_role;
grant select on private.research_owner to authenticated;
grant all on private.research_owner to service_role;
create policy read_own_access on private.research_owner for select to authenticated
 using(user_id=(select auth.uid()));

alter table analysis_requests add column user_id uuid default auth.uid() references auth.users(id);
alter table analysis_requests add constraint valid_request_shape check (
 (kind='analysis' and symbol is not null and symbol ~ '^[A-Z0-9&-]{1,24}$' and question_text is null and thread_id is null)
 or (kind='question' and thread_id is not null and question_text is not null and length(trim(question_text)) between 1 and 2000)
);
create index analysis_requests_user_idx on analysis_requests(user_id);
create index analysis_requests_thread_idx on analysis_requests(thread_id);
create index messages_reply_idx on messages(reply_to);

-- Reserved attempts count toward budgets even if the process or provider fails.
create table agent_call_reservations (
 id uuid primary key default gen_random_uuid(), run_id uuid not null,
 thread_id uuid references threads(id), role text not null, provider text not null, model text not null,
 budget_day date not null, reserved_at timestamptz not null default now(),
 estimated_input_tokens integer not null check(estimated_input_tokens>=0),
 tokens_in integer, tokens_out integer, status text not null default 'reserved'
 check(status in ('reserved','success','failed')), event_id bigint references agent_events(id)
);
create index agent_calls_day_idx on agent_call_reservations(provider,budget_day);
create index agent_calls_thread_idx on agent_call_reservations(thread_id);
create index agent_calls_event_idx on agent_call_reservations(event_id);
create index agent_calls_time_idx on agent_call_reservations(reserved_at);

do $$ declare t text; begin
 foreach t in array array['threads','messages','evidence_packs','analysis_reports','analysis_requests','report_outcomes','agent_call_reservations'] loop
  execute format('alter table public.%I enable row level security',t);
  execute format('revoke all on public.%I from anon,authenticated',t);
  execute format('grant select on public.%I to authenticated',t);
  execute format('grant all on public.%I to service_role',t);
  execute format('create policy owner_read on public.%I for select to authenticated using (exists(select 1 from private.research_owner where user_id=(select auth.uid())))',t);
 end loop;
end $$;
grant usage,select on sequence messages_id_seq,analysis_requests_id_seq to service_role;
grant usage on sequence analysis_requests_id_seq to authenticated;
grant insert(kind,symbol,thread_id,question_text) on analysis_requests to authenticated;
create policy owner_request on analysis_requests for insert to authenticated with check (
 user_id=(select auth.uid()) and status='pending' and picked_up_at is null and finished_at is null and error is null
 and exists(select 1 from private.research_owner where user_id=(select auth.uid()))
 and (kind='question' or exists(select 1 from public.watchlist w where w.symbol=analysis_requests.symbol and w.exchange='NSE' and w.active and w.kind='equity'))
);

create function public.set_research_owner(p_user uuid) returns void language plpgsql security invoker set search_path='' as $$
begin
 if exists(select 1 from private.research_owner where user_id<>p_user) then raise exception 'Owner already configured';end if;
 insert into private.research_owner(user_id) values(p_user) on conflict(user_id) do nothing;
end $$;
revoke all on function public.set_research_owner(uuid) from public,anon,authenticated;
grant execute on function public.set_research_owner(uuid) to service_role;

create function public.claim_analysis_request() returns setof public.analysis_requests
language sql security invoker set search_path='' as $$
 update public.analysis_requests set status='running',picked_up_at=now()
 where id=(select id from public.analysis_requests where status='pending' order by requested_at,id for update skip locked limit 1)
 returning *;
$$;
revoke all on function public.claim_analysis_request() from public,anon,authenticated;
grant execute on function public.claim_analysis_request() to service_role;

create function public.reserve_agent_call(p_run uuid,p_thread uuid,p_role text,p_provider text,p_model text,
 p_day date,p_daily_limit integer,p_thread_limit integer,p_rpm integer,p_input_tokens integer,p_tpm integer)
returns uuid language plpgsql security invoker set search_path='' as $$
declare result uuid;
begin
 perform pg_advisory_xact_lock(hashtextextended('research_llm_budget',0));
 if p_daily_limit<1 or p_thread_limit<1 or p_rpm<1 or p_tpm<1 then raise exception 'Invalid budget';end if;
 if (select count(*) from public.agent_call_reservations where provider=p_provider and budget_day=p_day)>=p_daily_limit then raise exception 'DAILY_BUDGET';end if;
 if (select count(*) from public.agent_call_reservations where run_id=p_run)>=p_thread_limit then raise exception 'RUN_BUDGET';end if;
 if (select count(*) from public.agent_call_reservations where provider=p_provider and reserved_at>now()-interval '1 minute')>=p_rpm then raise exception 'RATE_LIMIT';end if;
 if p_input_tokens>p_tpm then raise exception 'PROMPT_TOO_LARGE';end if;
 if coalesce((select sum(estimated_input_tokens) from public.agent_call_reservations where provider=p_provider and reserved_at>now()-interval '1 minute'),0)+p_input_tokens>p_tpm then raise exception 'RATE_LIMIT';end if;
 insert into public.agent_call_reservations(run_id,thread_id,role,provider,model,budget_day,estimated_input_tokens)
 values(p_run,p_thread,p_role,p_provider,p_model,p_day,p_input_tokens) returning id into result;
 return result;
end $$;
revoke all on function public.reserve_agent_call(uuid,uuid,text,text,text,date,integer,integer,integer,integer,integer) from public,anon,authenticated;
grant execute on function public.reserve_agent_call(uuid,uuid,text,text,text,date,integer,integer,integer,integer,integer) to service_role;

alter publication supabase_realtime add table public.messages,public.threads;
commit;
