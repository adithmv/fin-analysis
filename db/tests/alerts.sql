begin;
do $$ declare first_id bigint; second_id bigint; begin
 first_id:=public.record_health('fixture','test','warn',1,'{}','warning','Test');
 update public.alerts set status='acknowledged' where id=first_id;
 second_id:=public.record_health('fixture','test','warn',1,'{}','warning','Still failing');
 if first_id<>second_id then raise exception 'Acknowledgement lost deduplication'; end if;
 perform public.record_health('fixture','test','ok',0,'{}','warning','Cleared');
 if (select status from public.alerts where id=first_id)<>'resolved' then raise exception 'Resolution failed'; end if;
 if public.is_research_owner('00000000-0000-0000-0000-000000000001') then raise exception 'Nonowner accepted'; end if;
 if has_function_privilege('authenticated','public.owner_ops_action(uuid,text,bigint)','execute') then raise exception 'Browser write allowed'; end if;
 if has_function_privilege('anon','public.record_health(text,text,text,numeric,jsonb,text,text)','execute') then raise exception 'Anonymous write allowed'; end if;
end $$;
set local role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000001',true);
do $$ begin
 if exists(select 1 from public.alerts) or exists(select 1 from public.jobs) then raise exception 'Nonowner can read operations'; end if;
end $$;
reset role;
select 'Passed: incident deduplication, resolution, nonowner isolation, no browser mutation grants' as result;
rollback;
