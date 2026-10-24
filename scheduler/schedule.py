"""Bounded IST catch-up: latest due occurrence only, with durable idempotency."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from uuid import uuid4
from shared.logbook import log_event


def field_values(field, low, high):
    values = set()
    for part in field.split(","):
        base, *steps = part.split("/")
        if len(steps) > 1:
            raise ValueError("Invalid cron step")
        step = int(steps[0]) if steps else 1
        if step < 1:
            raise ValueError("Invalid cron step")
        if base == "*":
            start, end = low, high
        elif "-" in base:
            start, end = map(int, base.split("-"))
        else:
            start = end = int(base)
        if not low <= start <= end <= high:
            raise ValueError("Cron field outside range")
        values.update(range(start, end + 1, step))
    return values


def latest_due(cron, now, catchup_minutes):
    minute, hour, day, month, weekday = cron.split()
    if day != "*" or month != "*":
        raise ValueError("Only daily/weekly schedules supported; day and month must be *")
    minutes, hours, weekdays = field_values(minute, 0, 59), field_values(hour, 0, 23), field_values(weekday, 0, 6)
    if not 1 <= catchup_minutes <= 10080:
        raise ValueError("Catch-up must be between 1 minute and 7 days")
    current = now.replace(second=0, microsecond=0)
    for offset in range(catchup_minutes):
        candidate = current - timedelta(minutes=offset)
        if candidate.minute in minutes and candidate.hour in hours and (candidate.weekday() + 1) % 7 in weekdays:
            return candidate
    return None


def tick(client, queue, config, now=None):
    now = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(config["timezone"]))
    run_id = str(uuid4())
    result = {"evaluated": 0, "calendar_unknown": 0}
    for name, pipeline in config["pipelines"].items():
        if not pipeline.get("enabled", True):
            continue
        due = latest_due(pipeline["cron"], now, pipeline.get("catchup_minutes", 60))
        if due is None:
            continue
        stages = [dict(stage) for stage in pipeline["stages"]]
        if pipeline.get("trading_days_only", False):
            rows = client.table("trading_calendar").select("is_trading_day").eq("exchange", "NSE").eq("day", str(due.date())).execute().data
            if not rows:
                result["calendar_unknown"] += 1
                continue  # Unknown is not a holiday. Health checks report this.
            if not rows[0]["is_trading_day"]:
                for stage in stages:
                    stage.update(status="skipped", result_summary="Exchange calendar: non-trading day")
        key = f"{name}:{due.isoformat()}"
        queue.enqueue(key, due, stages)
        result["evaluated"] += 1
    recovered = queue.recover()
    for job in recovered:
        log_event(run_id, "scheduler", "recover_job", "warning", output_summary=f"Job {job['id']}: {job['status']}")
    client.table("health_checks").insert({"check_key": "scheduler_heartbeat", "subject": "local",
        "status": "warn" if result["calendar_unknown"] else "ok", "detail": result}).execute()
    return result
