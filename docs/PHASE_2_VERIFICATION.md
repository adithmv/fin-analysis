# Phase 2 verification — 2026-10-23

## Stored history and calculations

- HDFCBANK, ICICIBANK, INFY, RELIANCE and TCS each have 743 daily candles from
  2023-10-25 through 2026-10-22 (3,715 total active-watchlist candles).
- Migrations 002 and 003 are applied. All six new tables have RLS and public
  SELECT only; SQL privilege checks confirm no public INSERT/UPDATE/DELETE.
  Signal-day replacement is an atomic service-role-only function.
- Signals run `00e4fe3a-d016-4140-b035-904b43bf65f5` processed all five stocks.
  Repeat `496d0352-0082-497b-9e12-bc604dee903c` skipped all five with zero writes.
- Live TCS drill deleted the latest day's reproducible derived signals, restored
  exactly that day, compared all fields except the new computation timestamp,
  and confirmed the next run wrote nothing. Script: `signals/tests/cloud_drill.py`.
- Short-history run `98bab081-fba5-43b0-bead-9094aeba8170` processed the nine stored
  SBIN fallback candles while TCS continued normally; long indicators stayed null.
- Two full event studies (`d8a2fa7c-8f0d-4cb8-a189-b673f8ba490f` and
  `46304523-09c2-48ef-ab61-90f29adeab62`) each saved 2,400 results. A database join
  compared counts, means, medians, win rates, baselines and edge: zero differences.
  The second run uses the faster array-based calculation.
- All five stocks have all/in-sample/out-of-sample results for SMA crossover
  (`44d810a3-1e81-4b29-9e83-f0ccf45a68b3`), RSI reversion
  (`379bdc36-d4fa-4189-b5dd-a63f055cc41a`), pattern/trend
  (`bbc0b282-56f6-42dd-91f1-c258866de74b`), and buy-and-hold
  (`f2c83245-878c-4508-acb0-b319b1da7257`). Each strategy includes a matched benchmark.
- Repeated TCS strategy runs `47067b6a-a7d2-4532-92d4-423f077dc6a4` and
  `a5b6cb70-61a9-4570-b37b-169a93dfe6ad` have identical configs, commit hashes,
  metrics, curves and trades. Script: `backtest/tests/cloud_drill.py`.

## Checks and failure drills

- 31 shared/ingestion tests, 8 signal tests and 7 backtest tests pass.
- Signal tests independently calculate SMA, EMA, RSI and Bollinger bands; verify
  null warm-up, positive/negative pattern examples, one-day crossings, confirmed
  swing dates, quality flags, incremental repair and future-prefix invariance.
- Simulated stored-table test verifies a rule/version change replaces old rows
  and removes an obsolete signal. Short-history handling logs the skipped reason.
- Injected 50% jumps and long gaps trigger flags; backtest tests confirm excluded
  windows cannot enter outcome calculations. Real flagged histories also emit
  `apply_exclusions` warnings in the cloud logbook.
- Hand-checked event/strategy fixtures verify next-open entries, both-side costs,
  time/sample boundaries, independent counts, matched baseline and buy-and-hold.
- Broken credentials were tested separately in both module environments: nonzero
  exit, clear failure, no credential in captured output. Local `.env` was unchanged.
- Connection resets occurred during live verification. Idempotent backtest reads
  now retry three times; log writes retry connection-setup failures only, avoiding
  duplicate writes after ambiguous timeouts. Persistent failures remain explicit.
- Six Playwright scenarios pass: chart/mobile, live event and offline/reconnect,
  logbook filters/run navigation, overlays/range/signal filters, Signal Lab and
  backtest metrics/trades. Browser error listeners report no application errors.
- Production build and TypeScript checks pass. GitHub Actions checks ingestion,
  each isolated research environment, and the dashboard build on every push.
- Supabase security advisor: no findings. Performance advisor only notes new
  indexes not yet used; retained for the intended lookup paths. See
  [unused-index guidance](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index).

## Deliberate choices and limits

- Full history is calculated, while only changed/missing days are written. This
  preserves recursive indicator seeds and cumulative OBV exactly; a fixed tail would not.
- Event horizon 1 means next session open to that session close. Bearish directional
  evidence always pays costs; simply negating a net long result would reward costs.
- Exclusions are retrospective data filters, not tradable forecasts. Both strategies
  and benchmarks use them, including liquidation before an excluded window.
- Costs are illustrative placeholders. The universe is small; pooled stock events
  can be correlated. Independent counts remove within-stock horizon overlap only.
- No automated parameter sweep was added (optional in the specification). Runs
  record one combination, and the dashboard warns if a future run records a sweep.
- Dates and metrics use stored daily data. Signals are loaded on demand for the
  selected chart range and update on reload; action events update live.
- Logbook remains best-effort if the database is completely unavailable. Its failure
  is printed without credentials; no durable offline event queue is claimed.
- No paid API, trade execution, LLM agent or Phase 3 functionality was added.
