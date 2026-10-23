begin;
alter table public.articles add column provenance jsonb not null default '{}'::jsonb;

create function public.replace_article_analysis(p_article uuid,p_links jsonb,p_events jsonb,p_processing jsonb)
returns void language plpgsql security invoker set search_path='' as $$
begin
 perform 1 from public.articles where id=p_article for update;
 if not found then raise exception 'Article not found'; end if;
 if p_links is not null then
  delete from public.article_symbols where article_id=p_article;
  insert into public.article_symbols select * from jsonb_populate_recordset(null::public.article_symbols,p_links);
 end if;
 if p_events is not null then
  delete from public.news_events where article_id=p_article;
  insert into public.news_events(article_id,symbol,exchange,event_type,importance,published_at,effective_trading_date,classifier,matched_rule,details,logic_version)
  select article_id,symbol,exchange,event_type,importance,published_at,effective_trading_date,classifier,matched_rule,details,logic_version
  from jsonb_populate_recordset(null::public.news_events,p_events);
 end if;
 update public.articles set processing=processing||p_processing where id=p_article;
end $$;
revoke all on function public.replace_article_analysis(uuid,jsonb,jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.replace_article_analysis(uuid,jsonb,jsonb,jsonb) to service_role;

create function public.search_news(query_embedding extensions.vector(384),requested_model text,result_limit integer default 10,filter_symbol text default null,from_date timestamptz default null,to_date timestamptz default null,filter_event text default null)
returns table(article_id uuid,title text,summary text,url text,source_key text,published_at timestamptz,similarity double precision)
language sql stable security invoker set search_path='' as $$
 select a.id,a.title,a.summary,a.url,a.source_key,a.published_at,
  1-(e.embedding operator(extensions.<=>) query_embedding) as similarity
 from public.article_embeddings e join public.articles a on a.id=e.article_id
 where e.model_key=requested_model and not a.is_duplicate
 and (filter_symbol is null or exists(select 1 from public.article_symbols s where s.article_id=a.id and s.symbol=filter_symbol))
 and (from_date is null or a.published_at>=from_date)
 and (to_date is null or a.published_at<to_date)
 and (filter_event is null or exists(select 1 from public.news_events n where n.article_id=a.id and n.event_type=filter_event))
 order by e.embedding operator(extensions.<=>) query_embedding,a.id
 limit greatest(1,least(result_limit,50));
$$;
revoke all on function public.search_news(extensions.vector,text,integer,text,timestamptz,timestamptz,text) from public;
grant execute on function public.search_news(extensions.vector,text,integer,text,timestamptz,timestamptz,text) to anon,authenticated,service_role;

create view public.news_source_health with (security_invoker=true) as
select s.*,
 (select count(*) from public.articles a where a.source_key=s.source_key and a.fetched_at>now()-interval '24 hours') as items_24h,
 (select count(*) from public.articles a where a.source_key=s.source_key and a.fetched_at>now()-interval '7 days') as items_7d,
 (select avg(a.is_duplicate::int)::numeric from public.articles a where a.source_key=s.source_key) as duplicate_rate,
 (select avg(a.published_at_assumed::int)::numeric from public.articles a where a.source_key=s.source_key) as assumed_time_rate,
 (select avg((exists(select 1 from public.article_symbols l where l.article_id=a.id and l.symbol<>'MARKET'))::int)::numeric from public.articles a where a.source_key=s.source_key) as link_coverage,
 (select max(a.published_at) from public.articles a where a.source_key=s.source_key) as newest_publication
from public.news_sources s;
grant select on public.news_source_health to anon,authenticated,service_role;

create index article_symbols_article_idx on public.article_symbols(article_id);
create index articles_fetched_idx on public.articles(source_key,fetched_at desc);
commit;
