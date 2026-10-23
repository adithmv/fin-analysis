begin;

create table public.watchlist (
  symbol text not null,
  exchange text not null default 'NSE',
  active boolean not null default true,
  added_at timestamptz not null default now(),
  primary key (symbol, exchange)
);

create table public.candles (
  symbol text not null,
  exchange text not null default 'NSE',
  timeframe text not null default '1d',
  ts timestamptz not null,
  open numeric not null check (open > 0),
  high numeric not null check (high > 0),
  low numeric not null check (low > 0),
  close numeric not null check (close > 0),
  volume bigint check (volume >= 0),
  source text not null,
  adjusted boolean not null default false,
  fetched_at timestamptz not null default now(),
  primary key (symbol, exchange, timeframe, ts),
  check (high >= greatest(open, close) and low <= least(open, close)),
  check (open <> 'NaN'::numeric and high <> 'NaN'::numeric
    and low <> 'NaN'::numeric and close <> 'NaN'::numeric
    and high <> 'Infinity'::numeric)
);
create index candles_symbol_ts_idx on public.candles (symbol, timeframe, ts desc);

create table public.agent_events (
  id bigserial primary key,
  ts timestamptz not null default now(),
  run_id uuid not null,
  module text not null,
  agent text,
  action text not null,
  tool text,
  status text not null check (status in ('started','success','failed','retried','skipped','warning')),
  symbol text,
  input_summary text,
  output_summary text,
  source_urls text[],
  duration_ms integer check (duration_ms >= 0),
  api_calls integer check (api_calls >= 0),
  tokens_in integer,
  tokens_out integer,
  error text,
  meta jsonb not null default '{}'::jsonb
);
create index agent_events_ts_idx on public.agent_events (ts desc, id desc);
create index agent_events_module_idx on public.agent_events (module, ts desc);
create index agent_events_status_idx on public.agent_events (status, ts desc);
create index agent_events_symbol_idx on public.agent_events (symbol, ts desc);
create index agent_events_run_idx on public.agent_events (run_id, ts, id);

alter table public.watchlist enable row level security;
alter table public.candles enable row level security;
alter table public.agent_events enable row level security;

-- Phase 1 explicitly permits public read-only access. Never put private data here.
revoke all on public.watchlist, public.candles, public.agent_events from anon, authenticated;
grant select on public.watchlist, public.candles, public.agent_events to anon, authenticated;
create policy read_watchlist on public.watchlist for select to anon, authenticated using (true);
create policy read_candles on public.candles for select to anon, authenticated using (true);
create policy read_events on public.agent_events for select to anon, authenticated using (true);
grant select, insert, update on public.watchlist, public.candles to service_role;
revoke all on public.agent_events from service_role;
grant select, insert on public.agent_events to service_role;
grant usage, select on sequence public.agent_events_id_seq to service_role;
revoke all on sequence public.agent_events_id_seq from anon, authenticated;

alter publication supabase_realtime add table public.agent_events, public.candles;
comment on column public.candles.ts is 'Daily session date at 00:00 Asia/Kolkata, stored in UTC';
comment on table public.agent_events is 'Append-only action log; public read-only in Phase 1';
commit;
