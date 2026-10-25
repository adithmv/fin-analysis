# Health checks and Telegram

Use this module's `.venv` and install `requirements-lock.txt` plus `-e ./shared`.
`python alerts/main.py check` records independent check groups and maintains one
incident per rule/subject. Acknowledgement preserves the incident; a passing
check resolves it. A failed check never treats missing observations as recovery.
`digest` previews the daily summary until notifications are enabled.

The owner selected Telegram. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in
the ignored root `.env`; start a private chat with the bot first. Run
`python alerts/main.py test-notify`, then enable `notifications_enabled` in
`config/alerts.yaml`. No token, URL containing the token, personal question or
credential appears in notifications or errors. Only operational summaries leave
the machine. Tests use a fake HTTP transport and send no messages.

One batch of at most eight incidents is reserved in Postgres every ten minutes.
Critical incidents bypass quiet hours; warnings wait until 07:00 IST; info items
belong in the daily digest. Resolution notices are sent only for previously
notified incidents. Failed delivery leaves incidents on `/alerts` for retry.
Delivery is at least once: a crash after Telegram accepts a message but before
the database acknowledgement can cause a duplicate after the cooldown.

[Telegram's FAQ](https://core.telegram.org/bots/faq#how-do-i-avoid-hitting-limits)
and [sendMessage API](https://core.telegram.org/bots/api#sendmessage) checked
2026-10-24. Normal bot messages are free within limits; paid broadcasts are
explicitly disabled. The configured ten-minute batch rate is conservative.
Supabase Free's [database allowance](https://supabase.com/pricing) is configured
as 500,000,000 bytes; this measures database size, not provider disk/WAL usage.
Free accounts should maintain their own [off-site backups](https://supabase.com/docs/guides/platform/backups).

Current checks: calendar availability; per-symbol candle and signal freshness;
zero-volume streak; source enabled/failure/staleness; dead jobs; scheduler
heartbeat; database/local disk size; backup recency; daily model budget;
consecutive discussion failures; recent verified-claim fraction. Verification
fraction is a mechanical validation metric, not model accuracy.
Remaining Phase 5 checks are tracked in `docs/PHASE_5_PROGRESS.md`.

No monitor on this laptop can notify while the whole laptop is off. An external
dead-man monitor would be needed for that guarantee; none is configured yet.

## Live laptop monitoring

As of 2026-10-25, private Telegram delivery is enabled and Windows task
`Fin Analysis Alert Checks` runs every 15 minutes. It requires the signed-in user,
an awake laptop and internet. It retries failures twice, two minutes apart, skips
overlapping runs and catches missed starts when available. Market/research pipeline
schedules remain disabled independently. The daily digest is not scheduled yet.

The Windows task needs a host-accessible Python runtime. From the repository root:

```powershell
uv venv .cache/alerts-runtime/.venv --python C:/Python314/python.exe
uv pip install --python .cache/alerts-runtime/.venv/Scripts/python.exe -r alerts/requirements-lock.txt -e ./shared
./ops/install-alert-task.ps1
```

Run `ops/alerts.ps1` for an immediate check; inspect `.cache/alerts/last-run.log`
and Task Scheduler's last result (0 means success). Each completed check records
`alert_monitor_completed` with its check and delivery summary. An actual scheduled
run passed on 2026-10-25, with 34 checks and no failed groups; Telegram separately
accepted a live connection test. Six stale-price and five stale-source warnings
remain genuine while collection is not commissioned. Warnings wait during
22:00–07:00 IST quiet hours; critical incidents bypass quiet hours.

Intentionally disabled sources and an intentionally stopped pipeline scheduler are
recorded as monitoring paused, rather than failure. Stale data for enabled sources
and watched symbols still warns. Failed check groups create their own critical
incident and preserve prior incidents until the group succeeds. Daily backups now
warn after two days without a successful verified filesystem copy. Cloud receipt
and full restore checks remain separate.

Notifications prioritize critical incidents and bound the batch before sending,
so incidents omitted for message length are left pending for a later batch. Tests
cover delivery failures, quiet hours, batch limits, disabled monitoring and check
failures. No external monitor can detect a powered-off laptop in this setup.
