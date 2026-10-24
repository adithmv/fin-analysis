-- Transactional contract checks: no jobs, alerts or data survive the rollback.
begin;
do $$
declare a public.jobs; b public.jobs; d public.jobs; n integer; old_run uuid;
begin
 perform public.enqueue_pipeline('contract:queue',now(), '[
  {"name":"first","module":"contract","kind":"test"},
  {"name":"second","module":"contract","kind":"test","after":["first"]},
  {"name":"third","module":"contract","kind":"test","after":["second"]},
  {"name":"digest","module":"contract","kind":"test","after":["third"],"dependency_mode":"finished"}]');
 perform public.enqueue_pipeline('contract:queue',now(), '[{"name":"duplicate","module":"contract","kind":"test"}]');
 select count(*) into n from public.jobs where pipeline_run='contract:queue';
 if n<>4 then raise exception 'Idempotency failed'; end if;
 select * into a from public.claim_job('worker-a');
 if a.kind<>'test' or a.attempts<>1 then raise exception 'Claim failed'; end if;
 select count(*) into n from public.claim_job('worker-b');
 if n<>0 then raise exception 'Dependency/module exclusivity failed'; end if;
 if public.finish_job(a.id,a.run_id,'wrong-worker',0,'wrong') then raise exception 'Owner fencing failed'; end if;
 if not public.finish_job(a.id,a.run_id,'worker-a',1,'forced failure') then raise exception 'Finish failed'; end if;
 select * into b from public.jobs where id=a.id;
 if b.status<>'queued' or b.scheduled_for<=now() then raise exception 'Backoff failed'; end if;
 update public.jobs set scheduled_for=now() where id=a.id;
 select * into b from public.claim_job('worker-b');
 if b.run_id=a.run_id or b.attempts<>2 then raise exception 'Attempt fencing failed'; end if;
 if public.heartbeat_job(a.id,a.run_id,'worker-a') then raise exception 'Old heartbeat accepted'; end if;
 if public.finish_job(a.id,a.run_id,'worker-a',0,'late') then raise exception 'Late finish accepted'; end if;
 old_run:=b.run_id;
 update public.jobs set heartbeat_at=now()-interval '11 minutes' where id=b.id;
 perform public.recover_jobs();
 select * into b from public.jobs where id=a.id;
 if b.status<>'queued' then raise exception 'Lease recovery failed'; end if;
 update public.jobs set scheduled_for=now() where id=a.id;
 select * into b from public.claim_job('worker-c');
 if b.attempts<>3 or b.run_id=old_run then raise exception 'Recovery reclaim failed'; end if;
 perform public.finish_job(b.id,b.run_id,'worker-c',1,'terminal failure');
 perform public.recover_jobs();
 select count(*) into n from public.jobs where pipeline_run='contract:queue' and status='skipped';
 if n<>2 then raise exception 'Transitive failure propagation failed'; end if;
 select * into d from public.claim_job('digest-worker');
 if d.idempotency_key<>'contract:queue:digest' then raise exception 'Failure digest did not run'; end if;
 perform public.control_job(d.id,'cancel');
 if public.heartbeat_job(d.id,d.run_id,'digest-worker') then raise exception 'Cancellation not fenced'; end if;
 if not public.control_job(a.id,'retry') then raise exception 'Explicit retry failed'; end if;
 select * into b from public.jobs where id=a.id;
 if b.attempts<>0 or b.status<>'queued' then raise exception 'Retry state failed'; end if;
 if has_function_privilege('anon','public.claim_job(text)','execute') or
    has_function_privilege('authenticated','public.control_job(bigint,text)','execute') or
    has_table_privilege('authenticated','public.jobs','update') or
    has_table_privilege('anon','public.documents','select') then raise exception 'Access control failed'; end if;
end $$;
select 'Queue contract passed: idempotency, ownership, retry, lease recovery, dependencies, digest and permissions' as result;
rollback;
