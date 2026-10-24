# Operations runbook

Phase 5 is not commissioned. Schedules and Telegram delivery remain disabled. Five trading days unattended and a real restore drill have not happened. See `docs/PHASE_5_PROGRESS.md` for current acceptance evidence.

## Inspect and recover jobs

Open `/ops`, sign in as the owner, and follow a job's logbook link. Check its dependencies, failure reason and module configuration. Fix the cause before Retry; Cancel terminates a running child after the worker's next heartbeat check. A retry gets a new attempt/run identity. Repeated source refusal must be fixed by disabling the source, not by repeated retries.

From the repository root, use `scheduler/.venv/Scripts/python.exe scheduler/main.py status`. The scheduler `run` loop enqueues enabled schedules; the separate `runner` loop executes jobs. Both require their own persistent process on this laptop. Do not enable startup tasks until the commissioning checklist is met. Sleep or shutdown prevents execution; missed schedules are bounded by configured catch-up windows. Never run the old research request worker alongside scheduled research workers.

## Alerts

Open `/alerts` for incidents even when Telegram is unavailable. Acknowledge means seen; it does not erase the failure. A healthy subsequent check resolves the incident. Check rule, subject and latest logbook entries first. Telegram delivery requires the two local credentials and a successful private-chat test before setting `notifications_enabled: true`. Normal batches are at least ten minutes apart; quiet hours suppress warnings, not critical incidents. Failed sends keep incidents visible. A crash after delivery but before receipt recording can produce a duplicate.

For stale prices/signals, inspect exchange calendar, permitted data source and upstream jobs before rerunning. Do not invent missing sessions or silently mix adjusted and raw prices. For source failures, inspect robots/terms and HTTP status, then disable refused sources. For heartbeat/dead-job alerts, inspect laptop sleep, scheduler processes, queue leases and module environments. For disk/database capacity alerts, inspect usage and backup status; review a retention dry run before deleting. For model budget or verification alerts, inspect `/usage` and evidence quality; wait for budget reset or reduce scheduled work. For backup alerts, follow the backup checks below. Confirm fixes by rerunning the corresponding health check, not by manually resolving an active failure.

## Backups and recovery

`ops/backup.ps1` on Windows (or `ops/backup.sh` on Unix) runs a compressed PostgreSQL custom-format dump. Install compatible `pg_dump` and `pg_restore` tools on PATH. Put a direct/session-pooler URL with database password in ignored `.env` as `DATABASE_URL`; use `BACKUP_SECONDARY_DIR` for a separate private destination outside the repository. Default first destination is `C:\dev\fin-analysis-backups` on this laptop.

The script checks archive contents, copies config/migrations/`.env.example`, writes SHA-256 hashes, and verifies the second filesystem copy. It never exports real environment files or deletes old dumps. Database dumps contain private research and account data: keep both destinations private. A Google Drive desktop sync folder can be the second destination once configured; check the cloud upload separately. A local copy does not prove Google received it. Google Docs is not a database archive destination.

Credentials are passed through a temporary PostgreSQL password file, removed on exit. They are not command arguments. On Windows this relies on the user's private temporary directory permissions. The connection requires TLS. See [PostgreSQL password files](https://www.postgresql.org/docs/17/libpq-pgpass.html) and [custom-format dumps](https://www.postgresql.org/docs/current/app-pgdump.html).

A successful archive-list check is not a restore test. Restore only into a disposable database, using compatible PostgreSQL and Supabase roles/extensions/auth schema dependencies. Verify the destination is not production before `pg_restore`. Inspect the archive, restore with errors treated as fatal, compare table counts and representative records, and test expected views/RLS. Record the actual result and dump checksum. This workflow has not yet been exercised against a real dump; do not claim recovery readiness. Keep existing backups until the retention policy and a successful restore are reviewed.

## Keys and source changes

Create a replacement key with the provider, update only the ignored local environment file, restart affected processes, test access, then revoke the old key. A Gemini key previously shared in chat still needs replacement. Never put credentials in commits, reports, screenshots or logbook fields.

Disable a source in its module configuration and database source row where applicable, then confirm subsequent scheduled work skips it. Record the reason and review date in `docs/SOURCES_TERMS.md`. Browser sources additionally require exact host/path approval and accessible robots rules. Never enable a source solely because a client library can fetch it.
