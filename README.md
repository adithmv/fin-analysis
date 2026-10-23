# Indian Market Research

Personal, read-only NSE stock research. Phase 1 builds daily price ingestion,
validation, an action logbook, and a live dashboard. No order placement or LLMs.

Implementation is in progress. See [PHASE_1.md](PHASE_1.md) for the specification.
Each completed step is checked, committed with a plain-language description,
and pushed to GitHub.

## Modules

Python modules cooperate through database tables, importing only `shared`.
`ingest` writes candles, `logbook` reads events, and `dashboard` displays both.
Later phases add signals, backtesting, news, and evidence-based discussions.

All displayed findings are analysis for research, not investment recommendations.
