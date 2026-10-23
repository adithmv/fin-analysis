# Project Overview: Indian Stock Market Research & Analytics Tool

> Read this file first. It explains WHAT we are building, the constraints, and the tech stack.
> A separate `WORKINGS.md` (to be written next) explains HOW each module works in detail.

---

## 1. What we are building

A **personal research and analytics tool** for the **Indian stock market (NSE/BSE)**. It is a set of cooperating AI agents and data pipelines that:

1. Understand **candlesticks, indicators and trends** from price data.
2. Analyse **latest and historical news** (and announcements) and relate it to price moves.
3. **Browse the web like a human** when a source has no API or feed.
4. Let the user **see what every agent is doing** (logbook) and **what the agents are discussing** (discussion area).

The output is **research support**: summaries, signals, evidence and debate. It is not a trading bot.

---

## 2. Hard constraints (do not violate)

- **Personal use only.** Single user. No multi-tenant features, no public product.
- **Indian market only.** NSE/BSE equities (indices and F&O data only if useful later).
- **Free only.** Use free tools, free APIs and free tiers. Do not add any paid service or paid API without explicit approval from the user.
- **No order placement.** The tool never places, modifies or cancels trades. Read-only market data and research.
- **Not financial advice.** Every report should say it is analysis for research, not a recommendation.
- **Reuse over rebuild.** Prefer existing open-source GitHub libraries to writing algorithms from scratch.
- **Respect site terms.** Prefer official APIs and RSS. Use browser automation only when no API/feed exists, at a polite rate.

---

## 3. Architecture principles

- **Monorepo.** Everything lives in one repository.
- **One folder per module.** Each module is self-contained with its own folder, dependency file and README.
- **Modules never import each other's code.** They cooperate only by reading and writing shared database tables with agreed schemas (the "contracts").
- **The database is the hub.** A module writes rows; the next module picks them up (via a `jobs` table or a scheduler).
- **`shared/` stays tiny.** It contains only the DB client and the logbook writer, so logging works the same everywhere.
- **Every module runs on its own** (for example `python ingest/main.py`) so it can be tested or restarted independently.
- **Failure isolation.** If one source or module breaks, others keep working on the last good data.
- **Source fallbacks and caching.** Every data fetch tries source A, falls back to B, and caches results locally in the database.

---

## 4. Repository layout

```
market-research/
├── README.md
├── PROJECT_OVERVIEW.md      # this file
├── WORKINGS.md              # how each module works (next)
├── .env.example
├── db/
│   └── migrations/          # table schemas = contracts between modules
├── shared/                  # DB client + logbook writer only
├── ingest/                  # price data fetching
├── signals/                 # indicators + candlestick patterns
├── news/                    # news/announcement fetching + sentiment
├── browser-agent/           # human-like web browsing (last resort source)
├── analysis-agents/         # analyst agents + bull/bear debate
├── backtest/                # test whether signals worked historically
├── logbook/                 # queries/viewer for the agent_events table
└── dashboard/               # Next.js app: live feed, logbook, discussion
```

---

## 5. Modules (purpose, reads, writes)

| Module | Purpose | Reads | Writes |
|---|---|---|---|
| `ingest` | Fetch OHLCV candles for the watchlist | external sources | `candles` |
| `signals` | Compute indicators and candlestick patterns | `candles` | `signals` |
| `news` | Pull news/announcements, score sentiment, embed | RSS/exchange feeds | `articles` |
| `browser-agent` | Extract data from pages with no API | web pages | `documents` |
| `analysis-agents` | Technical, news, bull, bear, risk agents + summariser | `signals`, `articles`, `documents` | `threads`, `messages` |
| `backtest` | Evaluate signals historically | `candles`, `signals` | `backtest_results` |
| `logbook` | Record and show every real action | `agent_events` | (viewer) |
| `dashboard` | Live feed, logbook view, discussion, ask questions | all tables (read) | `messages` (user questions only) |

Every module writes one row to `agent_events` for each real action it performs.

---

## 6. Logbook and discussion area

**Logbook (`agent_events`)** is the ground truth, written by code, never by the AI's own narration. Each row has: timestamp, module/agent, action, tool used, short input and output summary, source links, status (success/failed/retried), and token/API usage.

**Discussion area (`threads`, `messages`)** is where agents post as roles (technical analyst, news analyst, bull, bear, risk, summariser). One thread per stock per day. The user can post questions into a thread and agents reply.

**Rule:** every discussion message must reference the logbook entries it relied on. A claim with no matching log entry is treated as unverified.

**Free-tier rule:** cap debates at about two rounds per stock per day, and run full debates only on the watchlist.

---

## 7. Tech stack

### Language and runtime
- **Python** for data, signals, news, agents, backtesting.
- **TypeScript / Next.js** for the dashboard.

### Data and storage
- **Supabase (Postgres)** as the database hub, with **pgvector** for news embeddings.
- **Supabase Realtime** to push new logbook/discussion rows to the dashboard.

### Price data (free, Indian market)
- **jugaad-data**: historical and live data from NSE's website, with built-in caching.
- **OpenChart**: intraday and end-of-day NSE/NFO data.
- **PKNSETools**: OHLCV, quotes, option chains, with yfinance fallback.
- **yfinance** (`.NS` tickers): fallback source (unofficial, can break).
- **Optional official broker APIs (free data):** Angel One SmartAPI, Fyers, Upstox. Requires a demat account with that broker. Data only, no orders.
- **Optional / risky:** tvdatafeed (TradingView, unofficial, personal experiments only).
- NSE bhavcopy end-of-day files as a stable fallback for daily candles.

### Technical analysis and backtesting
- **TA-Lib**: 150+ indicators and 61 candlestick patterns (needs the C library).
- **pandas-ta**: 130+ indicators, can use TA-Lib underneath.
- **VectorBT**: fast vectorised backtesting, integrates TA-Lib and pandas-ta.

### News and sentiment
- RSS feeds from Indian financial news sites and NSE/BSE corporate announcements.
- **FinBERT** (local) for headline sentiment, and/or an LLM.
- Reference: **FinGPT** (AI4Finance) for financial NLP datasets and ideas; its models are from 2023, so prefer a current general LLM for analysis.

### Agents and reference design
- **TradingAgents** (Tauric Research): reference for the multi-agent structure (analysts, researchers, trader, risk team). Study and borrow ideas; it is research-oriented and not for live trading here.
- **LLM options (free):** Gemini API free tier, or a local model via **Ollama**. Free-tier limits and model availability change often, so check Google AI Studio for current limits. Do not send private data (for example a personal portfolio) to a free cloud tier, since inputs may be used to improve models.

### Web browsing
- **browser-use** (open source, MIT) on **Playwright**, used only for sources with no API or RSS.
- **Playwright MCP** is an alternative; consider plain Playwright for predictable steps and AI browsing only where reasoning is needed.

### Data hub / reference
- **OpenBB** (AGPLv3) is an optional data-integration layer. Fine for personal use; check licence before any distribution.

---

## 8. Rules for any AI agent working on this repo

1. Read this file, then `WORKINGS.md`, before changing anything.
2. Stay inside the module you were asked to work on. Never import another module's code.
3. Cross-module communication happens only through database tables defined in `db/migrations`. Do not change a table schema without updating the migration and the affected module READMEs.
4. Log every real action to `agent_events` using the `shared` logbook writer.
5. Do not add paid services, paid APIs or new broker order functionality.
6. Always add source fallbacks and caching for external data.
7. Keep module READMEs current: what it reads, what it writes, what config it needs.
8. Never present output as investment advice.

---

## 9. Build order

1. `db/` migrations (candles, agent_events) and `shared/`
2. `ingest/`
3. `logbook/`
4. `dashboard/` (live feed first)
5. `signals/`
6. `backtest/`
7. `news/`
8. `analysis-agents/` (discussion area)
9. `browser-agent/` (last)

---

## 10. Open decisions

- Which price source to use first (needs: does the user have a demat account with Angel One, Upstox or Fyers?).
- Which LLM: Gemini free tier or local Ollama (depends on laptop capability and privacy needs).
- Watchlist size (decides how often agents can run within free-tier limits).
- Whether to use Langfuse (open-source LLM tracing, self-hostable) on top of the custom logbook.

---

## 11. Notes on data quality

- Scraped NSE data can have missing days or unadjusted splits. Compare two sources occasionally.
- Scraper libraries can break when NSE changes its website. Keep at least two sources and cache everything.
- Candlestick patterns alone rarely predict prices. Always validate with backtests and treat results as research, not prediction.
