begin;
-- Allow index/benchmark rows (e.g. 'NIFTY 50') next to stocks.
alter table watchlist add column if not exists kind text not null default 'equity'
  check (kind in ('equity','index'));

-- News events have no inherent direction, so we also measure how much prices MOVE.
alter table signal_stats add column if not exists mean_abs_return    numeric;
alter table signal_stats add column if not exists baseline_mean_abs  numeric;
alter table signal_stats add column if not exists abnormal           boolean not null default false;
-- 'abnormal' = returns are market-adjusted (stock return minus benchmark return)

drop index public.signal_stats_run_unique;
create unique index signal_stats_run_unique on public.signal_stats (stats_run_id,signal_key,direction,scope,sample,horizon_days,abnormal);

commit;
