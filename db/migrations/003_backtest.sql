begin;
-- Event-study results: what happened after each signal.
create table signal_stats (
  id                 bigserial primary key,
  stats_run_id       uuid        not null,
  signal_key         text        not null,
  direction          text,
  scope              text        not null,   -- a symbol, or 'POOLED' for all watchlist stocks
  sample             text        not null
                     check (sample in ('all','in_sample','out_of_sample')),
  horizon_days       integer     not null,   -- 1, 3, 5, 10, 20
  n_events           integer     not null,   -- raw count of occurrences
  n_independent      integer     not null,   -- count after removing overlapping events
  mean_return        numeric,                -- directional, see section 7.4
  median_return      numeric,
  win_rate           numeric,
  baseline_mean      numeric,                -- same stock/period, all days, same direction
  edge               numeric,                -- mean_return - baseline_mean
  sufficient_sample  boolean     not null,   -- n_independent >= configured minimum
  period_start       date,
  period_end         date,
  config             jsonb       not null default '{}'::jsonb,
  logic_version      text        not null,
  computed_at        timestamptz not null default now()
);
create index signal_stats_lookup_idx on signal_stats (signal_key, scope, sample, horizon_days);

-- One row per backtest execution.
create table backtest_runs (
  id            uuid        primary key,
  name          text        not null,
  strategy_key  text        not null,
  config        jsonb       not null,        -- full parameters, fees, slippage, split dates
  symbols       text[]      not null,
  period_start  date        not null,
  period_end    date        not null,
  fees_pct      numeric     not null,
  slippage_pct  numeric     not null,
  code_version  text        not null,        -- git commit hash
  created_at    timestamptz not null default now()
);

-- Per-symbol, per-sample results.
create table backtest_results (
  run_id             uuid    not null references backtest_runs(id) on delete cascade,
  symbol             text    not null,
  sample             text    not null check (sample in ('all','in_sample','out_of_sample')),
  metrics            jsonb   not null,       -- total_return, cagr, max_drawdown, sharpe, win_rate, n_trades, exposure
  benchmark_metrics  jsonb   not null,       -- buy-and-hold for the same stock and period
  benchmark_equity_curve jsonb,
  equity_curve       jsonb,                  -- downsampled [[date, value], ...]
  primary key (run_id, symbol, sample)
);

create table backtest_trades (
  id           bigserial primary key,
  run_id       uuid        not null references backtest_runs(id) on delete cascade,
  symbol       text        not null,
  sample       text not null check (sample in ('all','in_sample','out_of_sample')),
  entry_ts     timestamptz not null,
  exit_ts      timestamptz not null,
  entry_price  numeric     not null,
  exit_price   numeric     not null,
  return_pct   numeric     not null,         -- after costs
  bars_held    integer     not null,
  exit_reason  text                          -- 'signal', 'time_stop', 'end_of_data'
);
create index backtest_trades_run_idx on backtest_trades (run_id, symbol, entry_ts);

alter table public.signal_stats enable row level security;
revoke all on public.signal_stats from anon, authenticated;
grant select on public.signal_stats to anon, authenticated;
create policy read_signal_stats on public.signal_stats for select to anon, authenticated using (true);
grant select,insert,update,delete on public.signal_stats to service_role;
alter table public.backtest_runs enable row level security;
revoke all on public.backtest_runs from anon, authenticated;
grant select on public.backtest_runs to anon, authenticated;
create policy read_backtest_runs on public.backtest_runs for select to anon, authenticated using (true);
grant select,insert,update,delete on public.backtest_runs to service_role;
alter table public.backtest_results enable row level security;
revoke all on public.backtest_results from anon, authenticated;
grant select on public.backtest_results to anon, authenticated;
create policy read_backtest_results on public.backtest_results for select to anon, authenticated using (true);
grant select,insert,update,delete on public.backtest_results to service_role;
alter table public.backtest_trades enable row level security;
revoke all on public.backtest_trades from anon, authenticated;
grant select on public.backtest_trades to anon, authenticated;
create policy read_backtest_trades on public.backtest_trades for select to anon, authenticated using (true);
grant select,insert,update,delete on public.backtest_trades to service_role;

create unique index signal_stats_run_unique on public.signal_stats
  (stats_run_id,signal_key,direction,scope,sample,horizon_days);
create unique index backtest_trades_unique on public.backtest_trades
  (run_id,symbol,sample,entry_ts,exit_ts);
grant usage,select on sequence public.signal_stats_id_seq,public.backtest_trades_id_seq to service_role;
revoke all on sequence public.signal_stats_id_seq,public.backtest_trades_id_seq from anon,authenticated;

commit;
