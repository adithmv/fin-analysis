begin;
create extension if not exists vector with schema extensions;

-- Where news comes from, and how healthy each source is.
create table news_sources (
  source_key            text primary key,        -- e.g. 'moneycontrol_markets'
  name                  text not null,
  source_type           text not null check (source_type in ('rss','exchange_api','document')),
  url                   text,
  enabled               boolean not null default true,
  poll_interval_minutes integer not null default 30,
  etag                  text,                    -- for conditional requests
  last_modified         text,
  last_fetched_at       timestamptz,
  last_success_at       timestamptz,
  consecutive_failures  integer not null default 0,
  notes                 text
);

-- One row per distinct item collected. Titles, short summaries and links only.
create table articles (
  id                    uuid primary key default gen_random_uuid(),
  source_key            text not null references news_sources(source_key),
  url                   text not null,
  url_hash              text not null unique,     -- hash of the normalised URL
  title                 text not null,
  summary               text,                     -- feed snippet only, never full article text
  published_at          timestamptz,              -- as stated by the source, converted to UTC
  published_at_assumed  boolean not null default false,  -- true if we had to substitute fetched_at
  fetched_at            timestamptz not null default now(),
  language              text not null default 'en',
  title_hash            text not null,            -- hash of the normalised title
  dedupe_group_id       uuid,                     -- items that are the same story share this
  is_duplicate          boolean not null default false,
  external_id           text,                     -- exchange announcement id, if any
  processing            jsonb not null default '{}'::jsonb,
  raw                   jsonb not null default '{}'::jsonb
);
create index articles_published_idx  on articles (published_at desc);
create index articles_title_hash_idx on articles (title_hash);
create index articles_dedupe_idx     on articles (dedupe_group_id);
create index articles_source_idx     on articles (source_key, published_at desc);

-- Which stocks an article is about.
create table article_symbols (
  article_id      uuid not null references articles(id) on delete cascade,
  symbol          text not null,                  -- NSE symbol, or 'MARKET' for market-wide/macro items
  exchange        text not null default 'NSE',
  match_type      text not null check (match_type in
                    ('exchange_tag','company_name','alias','ticker','macro_rule')),
  confidence      numeric not null check (confidence >= 0 and confidence <= 1),
  matched_text    text,
  in_title        boolean not null default false,
  linker_version  text not null,
  primary key (article_id, symbol, exchange)
);
create index article_symbols_symbol_idx on article_symbols (symbol, exchange);

-- Sentiment of the text (one score per article in Phase 3).
create table article_sentiment (
  article_id     uuid not null references articles(id) on delete cascade,
  scope          text not null check (scope in ('title','title_summary')),
  model_key      text not null,                   -- e.g. 'prosusai/finbert'
  model_revision text not null default '',
  p_positive     numeric not null,
  p_negative     numeric not null,
  p_neutral      numeric not null,
  label          text not null check (label in ('positive','negative','neutral')),
  score          numeric not null,                -- p_positive - p_negative, range -1..1
  computed_at    timestamptz not null default now(),
  primary key (article_id, scope, model_key, model_revision)
);

-- Classified events (one article can contain events for one or more symbols).
create table news_events (
  id                      bigserial primary key,
  article_id              uuid not null references articles(id) on delete cascade,
  symbol                  text not null,
  exchange                text not null default 'NSE',
  event_type              text not null,          -- see config/news_events.yaml
  importance              smallint not null check (importance between 1 and 5),
  published_at            timestamptz,            -- first time this was public
  effective_trading_date  date,                   -- first session that opens AFTER published_at (see 7.6)
  classifier              text not null check (classifier in ('rules','exchange_category','llm')),
  matched_rule            text,
  details                 jsonb not null default '{}'::jsonb,
  logic_version           text not null,
  computed_at             timestamptz not null default now(),
  unique (article_id, symbol, event_type)
);
create index news_events_lookup_idx on news_events (symbol, event_type, published_at desc);

-- Semantic memory. One embedding model per table (see 7.8 about changing models).
create table article_embeddings (
  article_id   uuid not null references articles(id) on delete cascade,
  model_key    text not null check (model_key = 'sentence-transformers/all-MiniLM-L6-v2@1110a243fdf4706b3f48f1d95db1a4f5529b4d41'),
  embedding    extensions.vector(384) not null,              -- set to your chosen model's dimension
  text_basis   text not null default 'title_summary',
  computed_at  timestamptz not null default now(),
  primary key (article_id, model_key)
);
create index article_embeddings_hnsw
  on article_embeddings using hnsw (embedding extensions.vector_cosine_ops);

-- Official corporate actions: the cleanest historical events available for free.
create table corporate_actions (
  id            bigserial primary key,
  identity_key  text not null unique,
  symbol        text not null,
  exchange      text not null default 'NSE',
  action_type   text not null check (action_type in
                  ('dividend','split','bonus','rights','buyback','merger','demerger','other')),
  ex_date       date,
  record_date   date,
  announced_at  timestamptz,
  ratio_text    text,                             -- raw text as published, e.g. 'Bonus 1:1'
  parsed        jsonb,                            -- parsed ratio or amount, if parsing succeeded
  parse_status  text not null default 'unparsed'
                check (parse_status in ('unparsed','parsed','needs_review')),
  source        text not null,
  source_ref    text,
  fetched_at    timestamptz not null default now()
);
create unique index corporate_actions_uq
  on corporate_actions (symbol, exchange, action_type, coalesce(ex_date, date '1900-01-01'), source);
create index corporate_actions_symbol_idx on corporate_actions (symbol, ex_date desc);

alter table public.news_sources enable row level security;
revoke all on public.news_sources from anon, authenticated;
grant select on public.news_sources to anon, authenticated;
create policy read_news_sources on public.news_sources for select to anon, authenticated using (true);
grant select,insert,update,delete on public.news_sources to service_role;

alter table public.articles enable row level security;
revoke all on public.articles from anon, authenticated;
grant select on public.articles to anon, authenticated;
create policy read_articles on public.articles for select to anon, authenticated using (true);
grant select,insert,update,delete on public.articles to service_role;

alter table public.article_symbols enable row level security;
revoke all on public.article_symbols from anon, authenticated;
grant select on public.article_symbols to anon, authenticated;
create policy read_article_symbols on public.article_symbols for select to anon, authenticated using (true);
grant select,insert,update,delete on public.article_symbols to service_role;

alter table public.article_sentiment enable row level security;
revoke all on public.article_sentiment from anon, authenticated;
grant select on public.article_sentiment to anon, authenticated;
create policy read_article_sentiment on public.article_sentiment for select to anon, authenticated using (true);
grant select,insert,update,delete on public.article_sentiment to service_role;

alter table public.news_events enable row level security;
revoke all on public.news_events from anon, authenticated;
grant select on public.news_events to anon, authenticated;
create policy read_news_events on public.news_events for select to anon, authenticated using (true);
grant select,insert,update,delete on public.news_events to service_role;

alter table public.article_embeddings enable row level security;
revoke all on public.article_embeddings from anon, authenticated;
grant select on public.article_embeddings to anon, authenticated;
create policy read_article_embeddings on public.article_embeddings for select to anon, authenticated using (true);
grant select,insert,update,delete on public.article_embeddings to service_role;

alter table public.corporate_actions enable row level security;
revoke all on public.corporate_actions from anon, authenticated;
grant select on public.corporate_actions to anon, authenticated;
create policy read_corporate_actions on public.corporate_actions for select to anon, authenticated using (true);
grant select,insert,update,delete on public.corporate_actions to service_role;

grant usage,select on sequence public.news_events_id_seq,public.corporate_actions_id_seq to service_role;

commit;
