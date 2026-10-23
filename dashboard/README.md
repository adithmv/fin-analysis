# Dashboard

Read-only Next.js viewer for `watchlist`, `candles`, and `agent_events`. Writes
nothing and emits no business events. Subscribes to events/candles via Supabase
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
- `/logbook`: paginated events; `/logbook/run/[id]` shows a chronological run.
- `/stocks`: active watchlist, latest close, provenance and weekday-based health.
- `/stocks/[symbol]`: daily candles and volume, recent symbol activity.

Missing configuration/data and connection errors have explicit empty/error
states. Values are research data, not recommendations. Health approximates trading
days using weekdays; market holidays can trigger stale-data warnings.

## Checks

`npm run typecheck`, `npm run build`, `npm audit`.
`npx playwright install chromium`, then `npm run test:e2e` tests the configured
live project: chart navigation, mobile width, event filters, live delivery, and
network disconnect/reconnect. The live-delivery test invokes the root Python
environment to write one clearly named verification event; no secrets enter the
browser. Tests need the initial watchlist ingestion completed.

Charts use Lightweight Charts under Apache-2.0 with TradingView attribution.
Next.js generates `AGENTS.md`; keep its version-specific guidance in the repo.
