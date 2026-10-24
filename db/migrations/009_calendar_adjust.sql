begin;
create table public.trading_calendar (
 exchange text not null default 'NSE', day date not null, is_trading_day boolean not null,
 note text, source text not null, primary key(exchange,day)
);
create table public.adjustment_factors (
 symbol text not null, exchange text not null default 'NSE', ex_date date not null,
 factor numeric not null check(factor>0 and factor<='1000'::numeric),
 corporate_action_id bigint references public.corporate_actions(id),
 status text not null check(status in ('proposed','approved','rejected')),
 approved_by text, approved_at timestamptz, note text,
 primary key(symbol,exchange,ex_date),
 check(status<>'approved' or (approved_by is not null and approved_at is not null))
);
create index adjustment_action_idx on public.adjustment_factors(corporate_action_id);
do $$ declare t text; begin
 foreach t in array array['trading_calendar','adjustment_factors'] loop
  execute format('alter table public.%I enable row level security',t);
  execute format('revoke all on public.%I from anon,authenticated',t);
  execute format('grant select on public.%I to anon,authenticated',t);
  execute format('grant all on public.%I to service_role',t);
  execute format('create policy market_read on public.%I for select to anon,authenticated using(true)',t);
 end loop;
end $$;

create view public.candles_adjusted with(security_invoker=true) as
select c.symbol,c.exchange,c.timeframe,c.ts,
 c.open*coalesce(f.cum,1) as open,c.high*coalesce(f.cum,1) as high,
 c.low*coalesce(f.cum,1) as low,c.close*coalesce(f.cum,1) as close,
 c.volume/coalesce(f.cum,1) as volume,c.source,c.adjusted,c.fetched_at,
 (c.adjusted or f.cum is not null) as is_adjusted,coalesce(f.cum,1) as adjustment_factor
from public.candles c
left join lateral (
 select exp(sum(ln(a.factor))) as cum from public.adjustment_factors a
 where a.symbol=c.symbol and a.exchange=c.exchange and a.status='approved'
  and not c.adjusted -- Yahoo OHLC is already split-adjusted, even with auto_adjust=False.
  and a.ex_date>(c.ts at time zone 'Asia/Kolkata')::date
  and a.ex_date<=(select (max(last_c.ts) at time zone 'Asia/Kolkata')::date
    from public.candles last_c where last_c.symbol=c.symbol and last_c.exchange=c.exchange and last_c.timeframe=c.timeframe)
) f on true;
grant select on public.candles_adjusted to anon,authenticated,service_role;

-- Invoked by an authenticated server route after verifying the session and owner.
create function public.review_adjustment(p_symbol text,p_exchange text,p_date date,p_status text,p_actor uuid,p_note text)
returns boolean language plpgsql security invoker set search_path='' as $$
declare changed integer;
begin
 if not exists(select 1 from private.research_owner where user_id=p_actor) then raise exception 'Not owner'; end if;
 if p_status not in ('approved','rejected') or length(trim(p_note)) not between 3 and 1000 then
  raise exception 'Review decision and note required'; end if;
 update public.adjustment_factors set status=p_status,approved_by=p_actor::text,approved_at=now(),note=p_note
  where symbol=p_symbol and exchange=p_exchange and ex_date=p_date;
 get diagnostics changed=row_count;
 if changed=1 then
  insert into public.agent_events(run_id,module,action,status,symbol,output_summary,meta)
   values(gen_random_uuid(),'ingest','review_adjustment','success',p_symbol,
    'Human review: '||p_status,jsonb_build_object('ex_date',p_date,'decision',p_status,'reviewer',p_actor));
 end if;
 return changed=1;
end $$;
revoke all on function public.review_adjustment(text,text,date,text,uuid,text) from public,anon,authenticated;
grant execute on function public.review_adjustment(text,text,date,text,uuid,text) to service_role;
commit;
