# Dashboard

Next.js viewer for market data, research, and the logbook. Phase 4 adds single-owner login and insert-only research requests; the browser never writes messages or reports. Subscribes to events/candles via Supabase
Realtime and refetches after reconnect; a 15-second poll covers missed messages.

## Run

Create `dashboard/.env.local` containing **only**:

```dotenv
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-publishable-key
```

Despite the compatibility variable name, the value may be a modern publishable
key. Never put the service/secret key anywhere in this module.

```sh
cd dashboard
npm ci
npm run dev
```

Open http://127.0.0.1:3000. For production locally: `npm run build`, then
`npm start`. Both servers bind to loopback. Pages:

- `/`: live activity, module status, filters and event details.
- `/login`: sign in using locally configured owner credentials.
- `/threads` and `/threads/[id]`: private live discussions, evidence inspection, reports and queued questions.
- `/usage`: reserved model attempts, tokens and remaining application budget.
- `/track-record`: mature outcomes, live/replay separation and small-sample cautions.
- `/logbook`: paginated events; `/logbook/run/[id]` shows a chronological run.
- `/stocks`: active watchlist, latest close, provenance and weekday-based health.
- `/stocks/[symbol]`: candles, SMA/EMA/Bollinger overlays, pattern markers and hover descriptions,
  RSI/MACD/volume-average panels, trend inputs, quality flags and filterable recent signals.
- `/lab`: latest event-study run, independent counts, matched baselines, edge, and
  side-by-side in-sample/out-of-sample evidence. Small samples are labelled and greyed.
- `/backtests` and `/backtests/[runId]`: saved configurations, costs, benchmark comparisons,
  equity curves, sample comparisons and individual trades. Underperformance and sweeps are flagged.

Indicator/signal queries are paginated and constrained to the selected 3-month,
1-year or full-history date range. They load on demand; reload after recalculating
signals. They do not use Realtime. Chart panels share zoom/pan. The live event feed
continues to receive signals/backtest actions through its existing subscription.

Missing configuration/data and connection errors have explicit empty/error
states. Values are research data, not recommendations. Health approximates trading
days using weekdays; market holidays can trigger stale-data warnings.

## Checks

`npm run typecheck`, `npm run build`, `npm audit`.
`npx playwright install chromium`, then `npm run test:e2e` tests the configured
live project: chart navigation, mobile width, event filters, live delivery,
network disconnect/reconnect, overlays, signal filters, Signal Lab, and benchmark
comparisons. The live-delivery test invokes the root Python
environment to write one clearly named verification event; no secrets enter the
browser. Tests need the initial watchlist ingestion completed.

Charts use Lightweight Charts under Apache-2.0 with TradingView attribution.
Next.js generates `AGENTS.md`; keep its version-specific guidance in the repo.
