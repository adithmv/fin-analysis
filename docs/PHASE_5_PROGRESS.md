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
  HDFCBANK 2025-08-26, both 0.5. Independent source comparison and human review
  must precede changing the default price basis. Signals/backtests remain raw.

## Pending

Alerts/channel setup, browser guard and source review, operations dashboard,
adjustment review/comparison and rerun of studies, backups and actual restore,
retention dry-run review, security/dependency/history scans, expanded CI,
startup integration and five real trading days unattended.

Questions sent: preferred alert channel and second backup destination. Laptop is
the assumed scheduler host. Docker is installed but its engine is not running;
the restore drill needs a local scratch Postgres instance. No external messages
have been sent. Existing Phase 3 human-labelled news review remains deferred.

The Supabase advisor found no new database security findings; its existing
leaked-password-protection warning remains. The sole dashboard account uses a
generated password. See [Supabase password security](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
