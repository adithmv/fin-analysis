-- Transactional acceptance drill: no model call and no rows retained.
begin;
do $$
declare r uuid := gen_random_uuid(); denied boolean;
begin
  perform reserve_agent_call(r,null,'drill','validation','fake',current_date,10,1,10,10,100);
  denied := false;
  begin
    perform reserve_agent_call(r,null,'drill','validation','fake',current_date,10,1,10,10,100);
  exception when others then
    if sqlerrm not like '%RUN_BUDGET%' then raise; end if;
    denied := true;
  end;
  if not denied then raise exception 'Run budget was not enforced'; end if;
  denied := false;
  begin
    perform reserve_agent_call(gen_random_uuid(),null,'drill','validation','fake',current_date,1,10,10,10,100);
  exception when others then
    if sqlerrm not like '%DAILY_BUDGET%' then raise; end if;
    denied := true;
  end;
  if not denied then raise exception 'Daily budget was not enforced'; end if;
  denied := false;
  begin
    perform reserve_agent_call(gen_random_uuid(),null,'drill','validation','fake',current_date,10,10,1,10,100);
  exception when others then
    if sqlerrm not like '%RATE_LIMIT%' then raise; end if;
    denied := true;
  end;
  if not denied then raise exception 'RPM budget was not enforced'; end if;
  denied := false;
  begin
    perform reserve_agent_call(gen_random_uuid(),null,'drill','validation','fake',current_date,10,10,10,10,15);
  exception when others then
    if sqlerrm not like '%RATE_LIMIT%' then raise; end if;
    denied := true;
  end;
  if not denied then raise exception 'TPM budget was not enforced'; end if;
  denied := false;
  begin
    perform reserve_agent_call(gen_random_uuid(),null,'drill','validation','fake',current_date,10,10,10,101,100);
  exception when others then
    if sqlerrm not like '%PROMPT_TOO_LARGE%' then raise; end if;
    denied := true;
  end;
  if not denied then raise exception 'Prompt budget was not enforced'; end if;
end $$;
select 'Run, daily, RPM, TPM and oversized prompt checks passed' as result;
rollback;
