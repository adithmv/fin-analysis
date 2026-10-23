# Phase 3: News, Events and Memory

> Part of the Indian Stock Market Research & Analytics Tool.
> Read `PROJECT_OVERVIEW.md`, `PHASE_1.md` and `PHASE_2.md` first. Phases 1 and 2 must be complete before starting this phase.
> This file is the complete specification for Phase 3. An AI agent or developer should be able to build Phase 3 from this file alone.

---

## 1. Goal

Give the system a **memory of what has been happening** around each stock and the market, and measure honestly whether that news ever mattered.

Phase 3 builds a pipeline that:

1. **Collects** news (RSS feeds) and **official exchange announcements and corporate actions** (dividends, splits, bonuses and so on) for the watchlist.
2. **Cleans** them: removes duplicates, normalises timestamps, links each item to the right stocks (or to "MARKET" for macro news).
3. **Understands** them: sentiment scoring and event-type classification (results, dividend, board meeting, regulatory action and so on).
4. **Remembers** them: stores embeddings so you can search by meaning ("what happened last time the RBI changed rates?").
5. **Tests** them: reuses the Phase 2 event-study method to measure what prices did after each event type and each sentiment level, compared with a baseline.
6. **Shows** them: a news feed, stock-page news panel, sentiment timeline and semantic search on the dashboard.

Phase 3 deliberately uses **no cloud LLM and no paid API**. Sentiment, linking, classification and embeddings all run locally with free models and rules. Phase 4 agents will later read these tables as their evidence.

### An honest note about "old news"

Free news RSS feeds mostly expose only **recent** items (often the last few dozen). There is no free, legal way to bulk-download years of past articles from the major news sites. So:

- **News articles:** your archive starts the day you start collecting and grows over time. After 6 to 12 months it becomes a real history.
- **Exchange announcements and corporate actions:** these can usually be fetched going back further (many libraries paginate through history; verify how far back each one goes). They are structured, reliable, and the best "old news" you can get for free. They are the main historical evidence for event studies in this phase.
- Do not promise yourself a rich news history on day one. The system is designed so that history accumulates automatically.

---

## 2. Scope

### In scope
- `news/` module: feed collection, exchange announcements, corporate actions, normalisation, de-duplication, entity linking, sentiment, event classification, embeddings, semantic search, health reporting.
- Database migration(s): `news_sources`, `articles`, `article_symbols`, `article_sentiment`, `news_events`, `article_embeddings`, `corporate_actions`, plus small additions to `watchlist` and `signal_stats`.
- Index (benchmark) data in the existing ingest module (configuration plus verification of source support).
- `backtest/` extension: event studies on news events and sentiment buckets (reads tables only).
- Dashboard additions: news feed, article detail, stock-page news panel and sentiment timeline, semantic search, corporate actions view, source-health view.
- A small hand-labelled "gold set" to measure linking, sentiment and event accuracy.
- Tests, failure drills, READMEs.

### Out of scope (do NOT build in Phase 3)
- LLM agents, discussion threads (Phase 4).
- Browser agent, full-article scraping, scheduling, alerts (Phase 5). Phase 3 stores titles, short summaries and links only.
- Sentiment targeted at a specific company within a multi-company article (one score per article in Phase 3).
- Social media, forums, Telegram or Twitter/X sources.
- Non-English news (the sentiment model is English-only).
- Fundamentals data (balance sheets, ratios).
- Any paid service, paid news API or paid model API.
- Any trading or order function. Ever.

---

## 3. Prerequisites

| Item | Notes |
|---|---|
| Phases 1 and 2 done | Candles, signals, `signal_stats` and the backtest module working. |
| Python | 3.11 or newer for this module (at least one useful exchange library needs 3.11+). Own virtual environment. |
| Disk space | The FinBERT model file is roughly 440 MB, plus an embedding model and Python ML dependencies. Budget several GB. |
| CPU | Sentiment and embeddings run on CPU. Headlines are short, so a normal laptop is fine when processing in batches. |
| pgvector | Supabase Postgres supports the `vector` extension. Verify it is enabled for your project before the migration. |
| Free database size | Check your Supabase free-tier database size limit now. News and embeddings are the first tables that can grow large (see section 14). |

### Libraries and sources to evaluate (all free; verify current state before depending on them)

| Purpose | Candidate | Notes |
|---|---|---|
| RSS parsing | `feedparser` | Mature, standard choice. |
| News feeds | Moneycontrol, Livemint (markets), Business Standard (markets), The Hindu (markets) RSS | Seen listed in public RSS directories. Economic Times RSS and others may also exist. **Confirm every URL works before adding it.** Feeds move and disappear. |
| Exchange announcements and corporate actions | `dalal` (unified NSE and BSE Python library, requires Python 3.11+, no API keys) | Lists announcements, corporate actions (dividends, splits, bonuses), bulk and block deals, shareholding, holidays and more. Documents its own rate limits (NSE about 3 requests per second, BSE about 8). |
| Exchange announcements (BSE) | `bse` (unofficial BSE Python API) | Has paginated announcements and corporate actions. A second source for cross-checking. |
| Sentiment | `ProsusAI/finbert` on Hugging Face (via `transformers`) | Three labels: positive, negative, neutral. English only. Verify the model licence before relying on it beyond personal use. |
| Embeddings | A small `sentence-transformers` model that runs locally | Pick one, note its output dimension (many small models use 384) and put it in config. |
| Near-duplicate matching | `rapidfuzz` (or similar) | For title similarity. |

All exchange libraries are **unofficial** and scrape or call website back-ends. They can break when the exchange changes its site. The same fallback, caching and logbook habits from Phase 1 apply.

---

## 4. Repository changes

```
market-research/
├── config/
│   ├── feeds.yaml                # NEW: news sources and polling rules
│   ├── news_events.yaml          # NEW: event-type rules
│   ├── aliases.yaml              # NEW: company name and alias dictionary
│   └── news.yaml                 # NEW: models, thresholds, batch sizes
├── db/
│   └── migrations/
│       ├── 004_news.sql          # NEW
│       └── 005_phase3_alters.sql # NEW: watchlist.kind, signal_stats columns
├── news/                         # filled in
│   ├── README.md
│   ├── requirements.txt
│   ├── main.py
│   ├── collect/
│   │   ├── rss.py                # feed polling with conditional requests
│   │   ├── announcements.py      # NSE/BSE announcements
│   │   └── corporate_actions.py
│   ├── normalize.py              # URL cleaning, timestamps, hashing, de-duplication
│   ├── linking/
│   │   ├── aliases.py
│   │   └── linker.py
│   ├── events/
│   │   └── classifier.py         # rule-based event types and importance
│   ├── scoring/
│   │   └── sentiment.py          # FinBERT
│   ├── embeddings/
│   │   └── embedder.py
│   ├── search.py                 # semantic search
│   ├── health.py                 # source health report
│   └── tests/
│       └── gold/                 # hand-labelled headlines
├── backtest/
│   └── event_sources/            # NEW: news-event and sentiment adapters for the event study
└── dashboard/                    # extended (section 11)
```

`news/` keeps its own dependency file and environment. It never imports other modules (only `shared/`). The `backtest` extension reads the new tables and never imports `news/`.

---

## 5. Database design

Same conventions as before: timestamps in UTC `timestamptz`; writes are idempotent (upsert or unique constraints); read-only RLS for the browser; writes only from Python with the service key.

### 5.1 `004_news.sql`

```sql
create extension if not exists vector;

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
  model_revision text,
  p_positive     numeric not null,
  p_negative     numeric not null,
  p_neutral      numeric not null,
  label          text not null check (label in ('positive','negative','neutral')),
  score          numeric not null,                -- p_positive - p_negative, range -1..1
  computed_at    timestamptz not null default now(),
  primary key (article_id, scope, model_key)
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
  model_key    text not null,
  embedding    vector(384) not null,              -- set to your chosen model's dimension
  text_basis   text not null default 'title_summary',
  computed_at  timestamptz not null default now(),
  primary key (article_id, model_key)
);
create index article_embeddings_hnsw
  on article_embeddings using hnsw (embedding vector_cosine_ops);

-- Official corporate actions: the cleanest historical events available for free.
create table corporate_actions (
  id            bigserial primary key,
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
```

### 5.2 `005_phase3_alters.sql`

New numbered migration that **adds nullable columns only**. No existing column changes meaning.

```sql
-- Allow index/benchmark rows (e.g. 'NIFTY 50') next to stocks.
alter table watchlist add column if not exists kind text not null default 'equity'
  check (kind in ('equity','index'));

-- News events have no inherent direction, so we also measure how much prices MOVE.
alter table signal_stats add column if not exists mean_abs_return    numeric;
alter table signal_stats add column if not exists baseline_mean_abs  numeric;
alter table signal_stats add column if not exists abnormal           boolean not null default false;
-- 'abnormal' = returns are market-adjusted (stock return minus benchmark return)
```

### 5.3 Conventions that matter

- `published_at` is always UTC. Indian sources usually publish in IST (UTC+5:30). Parsing mistakes here silently ruin the event studies, so see 7.3.
- `symbol = 'MARKET'` marks market-wide items (RBI, budget, global markets). It is not a tradable symbol.
- `signal_stats` is reused for news studies: `signal_key` values look like `news:earnings_result` or `sentiment:very_negative`. This keeps one results table for the dashboard.
- The embedding `vector(N)` dimension must match the model. See 7.8 for how to change models safely.

### 5.4 Realtime and access
- Enable Realtime on `articles` only if you want a live news ticker. Otherwise read on demand.
- Read-only RLS policies on all new tables. No browser writes.

---

## 6. Configuration

### 6.1 `config/feeds.yaml`

```yaml
user_agent: "personal-market-research/1.0 (contact: your-email@example.com)"
default_poll_interval_minutes: 30
timeout_seconds: 20
max_consecutive_failures_before_disable: 5

sources:
  - key: moneycontrol_markets
    name: Moneycontrol - Markets
    type: rss
    url: "<VERIFY AND FILL IN>"
    tier: 1                 # 1 = most trusted, 3 = least; used in importance scoring
    enabled: true
  - key: livemint_markets
    name: Livemint - Markets
    type: rss
    url: "<VERIFY AND FILL IN>"
    tier: 1
    enabled: true
  - key: business_standard_markets
    name: Business Standard - Markets
    type: rss
    url: "<VERIFY AND FILL IN>"
    tier: 1
    enabled: true
  - key: thehindu_markets
    name: The Hindu - Markets
    type: rss
    url: "<VERIFY AND FILL IN>"
    tier: 2
    enabled: true
  - key: nse_announcements
    name: NSE corporate announcements
    type: exchange_api
    tier: 0                 # official source
    enabled: true
  - key: bse_announcements
    name: BSE corporate announcements
    type: exchange_api
    tier: 0
    enabled: true
```

The URLs are intentionally left as placeholders. The builder must find and test each one, because feed addresses change.

### 6.2 `config/news.yaml`

```yaml
sentiment:
  model: "ProsusAI/finbert"
  scope: title_summary          # 'title' or 'title_summary'
  batch_size: 16
  max_tokens: 512               # truncate longer inputs
  buckets:                      # thresholds on score = p_positive - p_negative
    very_negative: -0.6
    negative: -0.2
    positive: 0.2
    very_positive: 0.6

embeddings:
  model: "<chosen sentence-transformers model>"
  dimension: 384                # must match the migration
  embed_only_if_linked: true    # saves database space (see section 14)

dedupe:
  title_similarity_threshold: 0.92
  window_hours: 48

linking:
  min_confidence_to_store: 0.5
  min_confidence_for_events: 0.7

processing:
  linker_version: "1.0.0"
  events_logic_version: "1.0.0"

retention:
  keep_raw_days: 90             # raw jsonb is cleared after this; titles and scores stay
```

### 6.3 `config/aliases.yaml`

One entry per watchlist stock. Aliases are what makes linking work.

```yaml
RELIANCE:
  names: ["Reliance Industries", "Reliance Industries Ltd"]
  aliases: ["RIL", "Reliance"]
  ambiguous_aliases: ["Reliance"]     # also matches other 'Reliance ...' companies; require extra evidence
TCS:
  names: ["Tata Consultancy Services"]
  aliases: ["TCS"]
INFY:
  names: ["Infosys", "Infosys Ltd"]
  aliases: ["Infy"]
```

### 6.4 `config/news_events.yaml`

```yaml
logic_version: "1.0.0"

event_types:
  earnings_result:
    importance: 4
    patterns: ["quarterly results", "Q1 results", "Q2 results", "Q3 results", "Q4 results",
               "net profit", "net loss", "reports profit", "PAT"]
  dividend:
    importance: 3
    patterns: ["dividend", "record date"]
  bonus_split:
    importance: 3
    patterns: ["bonus issue", "stock split", "sub-division"]
  board_meeting:
    importance: 2
    patterns: ["board meeting", "board to consider"]
  merger_acquisition:
    importance: 4
    patterns: ["acquires", "acquisition", "merger", "demerger", "stake sale", "stake purchase"]
  fundraise:
    importance: 3
    patterns: ["QIP", "rights issue", "preferential allotment", "raises", "NCD"]
  regulatory_action:
    importance: 4
    patterns: ["SEBI order", "penalty", "show-cause", "probe", "raid", "ED ", "CBI"]
  rating_change:
    importance: 3
    patterns: ["upgrade", "downgrade", "target price", "rating"]
  order_win:
    importance: 3
    patterns: ["bags order", "wins order", "order worth", "contract worth"]
  management_change:
    importance: 3
    patterns: ["resigns", "appoints CEO", "new MD", "CFO quits"]
  macro_rbi:
    importance: 4
    scope: MARKET
    patterns: ["RBI", "repo rate", "monetary policy", "MPC"]
  macro_budget:
    importance: 4
    scope: MARKET
    patterns: ["Union Budget", "Budget 20", "tax proposal"]
  other:
    importance: 1
    patterns: []

exchange_category_map:      # maps official announcement categories to event types (fill after inspecting real data)
  # "Financial Results": earnings_result
  # "Dividend": dividend
```

These patterns are **starting points, not truth**. Rule-based classification will make mistakes, and the gold-set evaluation (section 9) measures how many. Expect to tune them.

---

## 7. `news/` module

### 7.1 Job
Collect, clean, link, score, classify and embed news; keep the archive healthy; make it searchable. Emit logbook events for everything.

### 7.2 Command line

```
python news/main.py fetch                        # all enabled sources, once
python news/main.py fetch --source moneycontrol_markets
python news/main.py announcements --symbols RELIANCE,TCS --since 2023-01-01   # includes backfill
python news/main.py corporate-actions --symbols RELIANCE --since 2020-01-01
python news/main.py process                      # runs all stages on anything unprocessed
python news/main.py process --stage link         # or: dedupe | link | classify | sentiment | embed
python news/main.py search "RBI rate hike impact on banks" --symbol HDFCBANK --k 10
python news/main.py health                       # per-source health report
python news/main.py gold-sample --n 100          # export random headlines for manual labelling
python news/main.py gold-eval                    # measure linking, sentiment, event accuracy
```

Every stage is **idempotent** and works on "what has not been processed yet for the current version". Re-running does nothing new. Bumping a version (for example `linker_version`) makes the affected stage re-process.

### 7.3 Collection

#### RSS (`collect/rss.py`)
- Poll each enabled source no more often than its `poll_interval_minutes` (default 30). Do not hammer feeds.
- Use **conditional requests** (`ETag` and `Last-Modified`) so unchanged feeds cost almost nothing.
- Send an honest `User-Agent` (from config). Respect `Retry-After` and HTTP 429.
- Timeouts on every request. Retries with exponential backoff for transient errors.
- **Circuit breaker:** after `max_consecutive_failures_before_disable` failures in a row, mark the source unhealthy, stop polling it until manually re-enabled (or after a long cool-down), and log a `warning`.
- Store only: title, link, short summary (the feed's own snippet), published time, and a small `raw` JSON of useful feed fields. **Do not copy full article text.** This is a personal research archive; keep it lean and respectful of publishers' rights.

#### Timestamps (the most common silent bug)
- Feeds use different formats and sometimes omit the timezone. Parse into timezone-aware datetimes.
- If a feed gives a time **without** a timezone and the source is Indian, assume IST and record that assumption in `raw`.
- If no usable time exists, set `published_at = fetched_at` and `published_at_assumed = true`. These rows are **excluded from event studies** because their timing is not reliable.
- Unit-test the parser on real sample items from every source.

#### Exchange announcements (`collect/announcements.py`)
- Use `dalal` and/or `bse` for NSE and BSE announcements per watchlist symbol.
- Convert each announcement into an `articles` row: source_key `nse_announcements` or `bse_announcements`, `external_id` = the exchange's id, the subject as `title`, a brief description as `summary`, `published_at` from the exchange timestamp.
- Because announcements carry the symbol natively, they get `article_symbols` rows with `match_type = 'exchange_tag'` and confidence 1.0.
- Respect the libraries' documented rate limits (NSE about 3 requests per second, BSE about 8) and add your own delay. Use the libraries' session handling and caching. Do not parallelise aggressively.
- **Backfill:** with `--since`, page back as far as the source allows. Log how far back each symbol actually went (`output_summary`). Different sources and symbols will differ; record it, do not assume.
- Where both NSE and BSE report the same announcement, de-duplication (7.4) merges them.

#### Corporate actions (`collect/corporate_actions.py`)
- Fetch dividends, splits, bonuses, rights, buybacks and similar for each symbol into `corporate_actions`.
- Store `ratio_text` exactly as published. Attempt parsing into `parsed` (for example a bonus ratio); if parsing is ambiguous, set `parse_status = 'needs_review'`. **Never guess a ratio.**
- Why this matters: Phase 2 flags suspicious one-day jumps as `possible_split_or_bonus`. Corporate actions are what confirms or explains those flags, and what a later hardening step (Phase 5) uses to produce split-adjusted prices.

### 7.4 Normalisation and de-duplication (`normalize.py`)

The same story arrives from many outlets, and the same outlet republishes. Without de-duplication, one event counts as five and statistics get inflated.

1. **URL normalisation:** lowercase host, strip tracking parameters (`utm_*` and similar), drop fragments, resolve trailing slashes. Hash it into `url_hash`. A repeated `url_hash` is skipped (unique constraint).
2. **Title normalisation:** lowercase, remove punctuation and outlet suffixes ("| Moneycontrol"), collapse whitespace. Hash into `title_hash`.
3. **Exact duplicates:** same `title_hash` within the window become one `dedupe_group_id`; later arrivals get `is_duplicate = true`.
4. **Near duplicates:** within `window_hours`, titles with similarity above the threshold (for example 0.92) join the same group. After embeddings exist, an optional second pass can merge groups whose embeddings are very close.
5. The **earliest `published_at`** in a group is treated as the first-public time of the story.
6. Duplicates are kept (for source statistics and importance), but sentiment and event studies count **one item per group**.

### 7.5 Entity linking (`linking/`)

Goal: decide which watchlist stocks an article is about, with a confidence.

Rules, in order:
1. **Exchange tag:** announcements already know their symbol. Confidence 1.0.
2. **Company names** (full names from `aliases.yaml`): case-insensitive whole-phrase match. High confidence, higher if in the title.
3. **Short aliases:** word-boundary match. Medium confidence.
4. **Tickers:** accept a ticker only as a standalone **uppercase** token (for example "TCS"), and lower the confidence for short or common-word tickers. Many tickers are also ordinary words or abbreviations.
5. **Ambiguous aliases** (flagged in config) need a second signal in the same text (a related word, or another alias) before confidence goes above the storage threshold.
6. **Macro rules:** matches for RBI, budget, global markets and similar link the article to `MARKET`.

Store `match_type`, `confidence`, `matched_text` and `in_title`. Only links with confidence at least `min_confidence_to_store` are stored; only links at least `min_confidence_for_events` feed event classification and studies.

The linker's job is **precision first**: a wrong link puts the wrong news on the wrong stock and corrupts every later statistic. Measure it on the gold set (section 9).

### 7.6 Event classification and timing (`events/classifier.py`)

For each linked article (above the event confidence threshold):
1. Choose the `event_type` using, in order: the exchange category map (for announcements), then keyword and pattern rules from `news_events.yaml`. Rules should match mainly on the **title**.
2. Assign `importance` (1 to 5): base value from config, plus small bumps for source tier 0 or 1, title match, and the size of the dedupe group (many outlets covered it). Keep the formula in config and documented.
3. Record `classifier`, `matched_rule` and `logic_version`.

#### Effective trading date (critical for no look-ahead)
A news event can only be traded on **after** it is public. Compute `effective_trading_date` as:

- The **first trading session whose open is after `published_at`**.
- "Trading session" dates come from the dates present in the `candles` table for the benchmark (and/or the stock). No separate holiday list is needed in Phase 3.
- Items published before the market opens (before about 9:15 IST) have the same day's open as their entry. Items published during the session or after the close (the NSE regular session runs about 9:15 to 15:30 IST; verify) have the **next** session's open as their entry.
- If no later candle exists yet, leave it null and fill it in on a later run.
- Items with `published_at_assumed = true` never get an effective date and are excluded from studies.

### 7.7 Sentiment (`scoring/sentiment.py`)

- Run FinBERT locally on the title or title plus summary (config). Truncate to the model's token limit.
- Store all three probabilities, the label, and `score = p_positive - p_negative` (range -1 to 1). **Read the label order from the model's own configuration**; do not hard-code which index means which label.
- Process in batches. First run downloads the model; log that.
- Record `model_key` and `model_revision`. Changing the model creates new rows rather than overwriting old ones.
- One score per article (the **first** limitation, listed in section 14): an article about two companies still gets one score.

Interpretation notes for README and dashboard:
- The model measures the **tone of the text**, not the effect on the price. "Company posts record profit" is positive text, but if the market already expected it, the price may not move.
- It was trained on formal English financial sentences. Slang, sarcasm, very short fragments, and non-English text will be less reliable.
- Treat sentiment as a **feature to be tested**, not as truth. The event study (section 8) is how you find out whether it has any relationship with prices.

### 7.8 Embeddings and semantic search (`embeddings/`, `search.py`)

- Embed `title + summary` with the configured local model and store the vector.
- With `embed_only_if_linked: true`, embed only articles linked to at least one watchlist symbol or `MARKET`. This keeps the database small.
- **Changing the embedding model** changes vector dimension and meaning. Never mix models in one column. Procedure: create a new table (for example `article_embeddings_v2`) with the new dimension, backfill, switch `search.py` via config, then drop the old table when satisfied.
- Search: embed the query, run a nearest-neighbour search (cosine similarity), with optional filters for symbol, date range and event type. Return title, source, date, similarity, sentiment, linked symbols and the link.
- **"Similar past events" helper:** given an article or event, find its nearest past neighbours, then attach what the stock actually did over the following days (using candles and the effective trading date). This is the exact "what happened last time" feature. Label it clearly as **anecdotal**: a handful of similar cases is not statistical evidence.

### 7.9 Health (`health.py`)

Per source, report: last success, consecutive failures, items collected in the last 24 hours and 7 days, duplicate rate, percentage of items linked to a watchlist stock, and percentage with `published_at_assumed`. Warn when a source returns nothing for an unusual period on weekdays.

### 7.10 Logbook events for `news`

| Moment | action | status |
|---|---|---|
| Run starts | `run_start` | started |
| Per source fetch | `fetch_feed` / `fetch_announcements` / `fetch_corporate_actions` | success / failed / retried / skipped (not modified) |
| Parse | `parse_items` | success / warning (items with assumed times) |
| De-duplicate | `dedupe` | success (counts) |
| Link | `link_entities` | success / warning (low coverage) |
| Classify | `classify_events` | success |
| Sentiment | `score_sentiment` | success / failed |
| Embed | `embed_articles` | success / failed |
| Source disabled | `disable_source` | warning |
| Run ends | `run_end` | success (totals) |

One failing source or item never stops the run.

---

## 8. `backtest/` extension: do news and sentiment matter?

Phase 2's `event_study.py` was written to accept any dated event list. Phase 3 adds two **adapters** in `backtest/event_sources/` that read tables (never importing `news/`):

1. **News events:** from `news_events`, one event per `(dedupe group, symbol, event_type)`, using `effective_trading_date` as the entry day.
2. **Sentiment buckets:** from `article_sentiment` joined to `article_symbols` and de-duplicated by group, bucketed by the thresholds in `news.yaml`.

### 8.1 Command line

```
python backtest/main.py events --source news                    # all event types
python backtest/main.py events --source news --event-type earnings_result
python backtest/main.py events --source sentiment               # sentiment buckets
```

### 8.2 Rules (all Phase 2 rules still apply, plus these)

- **Timing:** entry = open of `effective_trading_date`. Exits and horizons as in Phase 2. Never use the same day's close for something published after it.
- **One event per story:** use the dedupe group, not every duplicate.
- **Exclude** items with assumed timestamps, items below the event confidence threshold, and events inside Phase 2's data-quality exclusion windows (suspected splits).
- **Market-adjusted ("abnormal") returns:** when a benchmark index is available, also report returns **minus the index return over the same period**, so a day when the whole market moved is not credited to the news. Mark these rows `abnormal = true` in `signal_stats`. Add the index to the watchlist with `kind = 'index'` (for example NIFTY 50) and confirm your price source supports it. If no source supports the index, say so and report unadjusted results only.
- **Direction:** news event types have no inherent direction, so measure both the average return and the **average absolute move** (`mean_abs_return` compared with `baseline_mean_abs`). The question "does this kind of news make the price move more than a normal day?" is often more meaningful than "does it push the price up?". Sentiment buckets are directional: positive buckets are treated as bullish and negative as bearish.
- **Keys:** write results to `signal_stats` with `signal_key` such as `news:earnings_result`, `news:dividend`, `sentiment:very_negative`.
- **Minimum sample, in-sample / out-of-sample split, independent counts, baseline and edge** all stay mandatory and visible.
- **Multiple testing:** many event types times many horizons will produce lucky results. Show the number of combinations tested.

### 8.3 Logbook
Same pattern as Phase 2: `load_data`, `apply_exclusions`, `event_study`, `write_results`, `run_end`.

---

## 9. The gold set (how you know the pipeline is accurate)

Machine-generated labels cannot be trusted until a human has checked a sample.

1. `python news/main.py gold-sample --n 100` exports random recent items (title, source, current predictions hidden).
2. **You** label each: which watchlist symbols it is really about (or none), sentiment (positive, negative, neutral), and event type. Save as `news/tests/gold/headlines.csv`. Aim for 100 to 150 items to start; grow it over time.
3. `python news/main.py gold-eval` reports:
   - Linking: precision and recall per symbol and overall.
   - Sentiment: accuracy and per-class agreement against your labels.
   - Event type: accuracy and a confusion table.
4. Initial targets (adjust as you learn): linking precision of about 0.90 or better, sentiment agreement noticeably above chance, event-type accuracy high enough for the types you actually plan to study. If a target is missed, tune aliases and rules before using the results elsewhere.
5. Re-run `gold-eval` after any change to aliases, rules or models. Store results in the logbook.

---

## 10. Retention

- `raw` JSON on articles older than `keep_raw_days` is cleared; titles, summaries, scores, links and events stay.
- Never delete `corporate_actions`, `news_events` or `article_sentiment`: they are small and valuable.
- Embeddings for items not linked to any watchlist symbol are not created in the first place.
- See section 14 for the database size estimate.

---

## 11. Dashboard additions

Read-only, as before.

### 11.1 `/news` News feed
- Newest first, with filters: symbol, source, event type, sentiment bucket, date range, importance.
- Each row: time (shown in IST), title linking to the original article, source badge, linked-symbol chips, sentiment chip (with the score), event-type chip, and a "+N similar" badge when the dedupe group has duplicates.
- Items with assumed timestamps carry a small "time approximate" badge.

### 11.2 `/news/[id]` Article detail
- Title, source, link out, short summary, linked symbols with confidence and matched text, sentiment bars (three probabilities), classified events, other items in the same dedupe group, and the "similar past events" panel with an explicit "anecdotal" label.

### 11.3 Stock page (`/stocks/[symbol]`) extended
- **News panel:** recent items for the symbol.
- **Sentiment timeline** under the price chart: daily average sentiment score (of de-duplicated items), with the number of items per day.
- **Event markers** on the candle chart for corporate actions and high-importance events, with tooltips.
- **Corporate actions list**, including any that explain a Phase 2 `possible_split_or_bonus` flag.

### 11.4 `/search` Semantic search
- A search box ("what happened last time the RBI raised rates?"), filters for symbol and date, results with similarity and source, each linking to the article page.

### 11.5 `/lab` extended
- New tabs or filters for news-event and sentiment-bucket studies, using the same columns as before (n_independent, mean, baseline, edge, in-sample versus out-of-sample, insufficient-sample label) plus the **absolute move** columns. The "abnormal (market-adjusted)" flag is shown clearly.

### 11.6 `/sources` Source health
- Table from `health.py`: each source, last success, failures, items per day, duplicate rate, link coverage. Red for disabled or failing sources.

### 11.7 Status strip
- Add a tile for `news` next to the existing ones.

---

## 12. Build tasks (do in this order)

| # | Task | Check |
|---|---|---|
| 1 | Check pgvector availability and your free-tier database size limit | Extension enabled; limit noted in the README. |
| 2 | Create `news/` environment (Python 3.11+); install and smoke-test `feedparser`, the exchange library, `transformers` and the embedding model | Each imports and runs a one-line example. |
| 3 | Find, test and record working feed URLs in `config/feeds.yaml` | Each enabled feed returns items in a test script. |
| 4 | Add `004_news.sql` and `005_phase3_alters.sql`; extend read-only RLS | Tables exist; browser can read, not write. |
| 5 | Add the benchmark index to the watchlist (`kind = 'index'`) and backfill its candles | Index candles exist, or a documented reason why not. |
| 6 | Build `normalize.py` (URL, title, timestamps) with unit tests on real samples | Timezone cases pass, including a feed with no timezone. |
| 7 | Build RSS collection with conditional requests, retries and the circuit breaker | Second poll of an unchanged feed is `skipped (not modified)`. |
| 8 | Build exchange announcement collection and a small backfill | Items stored with `exchange_tag` symbols; logbook shows how far back it went. |
| 9 | Build corporate action collection with `needs_review` handling | A sample of splits and bonuses is stored; ambiguous ratios are flagged, not guessed. |
| 10 | Build de-duplication (exact and near) | Same story from two outlets shares one group; only the first is non-duplicate. |
| 11 | Build `aliases.yaml` and the linker | Hand-picked test headlines link correctly; ambiguous names do not over-match. |
| 12 | Build the rule-based event classifier and effective-trading-date logic | Test: after-hours item gets the next session; pre-market item gets the same day. |
| 13 | Build sentiment scoring (batched) | Obvious positive and negative headlines score sensibly; label order read from model config. |
| 14 | Build embeddings and semantic search | A query returns clearly related past items; filters work. |
| 15 | Build the "similar past events" helper | Shows subsequent price moves, labelled anecdotal. |
| 16 | Create the gold set and run `gold-eval` | Metrics reported; aliases and rules tuned until targets are reasonable. |
| 17 | Build `health.py` | Disabled and failing sources are visible. |
| 18 | Wire logbook events everywhere | Live feed shows each stage; one forced failure does not stop a run. |
| 19 | Backtest adapters for news events and sentiment buckets, with abnormal returns | Hand-built case reproduces expected counts and edge. |
| 20 | Run the news and sentiment studies | Results appear in `signal_stats`, with insufficient-sample rows labelled. |
| 21 | Dashboard: `/news`, article page, stock-page panels and sentiment timeline | Data matches the database on spot checks. |
| 22 | Dashboard: `/search`, `/sources`, `/lab` extension | Search works; source health is accurate. |
| 23 | Failure drills (section 13) | All pass. |
| 24 | Write READMEs including limitations (section 14) | A new reader can run Phase 3 from them. |

---

## 13. Testing and failure drills

### Unit tests
- **Timestamps:** every source's sample formats, with and without timezones.
- **URL and title normalisation:** tracking parameters, trailing slashes, outlet suffixes.
- **De-duplication:** exact duplicates, near duplicates, and similar-but-different stories that must **not** merge.
- **Linking:** positive and negative cases for each rule, especially ambiguous aliases and ticker-like words.
- **Event classification:** each event type has matching and non-matching headlines.
- **Effective trading date:** pre-market, in-session, after-close, weekend and holiday gaps.
- **Sentiment:** label order mapping, truncation of very long text.
- **Backtest adapters:** counts, baseline, abnormal returns and exclusions on a tiny hand-built dataset.

### Failure drills (all must pass)

| Drill | Expected result |
|---|---|
| A feed returns invalid XML | `failed` event; other sources continue; consecutive-failure counter increments. |
| A feed returns HTTP 429 or 403 | Backoff; after repeated failures the source is disabled with a `warning`. |
| A feed item has no date | Stored with `published_at_assumed = true`; excluded from studies. |
| The same story arrives from three outlets | One dedupe group; studies count it once. |
| Run `fetch` twice in a row | No duplicate articles; second run mostly `skipped`. |
| No internet during `process` | Local stages (link, classify, sentiment, embed) still run on stored data. |
| Sentiment model missing on first run | Downloads once, or fails clearly with a `failed` event; no partial garbage rows. |
| Very long or empty summary | Truncated or handled; no crash. |
| Non-English or garbled text | Stored; sentiment skipped or flagged; no crash. |
| Article mentioning no watchlist stock | Stored but unlinked; not embedded (when configured); not in studies. |
| Ambiguous alias ("Reliance" in an unrelated context) | Low confidence; not used for events. |
| A corporate action with an unclear ratio | `needs_review`; never auto-parsed. |
| Change `linker_version` and re-run `process` | Linking re-runs for affected items only. |
| Break the database key | Clear error, non-zero exit, nothing silently lost. |
| Dashboard open during `fetch` | Source health and (if enabled) news ticker update. |

---

## 14. Known limitations (document these in the README and on the dashboard)

1. **History is shallow for articles.** Free feeds expose recent items only; the archive grows from the day collection starts. Exchange announcements and corporate actions go back further, depending on the source.
2. **One sentiment score per article.** A story about two companies cannot be scored separately for each.
3. **English only.** Hindi and regional-language news are not covered.
4. **Sentiment is tone, not price impact.** It is tested, not assumed.
5. **Rule-based event types are approximate.** Accuracy is measured on the gold set, which is small and personal.
6. **Titles and snippets only.** The system does not read full articles in this phase.
7. **Unofficial exchange libraries can break** without notice. Keep fallbacks and watch source health.
8. **Free-tier storage.** Embeddings are about 1.5 KB each at 384 dimensions (plus index overhead). At several hundred relevant articles a day this can reach hundreds of megabytes per year. Embed only relevant items, monitor database size, and decide a retention rule before it becomes a problem.
9. **News studies are noisy.** Many event types, horizons and stocks mean some results will look good by luck. The baseline, minimum sample, abnormal-return and out-of-sample rules exist for that reason.

---

## 15. Acceptance criteria (Definition of Done)

Phase 3 is complete when **all** are true:

- [ ] `004_news.sql` and `005_phase3_alters.sql` are applied; new tables have read-only RLS for the browser.
- [ ] At least three RSS sources and both exchange announcement sources are collected without duplicates, using conditional requests and a circuit breaker.
- [ ] Corporate actions are stored for the watchlist, with ambiguous ratios flagged `needs_review`.
- [ ] All timestamps are timezone-correct, and items with assumed times are excluded from studies.
- [ ] De-duplication groups the same story across outlets.
- [ ] Linking, classification and sentiment run on all unprocessed items and are idempotent per version.
- [ ] `effective_trading_date` is correct for pre-market, in-session, after-close and weekend items (tests pass).
- [ ] Embeddings and semantic search work, with the "similar past events" helper labelled anecdotal.
- [ ] A gold set of at least 100 labelled items exists, and `gold-eval` metrics are recorded and acceptable.
- [ ] News-event and sentiment-bucket studies run through the backtest module, with baseline, abnormal returns (or a documented reason they are unavailable), independent counts, minimum-sample labels and in-sample / out-of-sample columns.
- [ ] Dashboard shows the news feed, article detail, stock-page news and sentiment timeline, semantic search, source health, and the extended Lab.
- [ ] Every action of the module appears in `agent_events` with a shared `run_id` per run.
- [ ] All failure drills in section 13 pass.
- [ ] No module imports another module's code (only `shared/`).
- [ ] No paid service, no cloud LLM call, no full-article copying, no secret in git or in browser code.

---

## 16. Risks and how to handle them

| Risk | Handling |
|---|---|
| Wrong timestamps create look-ahead bias | Timezone-aware parsing, assumed-time flag, effective-trading-date logic with tests. |
| Wrong entity links corrupt statistics | Precision-first linker, confidence thresholds, ambiguous-alias rules, gold-set measurement. |
| Duplicates inflate evidence | Dedupe groups; one event per group in studies. |
| Sources vanish or change | Source health, circuit breaker, multiple sources, logbook visibility. |
| Terms of use and copyright | Personal use, titles and snippets only, polite polling, honest user agent, no redistribution. |
| Model misreads tone | Gold-set evaluation; sentiment treated as a testable feature. |
| Database fills up | Embed only relevant items, retention policy, monitor size. |
| Heavy ML dependencies break the environment | Separate environment for `news/`, pinned versions, smoke tests first. |
| Over-trusting lucky results | Mandatory baseline, minimum sample, multiple-testing disclosure, out-of-sample column. |
| Over-building | Stick to section 2. |

---

## 17. Rules for any AI agent working on Phase 3

1. Read `PROJECT_OVERVIEW.md`, `PHASE_1.md`, `PHASE_2.md` and this file before writing code.
2. Work only in the folder for the task at hand. `news/` never imports other modules or `backtest/`; `backtest/` never imports `news/`. Only `shared/` is shared.
3. Existing tables keep their meaning. Additions go in new numbered migrations and must be nullable or defaulted.
4. Log every real action with the shared logbook writer.
5. Never store full article text. Store titles, short snippets, links and metadata.
6. Never guess a corporate action ratio. Flag it `needs_review`.
7. Never remove the baseline, sample-size, abnormal-return or out-of-sample reporting to make a result look better.
8. Never fabricate or hard-code numbers. Everything comes from stored data and reproducible code.
9. Bump the relevant `logic_version` or `linker_version` whenever rules, aliases or models change.
10. Do not use a cloud LLM, a paid API, a paid news service, or any trading function.
11. Do not start Phase 4+ work, even if it looks easy.
12. If a library's behaviour is uncertain (feed formats, exchange library responses, label order, rate limits), say so and verify with a small script instead of guessing.

---

## 18. What Phase 4 will need from Phase 3

- Reliable `articles`, `article_symbols`, `article_sentiment`, `news_events` and `corporate_actions`, each with provenance (source, time, version), so agents can cite exact rows as evidence.
- `signal_stats` rows for news and sentiment studies, so an agent that says "earnings news usually moves this stock" can attach the measured effect and its sample size, or admit there is none.
- Semantic search and the similar-past-events helper exposed as **read-only functions** the agents can call (the agent module will wrap them; it will not import `news/`).
- Clear importance scores, so agents focus on what matters instead of every headline.
- Prompt-injection awareness: news text is **untrusted data**. Nothing in this phase executes or follows instructions found in article text, and Phase 4 must keep it that way.
- Known limitations (section 14) written down, so agents and the dashboard can state them.
