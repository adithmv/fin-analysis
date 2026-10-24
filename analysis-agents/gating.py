from datetime import timedelta
from zoneinfo import ZoneInfo
from data.asof_db import instant


def decide(pack, config, force=False):
    cfg = config["gating"]
    cutoff = instant(pack["cutoff"])
    latest = instant(pack["latest_session"])
    weekdays = 0
    day = latest.astimezone(ZoneInfo("Asia/Kolkata")).date()
    while day < cutoff.astimezone(ZoneInfo("Asia/Kolkata")).date():
        day += timedelta(days=1)
        weekdays += day.weekday() < 5
    if weekdays > cfg["stale_data_max_trading_days"]:
        return False, ["Latest stored session is stale; analysis skipped"]
    if force:
        return True, ["Explicit on-demand analysis"]
    previous = [i["row"] for i in pack["items"] if i["section"] == "previous_report"]
    if not previous:
        return True, ["No previous report"]
    prior = instant(previous[0]["created_at"])
    reasons = []
    if (cutoff - prior).days >= cfg["days_since_last_report"]:
        reasons.append("Scheduled review interval elapsed")
    for item in pack["items"]:
        r = item["row"]
        if (
            item["section"] == "signals"
            and r["signal_type"] in cfg["new_signal_types"]
            and instant(r["ts"]) > prior
        ):
            reasons.append("New technical signal")
        if (
            item["section"] == "events"
            and r["importance"] >= cfg["new_news_event_min_importance"]
            and instant(r["published_at"]) > prior
        ):
            reasons.append("Material company event")
        if (
            item["section"] == "actions"
            and r.get("ex_date")
            and 0
            <= (instant(r["ex_date"]).date() - cutoff.date()).days
            <= cfg["upcoming_corporate_action_days"]
        ):
            reasons.append("Upcoming corporate action")
    prices = [i["row"] for i in pack["items"] if i["section"] == "prices"]
    atr = next(
        (
            i["row"]["value"]
            for i in pack["items"]
            if i["section"] == "indicators" and i["row"]["series_key"] == "atr_14"
        ),
        None,
    )
    if (
        len(prices) >= 2
        and atr
        and abs(float(prices[-1]["close"]) - float(prices[-2]["close"]))
        >= float(atr) * cfg["price_move_atr_multiple"]
    ):
        reasons.append("Large move relative to ATR")
    return bool(reasons), sorted(set(reasons)) or [
        "No material change since previous report; previous view stands"
    ]
