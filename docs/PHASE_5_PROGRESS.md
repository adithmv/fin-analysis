# Phase 5 verification and remaining work

Updated 2026-10-24. Phase 5 is in progress, not accepted as complete.

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
- Two real bonus factors proposed, not approved: RELIANCE 2024-10-28 and
  HDFCBANK 2025-08-26, both 0.5. Independent Yahoo comparison passed for 14
  sessions each (maximum relative errors 3.75e-8 and 2.57e-8 respectively).
  Human approval remains pending. Signals/backtests remain raw.
- Migration 010: atomic incident recording, notification cooldown and owner-only
  operations. Repeated failing check after acknowledgement preserved one incident;
  a passing check resolved it. Transactional fixture rolled back.
- Telegram adapter uses plain text, no paid broadcasts, sanitized failure messages.
  Four offline notifier tests passed. Live health run completed 34 checks without
  failed groups; 11 current incidents are visible in the dashboard. No messages sent.
- `/ops`, `/alerts`, `/documents`, `/corporate-actions` added. Playwright passed
  anonymous denial, owner session validation, invalid input, cross-origin denial,
  chart previews and mobile layout. No real approvals made by tests.

## Pending

Twenty browser tests passed, including a real Chromium context with intercepted
fixture responses, external-link denial and disabled script/subresource requests.
The browser collector now has a guarded deterministic recipe path, isolated browser
contexts, shared page budgets and text-hash deduplication. All live sites remain
disabled; candidate selectors are not commissioned. AI navigation, PDF integration
and downstream document ingestion remain unfinished.

Backup tooling and `ops/RUNBOOK.md` are prepared. Four offline tests verify password
handling, repository exclusion, second-copy checksums, config export without secrets,
and failure without a success manifest. No real dump, cloud receipt or restore has
been verified. Backup retention does not delete files yet.

Telegram credentials/delivery test, remaining health rules, browser guard and source review,
remaining operations views, human adjustment approval and rerun of studies, backups and actual restore,
retention dry-run review, security/dependency/history scans, expanded CI,
startup integration and five real trading days unattended.

Owner chose Telegram and Google cloud storage for the second copy. Google Drive
was suggested (not yet connected); Google Docs cannot hold a restorable dump.
Local bot credentials and PostgreSQL DATABASE_URL requested, fields prepared in
ignored `.env`. Laptop is the scheduler host. Docker is installed but its engine is not running;
the restore drill needs a local scratch Postgres instance. No external messages
have been sent. Existing Phase 3 human-labelled news review remains deferred.

The Supabase advisor found no new database security findings; its existing
leaked-password-protection warning remains. The sole dashboard account uses a
generated password. See [Supabase password security](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
