from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import time
import feedparser
import requests
from ..normalize import article


def due(source, now=None):
    now = now or datetime.now(timezone.utc)
    last = source.get("last_fetched_at")
    return source["enabled"] and (
        not last
        or (now - datetime.fromisoformat(last)).total_seconds() >= source["poll_interval_minutes"] * 60
    )


def fetch(source, config, request=requests.get, sleep=time.sleep, on_retry=None):
    headers = {"User-Agent": config["user_agent"]}
    if source.get("etag"):
        headers["If-None-Match"] = source["etag"]
    if source.get("last_modified"):
        headers["If-Modified-Since"] = source["last_modified"]
    response = None
    for attempt in range(3):
        try:
            response = request(source["url"], headers=headers, timeout=config["timeout_seconds"])
            if response.status_code == 304:
                return [], {}, True
            response.raise_for_status()
            break
        except requests.RequestException:
            status = getattr(response, "status_code", None)
            if attempt == 2 or (status is not None and status not in (403, 429, 500, 502, 503, 504)):
                raise
            wait = 2**attempt
            retry = response.headers.get("Retry-After") if response is not None else None
            if retry:
                try:
                    wait = max(wait, float(retry))
                except ValueError:
                    wait = max(
                        wait, (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
                    )
            if wait > 30:
                # Preserve politeness without blocking a run for minutes; next poll waits its interval.
                raise RuntimeError(f"Source requested Retry-After {wait:.0f}s; defer until next poll")
            if on_retry:
                on_retry(attempt + 1, wait)
            sleep(wait)
    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise ValueError("Feed is invalid XML or has no recognizable entries")
    if not parsed.version:
        raise ValueError("Response is not a recognized RSS/Atom feed")
    rows = []
    errors = []
    for item in parsed.entries:
        try:
            rows.append(
                article(
                    source["source_key"],
                    item.get("link", ""),
                    item.get("title", ""),
                    item.get("summary", ""),
                    item.get("published") or item.get("updated"),
                    raw={
                        "feed_id": item.get("id"),
                        "original_date": item.get("published") or item.get("updated"),
                    },
                    language=parsed.feed.get("language", "en").split("-")[0].lower(),
                )
            )
        except (ValueError, TypeError) as exc:
            errors.append(str(exc))
    return (
        rows,
        {
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "notes": f"{len(errors)} invalid items skipped" if errors else None,
        },
        False,
    )
