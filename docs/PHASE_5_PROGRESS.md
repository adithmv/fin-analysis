# Phase 5 verification and remaining work

Updated 2026-10-25. Phase 5 is in progress, not accepted as complete.

## Verified foundations

- Migration 008: owner-readable operations tables; no browser write grants;
  service-only queue functions. SQL contract checks passed with rollback.
- Live concurrency drill: two simultaneous enqueues produced one 12-stage pipeline;
  two workers claimed all 12 distinct jobs once. Fixture rows removed afterward.
- Retry backoff, attempt ownership, expired lease recovery, cancellation, transitive
  dependency failure and failure digest eligibility passed transactional checks.
- Runner tests cover child RUN_ID, secret redaction, nonzero exit, timeout and
  cancellation before launch. Schedules remain disabled during rollout.
- Migration 009: security-invoker adjusted view; raw candles never modified.
  Hand-calculated SQL checks passed: bonus 0.5, split 0.2, product 0.1, inverse
  volume, exact IST ex-date, unchanged series, future action ignored, already
  adjusted Yahoo rows untouched. Test approvals were synthetic and rolled back.
- Calendar loaded for 2023-2026 (1,461 rows). Library holidays plus official
  special-session overrides now have zero conflicts with stored candle dates.
- Two real bonus factors reviewed: RELIANCE 2024-10-28 and
  HDFCBANK 2025-08-26, both 0.5. Independent Yahoo comparison passed for 14
  sessions each (maximum relative errors 3.75e-8 and 2.57e-8 respectively).
  Owner approved both in chat on 2026-10-25; decisions were recorded using the
  audited review function. Signals 2.2.0 now use adjusted prices. Full recomputation
  succeeded for all six active symbols (4,453 sessions, zero failures). Neither
  affected stock retains the false possible-split flag. On the ex-dates, raw versus
  adjusted moves are RELIANCE -49.7552% / +0.4895% and HDFCBANK -50.4404% / -0.8808%.
- Adjusted reruns completed: 2,400 technical event-study results; 15 result rows
  for each of four strategies (SMA crossover, RSI reversion, pattern/trend and
  buy-and-hold); 840 news results; 780 sentiment results. Historical raw runs remain
  in the database with their original provenance.
- Migration 010: atomic incident recording, notification cooldown and owner-only
  operations. Repeated failing check after acknowledgement preserved one incident;
  a passing check resolved it. Transactional fixture rolled back.
- Telegram adapter uses plain text, no paid broadcasts, sanitized failure messages.
  Four offline notifier tests passed. Live health run completed 34 checks without
  failed groups; 11 current incidents are visible in the dashboard. No messages sent.
- `/ops`, `/alerts`, `/documents`, `/corporate-actions` added. Playwright passed
  anonymous denial, owner session validation, invalid input, cross-origin denial,
  chart previews and mobile layout. No real approvals made by tests.
- After the approved adjustments, charts default to the adjusted basis. TypeScript
  checks and all four operations/research browser tests passed, covering stock
  overlays, event-study samples, backtest details and protected operations routes.

## Pending

Twenty browser tests passed, including a real Chromium context with intercepted
fixture responses, external-link denial and disabled script/subresource requests.
The browser collector now has a guarded deterministic recipe path, isolated browser
contexts, shared page budgets and text-hash deduplication. All live sites remain
disabled; candidate selectors are not commissioned. AI navigation, PDF integration
and downstream document ingestion remain unfinished.

Daily backups are live through Windows Task Scheduler at 20:30 IST. Five offline
backup tests passed. A real scheduled run on 2026-10-25 completed with result 0,
producing `20261025T154041Z-d3322358`. Both local and Google Drive filesystem
copies passed SHA-256 checks; the four files were also confirmed in Drive online.
The laptop must be awake and signed in with Drive desktop available. See
`ops/RUNBOOK.md` for setup, retries, runtime requirements and troubleshooting.

A two-table restore smoke test of `20261025T113836Z-8e454b4b` into disposable
PostgreSQL 17.11 matched all 4,482 candles and six watchlist rows against production.
Its `restore-smoke.json` report is saved beside both backup copies. The scratch
server was stopped. Full Supabase recovery (including roles/extensions/views/RLS)
is still pending; no backup retention deletion is enabled.

Remaining health rules and source review, remaining operations views, full restore,
retention deletion implementation, final commissioning checks, pipeline startup
integration and five real trading days unattended remain pending.

All nine jobs in expanded GitHub CI passed for a3f1e54 and adjustment commit 150593f. Security and dependency
findings/fixes are in `PHASE_5_SECURITY.md`. Retention dry run executed against the
database: zero candidates in all four categories; reviewed, no deletion performed.

Owner chose private Telegram chat and Google Drive for the second backup copy.
Telegram credentials were corrected locally and a live test message was received
and confirmed by the owner. Automatic notifications are now enabled, with Windows task `Fin Analysis Alert Checks` running every 15 minutes. A scheduled run completed with result 0 and 34 checks, no failed groups; a fresh Telegram connection test was accepted. Eleven genuine stale-data/source warnings remain. False alarms for deliberately disabled sources and the uncommissioned scheduler were fixed; failed check groups now produce incidents. All 16 alert/backup tests passed. DATABASE_URL
and BACKUP_SECONDARY_DIR are configured in ignored `.env`; database connectivity
and TLS to the session pooler were verified. Primary backups are outside the repo
at `C:\dev\fin-analysis-backups`; secondary copies use
`G:\My Drive\Fin Analysis Backups`. Existing Phase 3 human-labelled news review
remains deferred.

The Supabase advisor found no new database security findings; its existing
leaked-password-protection warning remains. The sole dashboard account uses a
generated password. See [Supabase password security](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
