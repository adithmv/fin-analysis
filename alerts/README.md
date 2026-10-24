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
