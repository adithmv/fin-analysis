# Phase 1: Foundation and Visibility

> Part of the Indian Stock Market Research & Analytics Tool. Read `PROJECT_OVERVIEW.md` first.
> This file is the complete specification for Phase 1. An AI agent or developer should be able to build Phase 1 from this file alone.

---

## 1. Goal

Build the base of the whole system and make it **visible from day one**.

At the end of Phase 1 the user can:

1. Run one command and have **daily price candles for a watchlist of Indian stocks** fetched, validated and stored.
2. Open a **dashboard** and watch the **logbook** (every real action the system takes) update live.
3. Open a stock page and see its **candles on a chart**.
4. Break something on purpose (bad symbol, no internet) and see it **fail cleanly, be logged, and not stop the rest**.

Phase 1 deliberately uses **no LLM and no AI agents**. It is pure data plumbing plus visibility. That means no free-tier API limits to worry about, and everything built later sits on trustworthy data.

---

## 2. Scope

### In scope
- Monorepo skeleton with one folder per module (all modules created, only some filled in).
- Database schema (migrations) for: `watchlist`, `candles`, `agent_events`.
- `shared/` package: database client and the **logbook writer**.
- `ingest/` module: fetch daily candles with multi-source fallback, validation, caching, idempotent writes.
- `logbook/` module: command-line queries for viewing events.
- `dashboard/` (Next.js): live logbook feed, agent/module status strip, stock page with candle chart.
- Configuration, environment files, README per module.
- Tests and failure drills.

### Out of scope (do NOT build in Phase 1)
- Indicators, candlestick patterns, backtests (Phase 2).
- News, sentiment, embeddings (Phase 3).
- LLM agents, discussion threads (Phase 4).
- Browser agent, scheduling, alerts (Phase 5).
- Intraday candles (daily only for now; the schema supports other timeframes later).
- Any order placement or trading function. Ever.
- Any paid service.

---

## 3. Prerequisites

| Item | Notes |
|---|---|
| Python | 3.10 or newer recommended (verify against library requirements when installing). |
| Node.js | Current LTS, for the Next.js dashboard. |
| Supabase project | Free tier. Provides Postgres and Realtime. |
| Git repository | One repo for everything. |
| (Optional) Demat account | Angel One, Upstox or Fyers give free official data APIs. Not required for Phase 1. |

**Open decision for the user:** do they have a demat account with one of those brokers? If yes, the broker API can become the primary source. If no, Phase 1 works with jugaad-data, OpenChart and yfinance.

---

## 4. Repository skeleton to create

Create all folders now, so the structure is fixed from the start. Only the folders marked "Phase 1" get real code.

```
market-research/
├── README.md
├── PROJECT_OVERVIEW.md
├── PHASE_1.md
├── .env.example
├── .gitignore
├── config/
│   └── watchlist.yaml            # Phase 1: initial watchlist
├── db/
│   └── migrations/               # Phase 1: 001_init.sql
├── shared/                       # Phase 1: db client + logbook writer
│   ├── README.md
│   ├── pyproject.toml
│   └── shared/
│       ├── __init__.py
│       ├── db.py
│       └── logbook.py
├── ingest/                       # Phase 1
│   ├── README.md
│   ├── requirements.txt
│   ├── main.py
│   ├── sources/
│   │   ├── base.py               # common interface
│   │   ├── jugaad_source.py
│   │   ├── openchart_source.py
│   │   └── yfinance_source.py
│   ├── validate.py
│   └── tests/
├── logbook/                      # Phase 1: CLI viewer
│   ├── README.md
│   ├── requirements.txt
│   └── main.py
├── dashboard/                    # Phase 1: Next.js app
├── signals/                      # empty placeholder + README (Phase 2)
├── backtest/                     # empty placeholder + README (Phase 2)
├── news/                         # empty placeholder + README (Phase 3)
├── analysis-agents/              # empty placeholder + README (Phase 4)
└── browser-agent/                # empty placeholder + README (Phase 5)
```

Each placeholder folder gets a short `README.md` saying: "Not built yet. Planned for Phase N. Will read X and write Y."

---

## 5. Database design

All schemas live in `db/migrations/001_init.sql`. These tables are the **contracts** between modules. Changing a column later means updating the migration and every module README that touches it.

### 5.1 Conventions
- All timestamps are `timestamptz`, stored in UTC.
- Daily candles use `ts` = the trading session date at 00:00 in India Standard Time (IST), converted to UTC when stored. Document this in the ingest README so every module interprets it the same way.
- Prices are `numeric`, not float, to avoid rounding surprises.
- Writes are **idempotent**: running the same fetch twice must never create duplicates (use upsert on the primary key).

### 5.2 `watchlist`

Stocks the system tracks.

```sql
create table watchlist (
  symbol      text        not null,          -- NSE symbol, e.g. 'RELIANCE'
  exchange    text        not null default 'NSE',
  active      boolean     not null default true,
  added_at    timestamptz not null default now(),
  primary key (symbol, exchange)
);
```

### 5.3 `candles`

One row per symbol, timeframe and timestamp.

```sql
create table candles (
  symbol       text        not null,
  exchange     text        not null default 'NSE',
  timeframe    text        not null default '1d',   -- '1d' now; others later
  ts           timestamptz not null,                -- see convention above
  open         numeric     not null,
  high         numeric     not null,
  low          numeric     not null,
  close        numeric     not null,
  volume       bigint,
  source       text        not null,                -- which source produced this row
  adjusted     boolean     not null default false,  -- split/bonus adjusted or not
  fetched_at   timestamptz not null default now(),
  primary key (symbol, exchange, timeframe, ts)
);

create index candles_symbol_ts_idx on candles (symbol, timeframe, ts desc);
```

### 5.4 `agent_events` (the logbook)

Append-only. Rows are written by **code**, never by an AI describing itself.

```sql
create table agent_events (
  id             bigserial   primary key,
  ts             timestamptz not null default now(),
  run_id         uuid        not null,             -- groups events from one run
  module         text        not null,             -- 'ingest', 'signals', ...
  agent          text,                             -- null in Phase 1
  action         text        not null,             -- e.g. 'fetch_candles'
  tool           text,                             -- e.g. 'jugaad-data'
  status         text        not null
                 check (status in ('started','success','failed','retried','skipped','warning')),
  symbol         text,                             -- if the event concerns one stock
  input_summary  text,
  output_summary text,
  source_urls    text[],
  duration_ms    integer,
  api_calls      integer,
  tokens_in      integer,                          -- null until LLMs arrive
  tokens_out     integer,
  error          text,
  meta           jsonb       not null default '{}'::jsonb
);

create index agent_events_ts_idx     on agent_events (ts desc);
create index agent_events_module_idx on agent_events (module, ts desc);
create index agent_events_status_idx on agent_events (status, ts desc);
create index agent_events_symbol_idx on agent_events (symbol, ts desc);
```

### 5.5 Realtime and access

- Enable Supabase **Realtime** on `agent_events` (and `candles` if you want live chart updates).
- The dashboard needs read access. Options, in order of safety:
  1. **Row Level Security with read-only policies** and the public anon key in the browser (writes only from Python using the service key).
  2. Or fetch through Next.js server routes so the browser never holds database credentials.
- **Never put the Supabase service-role key in browser code or in the git repository.** It goes only in local `.env` files read by Python modules.

---

## 6. `shared/` package

Intentionally tiny. This is the **only** code modules are allowed to share.

### 6.1 `db.py`
- Creates a Supabase/Postgres client from environment variables.
- Exposes: `get_client()`, plus a helper for bulk upsert.
- No business logic.

### 6.2 `logbook.py`

The logbook writer used by every module.

Required interface:

```python
log_event(
    run_id, module, action, status,
    tool=None, symbol=None, agent=None,
    input_summary=None, output_summary=None,
    source_urls=None, duration_ms=None,
    api_calls=None, error=None, meta=None,
)
```

Also provide a **context manager** so timing and failure logging are automatic:

```python
with logbook.action(run_id, "ingest", "fetch_candles", tool="jugaad-data", symbol="RELIANCE") as ev:
    df = source.fetch_daily(...)
    ev.output_summary = f"{len(df)} rows"
# On exit: writes 'success' with duration. On exception: writes 'failed' with the error, then re-raises.
```

Rules:
- **Logging must never crash the caller.** If the logbook write fails, print to stderr and continue.
- Summaries are short (one line, under roughly 300 characters). Large data does not go in the logbook.
- Never write secrets (keys, tokens) into any field.

---

## 7. `ingest/` module

### 7.1 Job
For each active symbol in `watchlist`, fetch daily OHLCV candles for a date range, validate them, and upsert into `candles`.

### 7.2 Command line

```
python ingest/main.py --symbols RELIANCE,TCS         # specific stocks
python ingest/main.py --all                          # whole active watchlist
python ingest/main.py --all --days 365               # custom lookback
python ingest/main.py --all --since 2024-01-01       # explicit start date
python ingest/main.py --symbols INFY --source yfinance   # force one source (testing)
```

Default behaviour with no date flags: fetch only what is missing since the latest stored candle for that symbol (incremental). On first run, fetch about one year.

### 7.3 Source interface (`sources/base.py`)

Every source implements the same interface, so sources are swappable:

```python
class PriceSource:
    name: str
    def fetch_daily(self, symbol: str, start: date, end: date) -> pandas.DataFrame:
        """Return columns: ts, open, high, low, close, volume. Raise SourceError on failure."""
```

### 7.3.1 Sources, in default priority order

| Priority | Source | Notes |
|---|---|---|
| 1 | jugaad-data | Downloads from NSE's website, has built-in caching to avoid being blocked. |
| 2 | OpenChart | NSE/NFO historical data. Unofficial. |
| 3 | yfinance (`SYMBOL.NS`) | Unofficial scraper; can break without warning. Use as fallback. |
| Optional | Broker API (Angel One / Upstox / Fyers) | Official, free data API. Add as priority 1 if the user has an account. |

Do not add tvdatafeed in Phase 1 (unofficial, terms concerns). Do not add any paid source.

The priority order lives in `config`, not in code, so it can be changed without edits.

### 7.4 Fallback logic

```
for source in priority_order:
    try fetch -> validate
    if ok: stop, write rows
    else: log 'failed' (with reason) and try next source
if all sources fail: log 'failed' for this symbol, continue with next symbol
```

Every attempt, success or failure, produces a logbook event. One bad symbol never stops the run.

### 7.5 Validation (`validate.py`)

Run on every fetched DataFrame before writing. Reject a row, or the whole fetch, per these rules:

| Check | On failure |
|---|---|
| `high >= max(open, close)` and `low <= min(open, close)` | Drop the row, log `warning` with count. |
| Any price `<= 0` or null | Drop the row, log `warning`. |
| Duplicate timestamps | Keep one, log `warning`. |
| Volume missing | Allow (store null), log `warning` only if widespread. |
| Zero rows returned | Treat as source failure, try next source. |
| Missing weekdays in the range | Log `warning` only. Market holidays exist, so this is not an error. |
| Single-day price jump above about 20% | Log `warning` ("possible split/bonus, data may be unadjusted"). Still store. |

### 7.6 Cross-check between sources (lightweight)

After a successful fetch for a symbol, occasionally (for example once per run per symbol, last 5 days) fetch the same days from a second source and compare closing prices.

- Difference within about 0.5%: fine, no event beyond a `success` note.
- Larger difference: log a `warning` with both values. Do not overwrite automatically.

This catches silently bad data early. It can be switched off in config if it causes too many requests.

### 7.7 Politeness and caching

- Wait a short, configurable delay between symbols (for example 1 to 2 seconds).
- Retry transient failures with exponential backoff (for example 3 tries) before moving to the next source.
- Never fetch data that is already stored, unless `--since` or `--days` forces it.
- If a source signals blocking (HTTP 403/429 or similar), stop using that source for the rest of the run and log it.

### 7.8 Writing

- Upsert on the primary key `(symbol, exchange, timeframe, ts)`.
- Set `source` to the source that supplied each row.
- Set `adjusted = false` unless the source explicitly provides adjusted data (document which).
- Write in batches (for example 500 rows).

### 7.9 Logbook events ingest must emit

| Moment | action | status |
|---|---|---|
| Run starts | `run_start` | started |
| Per source attempt | `fetch_candles` | success / failed / retried |
| After validation | `validate_candles` | success / warning |
| After writing | `write_candles` | success / failed |
| Cross-check | `crosscheck` | success / warning |
| Run ends | `run_end` | success (with totals in `output_summary`) |

All events of one run share the same `run_id`.

---

## 8. `logbook/` module (CLI viewer)

A small command-line tool for reading `agent_events`, useful before the dashboard exists and for debugging afterwards.

```
python logbook/main.py tail                       # latest 50 events
python logbook/main.py tail --status failed       # only failures
python logbook/main.py tail --module ingest --symbol TCS
python logbook/main.py run <run_id>               # everything from one run
python logbook/main.py summary --since 24h        # counts by module and status
```

Read-only. It never writes events.

---

## 9. `dashboard/` (Next.js)

### 9.1 Purpose
The user's window into the system. In Phase 1 it only **reads**.

### 9.2 Pages

**1. `/` Live feed**
- Top **status strip**: one tile per module (`ingest`, and placeholders for others) showing last run time and last status (green success / amber warning / red failed / grey never run).
- Below: a **live list of logbook events**, newest first, updating in real time via Supabase Realtime. No page refresh needed.
- Filters: module, status, symbol, time range.
- Clicking an event expands it: full input/output summary, error text, source URLs, duration, `meta` JSON.
- Failed events are visually obvious.

**2. `/logbook` Full logbook**
- Paginated table of all events with the same filters.
- A "run view": clicking a `run_id` shows everything from that run in order, like a timeline.

**3. `/stocks` Watchlist**
- List of watchlist symbols with latest close, last candle date, source, and a data-health flag (for example "no candle in 3+ trading days").

**4. `/stocks/[symbol]` Stock page**
- Candlestick chart of stored daily candles with volume.
- Use an open-source charting library (for example TradingView's `lightweight-charts`; verify its current licence and API before adopting).
- Beneath the chart: the recent logbook events for this symbol.

### 9.3 Rules
- Dashboard never holds the service-role key.
- No write actions in Phase 1 (the "ask a question" feature arrives in Phase 4).
- Handle empty states gracefully (no data yet, Realtime disconnected).
- Show a small "live / reconnecting" indicator for the Realtime connection.

---

## 10. Configuration

### 10.1 `.env.example` (committed, no real values)

```
SUPABASE_URL=
SUPABASE_SERVICE_KEY=      # Python modules only. Never in the browser. Never committed.
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

Real values go in a local `.env` that is listed in `.gitignore`.

### 10.2 `config/watchlist.yaml`

```yaml
exchange: NSE
symbols:
  - RELIANCE
  - TCS
  - INFY
  - HDFCBANK
  - ICICIBANK
```

Start small (about 5 stocks). Syncing this file into the `watchlist` table is part of the ingest start-up.

### 10.3 `config/ingest.yaml`

```yaml
source_priority: [jugaad, openchart, yfinance]
default_lookback_days: 365
delay_between_symbols_seconds: 1.5
retries: 3
crosscheck:
  enabled: true
  tolerance_percent: 0.5
```

---

## 11. Build tasks (do in this order)

Each task is small and has a clear check.

| # | Task | Check |
|---|---|---|
| 1 | Create repo, folders, `.gitignore`, `.env.example` | Structure matches section 4. |
| 2 | Create Supabase project, run `001_init.sql` | Three tables exist with the right columns. |
| 3 | Write `shared/db.py` | A script can connect and read an empty `watchlist`. |
| 4 | Write `shared/logbook.py` (+ context manager) | Writing a test event produces a row; a failing write does not crash the caller. |
| 5 | `logbook` CLI `tail` | Test event appears in the terminal. |
| 6 | `ingest/sources/base.py` + `jugaad_source.py` | One stock, 30 days returns a clean DataFrame. |
| 7 | `validate.py` with unit tests | Bad rows are caught in tests. |
| 8 | `ingest/main.py` for one symbol, one source, with logging and upsert | Candles in DB; events in logbook; re-run creates no duplicates. |
| 9 | Add OpenChart and yfinance sources + fallback logic | Forcing source 1 to fail makes source 2 take over, and the logbook shows both attempts. |
| 10 | Incremental fetch, `--all`, delays, retries | Second run fetches only new days. |
| 11 | Cross-check between sources | A deliberately altered value triggers a warning. |
| 12 | Dashboard: project setup, Supabase read access, RLS read-only policies | Can read events in the browser with the anon key; cannot write. |
| 13 | Dashboard: live feed + status strip + filters | Running ingest in a terminal makes new events appear live. |
| 14 | Dashboard: `/logbook` and run view | A full run reads as a clear timeline. |
| 15 | Dashboard: `/stocks` and `/stocks/[symbol]` with chart | Chart matches the stored data for a stock. |
| 16 | Failure drills (section 13) | All pass. |
| 17 | Write module READMEs, update root README | A new reader can run Phase 1 from the READMEs. |

---

## 12. Module READMEs (required content)

Each module README states:

1. **Purpose** in one or two sentences.
2. **Reads** (tables or external sources).
3. **Writes** (tables).
4. **Config** needed (env vars, yaml files).
5. **How to run** (exact commands).
6. **Logbook events** it emits.
7. **Known limitations.**

---

## 13. Testing and failure drills

### Unit tests
- `validate.py`: each rule in section 7.5 has a test with a bad sample.
- Source adapters: output columns and types are correct (use saved sample data, not live calls).
- Logbook writer: success path, failure path, and "logging fails but caller survives".

### Failure drills (must all pass before Phase 1 is done)

| Drill | Expected result |
|---|---|
| Invalid symbol (`NOTASTOCK`) | `failed` events for every source; run continues with other symbols; `run_end` summarises failures. |
| Turn off internet mid-run | Retries, then `failed` events, no crash, no partial garbage rows. |
| Force the primary source to fail | Fallback source supplies data; logbook shows the failed attempt and the success. |
| Run ingest twice in a row | No duplicate candles; second run mostly `skipped` or tiny. |
| Break the Supabase key | Clear error, non-zero exit, nothing silently lost. |
| Dashboard open while ingest runs | Events stream in live without refreshing. |
| Disconnect then reconnect Realtime | Indicator shows "reconnecting", then recovers. |

---

## 14. Acceptance criteria (Definition of Done)

Phase 1 is complete when **all** are true:

- [ ] Repo structure exists exactly as in section 4, with README in every module folder.
- [ ] `001_init.sql` creates `watchlist`, `candles`, `agent_events` with indexes.
- [ ] `python ingest/main.py --all` fetches, validates and stores daily candles for the whole watchlist.
- [ ] Re-running it creates no duplicates and only fetches new days.
- [ ] At least two sources work, and automatic fallback is demonstrated.
- [ ] Every action in a run appears in `agent_events`, all sharing one `run_id`.
- [ ] `logbook` CLI can tail, filter, show a run, and summarise.
- [ ] Dashboard shows the live feed with status strip, filters and expandable events.
- [ ] Dashboard stock page shows a correct candle chart.
- [ ] All failure drills in section 13 pass.
- [ ] No secret is committed to git; the service key is never in browser code.
- [ ] No module imports another module's code (only `shared/`).

---

## 15. Risks and how to handle them

| Risk | Handling |
|---|---|
| NSE website changes and breaks a source | Fallback sources, caching, and the logbook makes the break visible immediately. |
| Source blocks requests | Delays, retries, caching, and stop-using-source-for-this-run behaviour. |
| Unadjusted data after splits/bonus | Store the `adjusted` flag, warn on large jumps, never mix adjusted and unadjusted silently. |
| Realtime misconfigured | Test with a manual insert first; fall back to polling every few seconds if needed. |
| Over-building | Stick to the scope in section 2. Anything else waits for its phase. |

---

## 16. Rules for any AI agent working on Phase 1

1. Read `PROJECT_OVERVIEW.md` and this file before writing code.
2. Work only in the folder for the task at hand. Never import code from another module (only `shared/`).
3. Do not change table schemas without updating `001_init.sql` (or adding a new numbered migration) and the READMEs.
4. Log every real action with the shared logbook writer.
5. Never commit secrets. Never use the service key in the dashboard.
6. Do not add paid services or any trading/order function.
7. Do not start Phase 2+ work, even if it looks easy.
8. If a library's behaviour is uncertain (for example a changed API), say so and test it with a small script instead of guessing.

---

## 17. What Phase 2 will need from Phase 1

So Phase 1 is built with the next step in mind:

- Reliable, validated daily candles in `candles` (signals will read only this table).
- A working logbook writer (signals and backtest will use it unchanged).
- A dashboard shell that can gain a "signals" layer on the chart.
- A `jobs` table or scheduler decision. This is **not** built in Phase 1, but note whether cron or a jobs table feels better after running ingest manually for a while.
