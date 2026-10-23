# Logbook

Read-only command-line viewer for `agent_events`. Writes nothing and emits no
events. Install `shared` and `logbook/requirements.txt` in the root virtualenv.
Configuration: root `.env` with Supabase URL and Python service key.

From repository root:

```sh
python logbook/main.py tail
python logbook/main.py tail --status failed --module ingest --symbol TCS
python logbook/main.py run <run-uuid>
python logbook/main.py summary --since 24h
```

Tail returns up to 1,000 events (50 by default). Run and summary paginate through
all matching rows. Events are JSON lines; summary groups by module and status.
Read failures exit 1. There is no continuous terminal follow mode; use the live
dashboard. An empty result is explicitly shown.
