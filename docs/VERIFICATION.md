# Phase 1 verification — 23 October 2026

## Implemented and exercised

- Free Supabase project `fin-analysis` in Mumbai; initial migration applied.
  The old `recipebook` project was deleted at the user's explicit request.
- Three tables, numeric price constraints, unique candle keys, filter/run indexes,
  explicit public read grants, RLS, append-only service access to events, Realtime.
- Python client successfully reads and writes; action logger tests cover redaction,
  automatic timing, exception propagation and database logging failure.
- Five active watchlist symbols each loaded 247 daily candles, ending 22 October
  2026. Daily dates were checked against raw NSE timestamps and converted to IST.
- Repeat watchlist run: zero writes, five skipped symbols, no external fetches.
- jugaad/NSE and yfinance both returned live data. Forced primary failure used
  real yfinance fallback for SBIN and recorded both attempts.
- Invalid symbol run `661a4af9-884f-4ecb-bef7-c98c0093cc45`: NOTASTOCK failed,
  TCS succeeded, process exited 1 and summary reported both outcomes.
- Simulated network failure after the first real fetch: TCS succeeded, INFY
  retried then failed, run completed without writing invalid rows. This was
  injected at the source boundary, not by disabling the user's whole network.
- Broken-key drill used an environment override: clear authentication error,
  exit 1, no source calls or database writes.
- Public read access succeeded for all three tables; public insert was denied.
  Supabase security advisor returned no findings.
- Cross-check run `47665c65-d819-46e5-8626-10803f76b1ae`: OpenChart unavailable,
  then Yahoo comparison succeeded with no differences above 0.5%.
- Logbook CLI: tail, status filtering, run timeline, duration summary exercised.
- Dashboard: production build and TypeScript check; watchlist-to-chart navigation,
  desktop/mobile chart rendering, event filters and run navigation checked.
- Browser test inserted a real code-written event and observed it without refresh.
  Browser networking was disabled/re-enabled; indicator changed to reconnecting
  and recovered to live. A stale-socket bug discovered by this drill was fixed.
- 30 Python tests passed. Three browser scenarios passed (chart/mobile in the
  first run; reconnect and filters rerun after fixes). Test artifacts are local
  in `dashboard/test-results`, excluded from Git.

## Material limits

- OpenChart equity search returned unrelated indices during testing. Exact-match
  protection rejects these results; NSE and Yahoo provide the two working sources.
- Yahoo's split-adjusted history cannot be blindly appended to an unadjusted NSE
  series. Such fallback writes are rejected and logged. Cross-checks can compare
  sources but record the adjustment distinction.
- Missing weekdays and stale-data health are approximations without an exchange
  holiday calendar. Warnings are expected on holidays and corporate actions.
- Historical gaps preceding the latest stored candle require `--since`/`--days`.
- Source adapters may make multiple HTTP requests internally; usage counts are
  fetch-operation counts. Suppressed library errors may be classified as empty
  results instead of their original HTTP status.
- Best-effort logging cannot persist events during a database outage; it reports
  the failure to stderr. Multi-batch candle writes are not one transaction, but
  every completed batch is validated and reruns are idempotent.
- Public-key read policies expose market data, the watchlist and sanitized events.
  No private portfolio data should be added under these policies.
- The performance advisor reported an informational unused status-filter index
  on this small new dataset; retained because the logbook uses that filter.
- Phase 2+ remains unimplemented. No scheduler or job table was added.

## Reproduce

See the root README, module READMEs, `scripts/verify_cloud.py`,
`scripts/failure_drills.py`, and `dashboard/tests/dashboard.spec.ts`.
