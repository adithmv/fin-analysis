begin;
-- Synthetic symbols never survive this transaction; not approvals of real actions.
insert into public.candles(symbol,ts,open,high,low,close,volume,source,adjusted)
select symbol,day::timestamp at time zone 'Asia/Kolkata',100,110,90,100,1000,'fixture',already
from (values ('__BONUS',false),('__SPLIT',false),('__TWO',false),('__NONE',false),('__FUTURE',false),('__YAHOO',true)) s(symbol,already)
cross join (values (date '2024-01-01'),(date '2024-01-02'),(date '2024-01-03')) d(day);
insert into public.adjustment_factors(symbol,ex_date,factor,status,approved_by,approved_at)
values ('__BONUS','2024-01-02',0.5,'approved','fixture',now()),
 ('__SPLIT','2024-01-02',0.2,'approved','fixture',now()),
 ('__TWO','2024-01-02',0.5,'approved','fixture',now()),
 ('__TWO','2024-01-03',0.2,'approved','fixture',now()),
 ('__FUTURE','2024-01-04',0.5,'approved','fixture',now()),
 ('__YAHOO','2024-01-02',0.5,'approved','fixture',now());
do $$ declare r record; expected numeric; begin
 for r in select * from public.candles_adjusted where symbol in ('__BONUS','__SPLIT','__TWO','__NONE','__FUTURE','__YAHOO') loop
  expected := case when (r.ts at time zone 'Asia/Kolkata')::date='2024-01-01' then
    case r.symbol when '__BONUS' then 0.5 when '__SPLIT' then 0.2 when '__TWO' then 0.1 else 1 end
   when (r.ts at time zone 'Asia/Kolkata')::date='2024-01-02' and r.symbol='__TWO' then 0.2 else 1 end;
  if abs(r.close-100*expected)>0.000001 or abs(r.open-100*expected)>0.000001
    or abs(r.high-110*expected)>0.000001 or abs(r.low-90*expected)>0.000001
    or abs(r.volume-1000/expected)>0.000001 then raise exception 'Adjustment mismatch for % %',r.symbol,r.ts; end if;
 end loop;
end $$;
select 'Passed: bonus, split, sequential factors, ex-date boundary, future action, unchanged series, inverse volume, no double adjustment' as result;
rollback;
