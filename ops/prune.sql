-- DRY RUN ONLY. These are candidates, never an authorization to delete.
-- Success events need daily aggregation before any future deletion implementation.
-- Preserve event references embedded in messages as well as reservation foreign keys.
begin transaction read only;
select 'agent_events_success' as category,count(*) as candidate_rows
from public.agent_events e
where e.ts < now()-interval '90 days' and e.status='success'
  and not exists(select 1 from public.agent_call_reservations r where r.event_id=e.id)
  and not exists(select 1 from public.messages m where e.id=any(m.event_ids))
union all
select 'health_checks',count(*) from public.health_checks h
where h.ts < now()-interval '30 days'
  and exists(select 1 from public.health_checks newer
    where newer.check_key=h.check_key and newer.subject is not distinct from h.subject and newer.ts>h.ts)
union all
select 'terminal_jobs',count(*) from public.jobs j
where j.finished_at < now()-interval '90 days' and j.status in ('succeeded','failed','dead','cancelled','skipped')
  and not exists(select 1 from public.jobs dependent where j.id=any(dependent.depends_on))
  and not exists(select 1 from public.documents d where d.job_id=j.id)
union all
select 'article_raw_fields',count(*) from public.articles
where fetched_at < now()-interval '90 days' and raw<>'{}'::jsonb;
rollback;
