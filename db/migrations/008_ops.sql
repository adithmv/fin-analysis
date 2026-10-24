begin;

create table public.jobs (
 id bigserial primary key, module text not null, kind text not null,
 params jsonb not null default '{}' check(jsonb_typeof(params)='object'),
 status text not null default 'queued' check(status in ('queued','running','succeeded','failed','dead','cancelled','skipped')),
 priority smallint not null default 5, idempotency_key text not null unique,
 pipeline_run text, depends_on bigint[] not null default '{}',
 dependency_mode text not null default 'succeeded' check(dependency_mode in ('succeeded','finished')),
 scheduled_for timestamptz not null default now(), attempts smallint not null default 0,
 max_attempts smallint not null default 3 check(max_attempts between 1 and 10),
 locked_by text, locked_at timestamptz, heartbeat_at timestamptz, run_id uuid,
 exit_code integer, last_error text, created_by text not null check(created_by in ('scheduler','user','module')),
 created_at timestamptz not null default now(), started_at timestamptz, finished_at timestamptz,
 result_summary text
);
create index jobs_claim_idx on public.jobs(status,priority,scheduled_for);
create index jobs_module_idx on public.jobs(module,status);
create index jobs_pipeline_idx on public.jobs(pipeline_run);

create table public.documents (
 id uuid primary key default gen_random_uuid(), job_id bigint references public.jobs(id) on delete set null,
 url text not null, domain text not null, title text, content_type text, text text,
 text_hash text, file_path text,
 extraction_method text not null check(extraction_method in ('recipe','agent','pdf')),
 trust_level text not null default 'untrusted' check(trust_level in ('untrusted','reviewed')),
 linked_symbols text[], published_at timestamptz, fetched_at timestamptz not null default now(),
 status text not null default 'ok' check(status in ('ok','partial','blocked','failed')),
 meta jsonb not null default '{}'
);
create unique index documents_url_hash_uq on public.documents(url,text_hash);
create index documents_domain_idx on public.documents(domain,fetched_at desc);
create index documents_job_idx on public.documents(job_id);
create table public.alerts (
 id bigserial primary key, ts timestamptz not null default now(),
 severity text not null check(severity in ('info','warning','critical')),
 rule_key text not null, subject text, message text not null, dedupe_key text not null,
 status text not null default 'open' check(status in ('open','acknowledged','resolved')),
 notified_at timestamptz, resolved_at timestamptz, meta jsonb not null default '{}'
);
-- Acknowledging does not create a new incident every ten minutes.
create unique index alerts_active_dedupe_uq on public.alerts(dedupe_key) where status <> 'resolved';
create table public.health_checks (
 id bigserial primary key, ts timestamptz not null default now(), check_key text not null,
 subject text, status text not null check(status in ('ok','warn','fail')), value numeric,
 detail jsonb not null default '{}'
);
create index health_checks_lookup_idx on public.health_checks(check_key,subject,ts desc);

do $$ declare t text; begin
 foreach t in array array['jobs','documents','alerts','health_checks'] loop
  execute format('alter table public.%I enable row level security',t);
  execute format('revoke all on public.%I from anon,authenticated',t);
  execute format('grant select on public.%I to authenticated',t);
  execute format('grant all on public.%I to service_role',t);
  execute format('create policy owner_read on public.%I for select to authenticated using (exists(select 1 from private.research_owner where user_id=(select auth.uid())))',t);
 end loop;
end $$;
grant usage,select on sequence public.jobs_id_seq,public.alerts_id_seq,public.health_checks_id_seq to service_role;

-- Insert a complete DAG transactionally. Earlier stage names only: no cycles or missing edges.
create function public.enqueue_pipeline(p_key text,p_at timestamptz,p_stages jsonb)
returns setof public.jobs language plpgsql security invoker set search_path='' as $$
declare s jsonb; ids jsonb := '{}'; deps bigint[]; stage_id bigint; stage_name text;
begin
 perform pg_advisory_xact_lock(hashtextextended('pipeline:'||p_key,0));
 if exists(select 1 from public.jobs where pipeline_run=p_key) then
  return query select * from public.jobs where pipeline_run=p_key order by id; return;
 end if;
 if jsonb_typeof(p_stages)<>'array' or jsonb_array_length(p_stages) not between 1 and 50 then
  raise exception 'Invalid stages'; end if;
 for s in select value from jsonb_array_elements(p_stages) loop
  stage_name := s->>'name';
  if stage_name is null or stage_name !~ '^[a-z0-9_-]{1,60}$' or ids ? stage_name then
   raise exception 'Invalid or duplicate stage'; end if;
  if exists(select 1 from jsonb_array_elements_text(coalesce(s->'after','[]')) d where not ids ? d) then
   raise exception 'Dependencies must name earlier stages'; end if;
  select coalesce(array_agg((ids->>d)::bigint),'{}') into deps
   from jsonb_array_elements_text(coalesce(s->'after','[]')) d;
  insert into public.jobs(module,kind,params,idempotency_key,pipeline_run,depends_on,dependency_mode,scheduled_for,created_by,status,result_summary)
   values(s->>'module',s->>'kind',coalesce(s->'params','{}'),p_key||':'||stage_name,p_key,deps,
    coalesce(s->>'dependency_mode','succeeded'),p_at,'scheduler',coalesce(s->>'status','queued'),s->>'result_summary')
   returning id into stage_id;
  ids := ids || jsonb_build_object(stage_name,stage_id);
 end loop;
 return query select * from public.jobs where pipeline_run=p_key order by id;
end $$;

create function public.claim_job(p_worker text) returns setof public.jobs
language plpgsql security invoker set search_path='' as $$
begin
 -- Serialise the short claim decision to exclude simultaneous jobs in one module.
 perform pg_advisory_xact_lock(hashtextextended('job_claim',0));
 return query update public.jobs set status='running',locked_by=p_worker,locked_at=now(),heartbeat_at=now(),
  attempts=attempts+1,run_id=gen_random_uuid(),started_at=now(),finished_at=null,exit_code=null
 where id=(select j.id from public.jobs j where j.status='queued' and j.scheduled_for<=now()
  and j.attempts<j.max_attempts
  and not exists(select 1 from public.jobs r where r.module=j.module and r.status='running')
  and not exists(select 1 from unnest(j.depends_on) dep left join public.jobs d on d.id=dep
   where d.id is null or case when j.dependency_mode='finished'
    then d.status not in ('succeeded','skipped','dead','cancelled','failed')
    else d.status not in ('succeeded','skipped') or (d.status='skipped' and d.last_error is not null) end)
 order by j.priority,j.scheduled_for,j.id for update skip locked limit 1) returning *;
end $$;

create function public.heartbeat_job(p_id bigint,p_run uuid,p_worker text) returns boolean
language sql security invoker set search_path='' as $$
 with changed as(update public.jobs set heartbeat_at=now() where id=p_id and run_id=p_run
  and locked_by=p_worker and status='running' returning id) select exists(select 1 from changed);
$$;
create function public.finish_job(p_id bigint,p_run uuid,p_worker text,p_exit integer,p_summary text)
returns boolean language sql security invoker set search_path='' as $$
 with changed as(update public.jobs set
  status=case when p_exit=0 then 'succeeded' when attempts<max_attempts then 'queued' else 'dead' end,
  exit_code=p_exit,result_summary=left(p_summary,2000),last_error=case when p_exit<>0 then left(p_summary,2000) end,
  finished_at=case when p_exit=0 or attempts>=max_attempts then now() end,
  scheduled_for=case when p_exit<>0 then now()+make_interval(secs=>least(3600,60*power(2,attempts-1)::integer)) else scheduled_for end,
  locked_by=null,locked_at=null,heartbeat_at=null
 where id=p_id and run_id=p_run and locked_by=p_worker and status='running' returning id)
 select exists(select 1 from changed);
$$;
create function public.recover_jobs() returns setof public.jobs
language plpgsql security invoker set search_path='' as $$
declare changed integer;
begin
 return query update public.jobs set status=case when attempts<max_attempts then 'queued' else 'dead' end,
  scheduled_for=now()+interval '1 minute',last_error='Runner heartbeat expired; previous attempt fenced',
  finished_at=case when attempts>=max_attempts then now() end,locked_by=null,locked_at=null,heartbeat_at=null
 where status='running' and heartbeat_at<now()-interval '10 minutes' returning *;
 loop
  return query update public.jobs j set status='skipped',finished_at=now(),last_error='Dependency failed or was cancelled',
   result_summary='Not executed: required stage did not succeed'
  where j.status='queued' and j.dependency_mode='succeeded'
   and exists(select 1 from public.jobs d where d.id=any(j.depends_on)
    and (d.status in ('dead','cancelled','failed') or (d.status='skipped' and d.last_error is not null))) returning j.*;
  get diagnostics changed = row_count;
  exit when changed=0;
 end loop;
end $$;

-- Retry is an explicit new attempt allowance on a terminal job, never a running job.
create function public.control_job(p_id bigint,p_action text) returns boolean
language plpgsql security invoker set search_path='' as $$
declare changed integer;
begin
 if p_action='cancel' then
  update public.jobs set status='cancelled',finished_at=now(),last_error='Cancelled by owner'
   where id=p_id and status in ('queued','running');
 elsif p_action='retry' then
  update public.jobs set status='queued',attempts=0,scheduled_for=now(),finished_at=null,locked_by=null,
   locked_at=null,heartbeat_at=null,run_id=null,last_error=null
   where id=p_id and status in ('dead','failed','cancelled','skipped');
 else raise exception 'Invalid job action'; end if;
 get diagnostics changed = row_count;
 return changed=1;
end $$;

revoke all on function public.enqueue_pipeline(text,timestamptz,jsonb),public.claim_job(text),
 public.heartbeat_job(bigint,uuid,text),public.finish_job(bigint,uuid,text,integer,text),
 public.recover_jobs(),public.control_job(bigint,text) from public,anon,authenticated;
grant execute on function public.enqueue_pipeline(text,timestamptz,jsonb),public.claim_job(text),
 public.heartbeat_job(bigint,uuid,text),public.finish_job(bigint,uuid,text,integer,text),
 public.recover_jobs(),public.control_job(bigint,text) to service_role;
commit;
