# Database

Owns SQL migrations defining the contracts between modules. Run
`migrations/001_init.sql` once in the Supabase SQL editor of a new project.
The file was created with the Supabase CLI then moved to the specification's
numbered migration path. Do not apply it twice.

- `watchlist`: `(symbol, exchange)` key, active flag, added time.
- `candles`: `(symbol, exchange, timeframe, ts)` key, numeric OHLC, nullable
  nonnegative volume, source, adjusted flag, retrieval time. Daily `ts` is midnight
  Asia/Kolkata converted to UTC. Database constraints reject invalid prices.
- `agent_events`: append-only events grouped by UUID run, indexed for filters and
  run timelines. Service-role access is select/insert only on this table.

Reads/writes: this module defines schemas; runtime writes belong to Python.
Configuration: a dedicated Supabase project; no credentials in migration files.
Events: none (DDL setup only).

RLS and explicit grants permit anonymous **read-only** access as specified for
Phase 1. This includes the watchlist and sanitized logbook: they are not private.
Before storing portfolio/private information, replace these read policies with
single-owner authenticated policies. Browser writes are denied. Realtime is
enabled for events and candles. Service keys stay in local Python configuration.

Verification: inspect the three tables, attempt an insert with the public key
(must fail), and subscribe to `agent_events` before running ingestion. Cloud
verification requires a configured project.
