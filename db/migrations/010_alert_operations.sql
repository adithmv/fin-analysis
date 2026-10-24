begin;
create function public.is_research_owner(p_user uuid) returns boolean
language sql security invoker set search_path='' as $$
 select exists(select 1 from private.research_owner where user_id=p_user);
$$;
create function public.database_size_bytes() returns bigint
language sql security invoker set search_path='' as $$ select pg_database_size(current_database()); $$;

-- One check result and one incident transition in the same transaction.
create function public.record_health(p_rule text,p_subject text,p_status text,p_value numeric,p_detail jsonb,
 p_severity text,p_message text) returns bigint
language plpgsql security invoker set search_path='' as $$
declare alert_id bigint; dedupe text := p_rule||':'||p_subject;
begin
 perform pg_advisory_xact_lock(hashtextextended('alert:'||dedupe,0));
 insert into public.health_checks(check_key,subject,status,value,detail)
 values(p_rule,p_subject,p_status,p_value,p_detail);
 select id into alert_id from public.alerts where dedupe_key=dedupe and status<>'resolved' for update;
 if p_status='ok' then
  update public.alerts set status='resolved',resolved_at=now(),meta=meta||jsonb_build_object('resolution_pending',notified_at is not null)
   where id=alert_id;
 elsif alert_id is null then
  insert into public.alerts(severity,rule_key,subject,message,dedupe_key,meta)
   values(p_severity,p_rule,p_subject,p_message,dedupe,p_detail) returning id into alert_id;
 else
  update public.alerts set severity=p_severity,message=p_message,meta=meta||p_detail where id=alert_id;
 end if;
 return alert_id;
end $$;

-- Reserve one outbound batch per interval across concurrent check/digest workers.
create function public.reserve_notification(p_key text,p_min_seconds integer) returns boolean
language plpgsql security invoker set search_path='' as $$
begin
 if p_min_seconds<60 then raise exception 'Minimum notification interval is 60 seconds'; end if;
 perform pg_advisory_xact_lock(hashtextextended('notification',0));
 if exists(select 1 from public.health_checks where check_key='notification_reserved'
  and ts>now()-make_interval(secs=>p_min_seconds)) then return false; end if;
 insert into public.health_checks(check_key,subject,status,detail)
  values('notification_reserved',p_key,'ok','{}');
 return true;
end $$;

create function public.owner_ops_action(p_actor uuid,p_action text,p_id bigint) returns boolean
language plpgsql security invoker set search_path='' as $$
declare changed boolean; affected integer;
begin
 if not public.is_research_owner(p_actor) then raise exception 'Not owner'; end if;
 if p_action in ('retry','cancel') then
  changed:=public.control_job(p_id,p_action);
 elsif p_action in ('acknowledge','resolve') then
  update public.alerts set status=case when p_action='acknowledge' then 'acknowledged' else 'resolved' end,
   resolved_at=case when p_action='resolve' then now() else resolved_at end
   where id=p_id and status<>'resolved';
  get diagnostics affected=row_count; changed:=affected=1;
 else raise exception 'Invalid operation'; end if;
 if changed then
  insert into public.agent_events(run_id,module,action,status,output_summary,meta)
   values(gen_random_uuid(),'scheduler','owner_action','success',p_action||' #'||p_id,
    jsonb_build_object('actor',p_actor,'target_id',p_id,'operation',p_action));
 end if;
 return changed;
end $$;
revoke all on function public.is_research_owner(uuid),public.database_size_bytes(),
 public.record_health(text,text,text,numeric,jsonb,text,text),public.reserve_notification(text,integer),
 public.owner_ops_action(uuid,text,bigint) from public,anon,authenticated;
grant execute on function public.is_research_owner(uuid),public.database_size_bytes(),
 public.record_health(text,text,text,numeric,jsonb,text,text),public.reserve_notification(text,integer),
 public.owner_ops_action(uuid,text,bigint) to service_role;
commit;
