# Shared

Database client and action logbook writer: the only shared Python code.

Install from repository root: `uv pip install -e ./shared` (or `python -m pip install -e ./shared`).
Configuration: root `.env` contains `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`.
`get_client()` returns a cached client with a 20-second REST timeout.
`bulk_upsert(client, table, rows, on_conflict)` writes batches of 500 and raises
database failures so ingestion cannot report false success.

Reads/writes: generic client; logger inserts only into `agent_events`.
`log_event(...)` returns a boolean; failures print a generic stderr warning and
never raise. `action(...)` emits started and terminal events with timing and
re-raises the original work exception. Metadata and summaries are sanitized for
known environment secrets, sensitive field names, JWTs, and token assignments.
Never deliberately pass sensitive data: redaction is defense in depth.

Tests: `python -m pytest shared/tests`.
Limit: events cannot be persisted while the database is offline; stderr makes
that loss explicit. There is no background event queue in Phase 1.
