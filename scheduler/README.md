# Scheduler and runner

The scheduler enqueues bounded, idempotent pipelines in Postgres. The runner launches
fixed commands in each module's own virtual environment. It imports only `shared`.
`job_queue.py` deliberately avoids shadowing Python's built-in `queue` module.

Create `scheduler/.venv`, install `requirements-lock.txt` and `-e ./shared` from the
repository root. Start `scheduler/main.py run` and `scheduler/main.py runner` as
separate processes. Both accept `--once` for diagnosis. `status` lists recent jobs.
`enqueue --module signals --kind all --key manual:signals:YYYY-MM-DD` requests a
configured command. `retry --id ID` retries a terminal job; `cancel --id ID` stops
a queued job or causes its running process tree to stop at the next heartbeat.

Schedules are IST. The supported cron subset has minute/hour/weekday ranges,
lists and steps; day-of-month and month must be `*`. Catch-up takes only the latest
occurrence within a bounded window, preventing a storm after laptop sleep. Daily
market work requires an explicit calendar entry; unknown dates remain unscheduled
and are recorded in scheduler health. A non-trading day creates skipped stages.

Claims use a transaction lock plus row locks, with one job per module at a time.
Each attempt gets a new UUID lease and `RUN_ID` for every child logbook event.
Heartbeats occur every 20 seconds. A database outage stops the child process tree;
the scheduler recovers leases after 10 minutes. Retries start after 60 seconds,
then 120, up to the configured attempt limit. Terminal dependency failures cascade
to skipped dependents; `dependency_mode: finished` allows a digest after failure.
Extra job parameters never become shell commands. Output is bounded and sanitized.

Execution is **at least once**, not exactly once: a child can commit before a crash.
Modules must retain idempotent writes. Lease fencing protects job completion but
cannot retract work already committed by a child. On a sleeping machine, a process
can briefly resume before its runner detects a lost lease. Cross-machine orphan
termination is not supported; this deployment runs on one laptop.

Phase 5 rollout: schedules remain disabled until calendar, alerts, environments and
failure drills pass. The existing Phase 4 request worker must be replaced by queued
`requests` jobs before enabling scheduled agent work, since both share its local lock.
17:00 IST is provisional; record real source arrival times during the five-day test.

Validation: `python -m pytest scheduler/tests`; transactional database contract in
`db/tests/job_queue.sql` (rolls back). Live concurrency tests use isolated fixture jobs.
