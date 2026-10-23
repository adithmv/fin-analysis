begin;
-- Indicator values: one row per symbol, timestamp and series.
create table indicator_values (
  symbol      text        not null,
  exchange    text        not null default 'NSE',
  timeframe   text        not null default '1d',
  ts          timestamptz not null,
  series_key  text        not null,    -- e.g. 'sma_50', 'rsi_14', 'macd_line_12_26_9', 'bb_upper_20_2'
  value       numeric,                 -- null during warm-up
  computed_at timestamptz not null default now(),
  primary key (symbol, exchange, timeframe, ts, series_key)
);
create index indicator_values_lookup_idx
  on indicator_values (symbol, timeframe, series_key, ts desc);

-- Signals: discrete things that happened on a given day.
create table signals (
  symbol        text        not null,
  exchange      text        not null default 'NSE',
  timeframe     text        not null default '1d',
  ts            timestamptz not null,
  signal_key    text        not null,   -- e.g. 'cdl_engulfing', 'rsi_14_oversold', 'sma_50_200_golden_cross'
  signal_type   text        not null
                check (signal_type in ('pattern','indicator','trend','level','data_flag')),
  direction     text
                check (direction in ('bullish','bearish','neutral')),
  raw_value     numeric,                -- e.g. TA-Lib raw output such as 100 / -100
  description   text        not null,   -- human-readable sentence (Phase 4 agents will read this)
  details       jsonb       not null default '{}'::jsonb,
  logic_version text        not null,   -- version of the rules that produced this row
  computed_at   timestamptz not null default now(),
  primary key (symbol, exchange, timeframe, ts, signal_key)
);
create index signals_key_idx    on signals (signal_key, ts desc);
create index signals_symbol_idx on signals (symbol, timeframe, ts desc);

alter table public.indicator_values enable row level security;
revoke all on public.indicator_values from anon, authenticated;
grant select on public.indicator_values to anon, authenticated;
create policy read_indicator_values on public.indicator_values for select to anon, authenticated using (true);
grant select,insert,update,delete on public.indicator_values to service_role;
alter table public.signals enable row level security;
revoke all on public.signals from anon, authenticated;
grant select on public.signals to anon, authenticated;
create policy read_signals on public.signals for select to anon, authenticated using (true);
grant select,insert,update,delete on public.signals to service_role;

create function public.replace_signal_days(p_symbol text, p_dates timestamptz[], p_indicators jsonb, p_signals jsonb)
returns void language plpgsql security invoker set search_path = '' as $$
begin
  perform pg_advisory_xact_lock(hashtextextended(p_symbol, 0));
  delete from public.indicator_values where symbol=p_symbol and exchange='NSE' and timeframe='1d' and ts=any(p_dates);
  delete from public.signals where symbol=p_symbol and exchange='NSE' and timeframe='1d' and ts=any(p_dates);
  insert into public.indicator_values select * from jsonb_populate_recordset(null::public.indicator_values,p_indicators);
  insert into public.signals select * from jsonb_populate_recordset(null::public.signals,p_signals);
end $$;
revoke all on function public.replace_signal_days(text,timestamptz[],jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.replace_signal_days(text,timestamptz[],jsonb,jsonb) to service_role;

commit;
