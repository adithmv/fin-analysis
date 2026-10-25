# How the application works

Start with the watchlist and exchange calendar. Ingestion stores daily OHLCV with source, adjustment and fetch timestamps. A missing expected trading session differs from a holiday. An unknown calendar date stops scheduling rather than guessing. The current calendar covers 2023–2026; later years require reviewed source data.

Corporate actions create proposals. A reviewer compares each proposed adjustment with an independent price series, then approves or rejects it with an audit note. The approved view adjusts historical prices and inverse-adjusts volume without modifying raw candles. RELIANCE's 2024-10-28 and HDFCBANK's 2025-08-26 bonus factors were explicitly approved on 2026-10-25.

Signals compute indicators, candlestick patterns, rules and quality flags. Dated trend markers carry configuration, input hashes and the price basis. Recalculation replaces each batch transactionally so obsolete flags disappear. Backtests refuse mismatched inputs rather than combining stale signals with revised prices. Historical event studies and strategies retain their configurations and provenance, separate in-sample and out-of-sample periods, and use next-session execution assumptions with illustrative costs.

News collection stores source snippets and provenance. CPU models add sentiment and embeddings; deterministic rules link symbols and classify events. Search is served by a loopback-only process. Human-labelled accuracy review remains deferred. The browser collector is a separate guarded source module: it checks exact domains/paths and robots rules, stops on access challenges, and stores extracted text as untrusted documents. Its live sources, AI navigation and downstream news handoff are not commissioned.

Research threads freeze evidence available at a cutoff. Statements must reference that evidence, and verification results accompany reports. Stored reports are research records rather than trade instructions. Later outcome grading requires actual future market sessions; elapsed time and market data cannot be simulated as acceptance evidence. Model calls share a database-enforced budget.

The intended daily queue is ingestion → signals and feed collection → news processing, followed by research, outcome grading and a digest. The database creates each dependency graph atomically using an idempotency key. Failed stages retry with bounded backoff; exhausted stages prevent success-dependent work. Digest work can run after terminal failures. Expired leases recover after heartbeat timeout. Schedules remain disabled until sources, credentials and recovery checks are ready.

Health checks produce one active incident per rule/subject. Acknowledgement preserves the incident; a healthy check resolves it. Telegram batches are optional, limited and private. Backups are compressed database archives plus non-secret rebuild files, stored outside the repository with a verified second filesystem copy. Cloud receipt and a real scratch restore are separate requirements. Retention is dry-run only today; no old records have been deleted.

Every action should be traceable in the logbook, every code increment should have a plain-language Git commit, and every acceptance claim should point to completed checks. Read `docs/PHASE_5_PROGRESS.md` before treating Phase 5 as complete.
