# Architecture

This is a private local research application. Next.js serves the dashboard on loopback; Supabase stores market data, research snapshots and operations state. Python modules have independent environments and communicate through database tables. Shared code contains only database access and sanitized logbook helpers. No module imports another module's implementation.

| Module | Reads | Writes |
| --- | --- | --- |
| ingest | Permitted market sources, watchlist, calendar | Raw candles, corporate actions, proposed adjustment factors |
| signals | Approved adjusted candle view, calendar | Indicator values and dated signals with version/input hashes |
| news | Permitted feeds and announcements | Articles, symbol links, sentiment, embeddings, news events |
| backtest | Prices, matching signal version, news events | Historical statistics, strategy runs/trades, mature report outcomes |
| analysis-agents | Data available by a fixed cutoff | Frozen evidence, discussions, verified claims, reports |
| browser-agent | Explicitly enabled reviewed sources | Untrusted extracted documents; all live sources currently disabled |
| scheduler | Local schedules, calendar, queue | Dependency graphs, leases, attempts and heartbeat checks |
| alerts | Source freshness, queue, budgets and health | Deduplicated incidents, optional Telegram batches |
| ops | Database and non-secret configuration | External backup archives, checksums and retention dry-run reports |

Public market tables have read-only policies. Research and operations tables are owner-readable. Dashboard writes go through server routes that verify the user session and the owner record before invoking restricted database functions. The service key stays server-side. Raw page text and article text are untrusted evidence, never code or system instructions.

Queue claims use database locks; each module has one active job at a time. Heartbeats and attempt identities reject late completion from an obsolete worker. Queue delivery remains at least once: module writes must be idempotent. Child processes use fixed command arguments and their own environments. The runner passes RUN_ID through the environment so child actions join the job's logbook history.

Raw candles remain unchanged. `candles_adjusted` applies only human-approved split/bonus factors and avoids double-adjusting Yahoo data. Signal and backtest configuration now select the adjusted basis. Historical research snapshots remain immutable; their original evidence and basis must not be silently rewritten.

Deployment is local only. Schedules, browser sources and Telegram delivery remain uncommissioned. See `docs/PHASE_5_PROGRESS.md` for gaps, `docs/SOURCES_TERMS.md` for access decisions and `ops/RUNBOOK.md` for recovery procedures.
