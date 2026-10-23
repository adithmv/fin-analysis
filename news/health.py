from datetime import datetime, timezone
from .storage import execute


def report(client):
    rows = execute(client.table("news_source_health").select("*").order("source_key"))
    now = datetime.now(timezone.utc)
    for row in rows:
        newest = row.get("newest_publication")
        stale = bool(newest and (now - datetime.fromisoformat(newest)).total_seconds() > 7 * 86400)
        quiet = not row["items_24h"] and now.weekday() < 5
        row["health"] = (
            "disabled"
            if not row["enabled"]
            else "failing"
            if row["consecutive_failures"]
            else "stale"
            if stale
            else "quiet"
            if quiet
            else "healthy"
        )
    return rows
