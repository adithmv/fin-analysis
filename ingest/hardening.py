"""Exchange calendar refresh and proposed (never automatic) price adjustments."""

import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo
import yaml
from shared.db import get_client, bulk_upsert
from shared.logbook import log_event

ROOT = Path(__file__).resolve().parents[1]


def read_calendar(client, start, end):
    rows = []
    for offset in range(0, 10000, 500):
        page = client.table("trading_calendar").select("day,is_trading_day,note,source").eq("exchange", "NSE").gte("day", str(start)).lte("day", str(end)).order("day").range(offset, offset+499).execute().data
        rows.extend(page)
        if len(page) < 500:
            return {date.fromisoformat(r["day"]): r for r in rows}
    raise ValueError("Calendar range too large")


def year_rows(year, holidays, overrides):
    holidays = set(holidays)
    if len(holidays) < 5 or any(d.year != year for d in holidays):
        raise ValueError(f"Holiday library has no complete calendar for {year}; update and review the source")
    day, end, rows = date(year, 1, 1), date(year + 1, 1, 1), []
    while day < end:
        override = overrides.get(day.isoformat())
        trading = day.weekday() < 5 and day not in holidays
        row = {"exchange": "NSE", "day": str(day), "is_trading_day": trading,
            "note": "Regular session" if trading else "Exchange holiday" if day in holidays else "Weekend",
            "source": "jugaad-data:holidays:0.37.0"}
        if override:
            if not override.get("source", "").startswith("https://"):
                raise ValueError("Calendar override requires an official source")
            row.update(override)
        rows.append(row)
        day += timedelta(days=1)
    return rows


def propose_factor(action):
    parsed = action.get("parsed") or {}
    try:
        if action["action_type"] == "bonus":
            new, existing = Decimal(str(parsed["new_shares"])), Decimal(str(parsed["existing_shares"]))
            if new <= 0 or existing <= 0:
                return None
            factor = existing / (existing + new)
        elif action["action_type"] == "split":
            old, new = Decimal(str(parsed["old_face_value"])), Decimal(str(parsed["new_face_value"]))
            if old <= 0 or new <= 0:
                return None
            factor = new / old
        else:
            return None
        if not factor.is_finite() or not 0 < factor <= 1000 or not action.get("ex_date"):
            return None
        return {"symbol": action["symbol"], "exchange": action["exchange"], "ex_date": action["ex_date"],
            "factor": str(factor), "corporate_action_id": action["id"], "status": "proposed",
            "note": "Unreviewed parsed ratio; compare raw chart and independent adjusted prices before approval"}
    except (KeyError, InvalidOperation, ZeroDivisionError):
        return None


def propose(client):
    actions = []
    for offset in range(0, 100000, 500):
        page = client.table("corporate_actions").select("*").in_("action_type", ["split", "bonus"]).order("id").range(offset, offset+499).execute().data
        actions.extend(page)
        if len(page) < 500:
            break
    groups = defaultdict(list)
    for action in actions:
        groups[(action["symbol"], action["exchange"], action.get("ex_date"))].append(action)
    rows, ambiguous = [], []
    for key, group in groups.items():
        candidates = [propose_factor(a) for a in group]
        if any(r is None for r in candidates) or len({r["factor"] for r in candidates if r}) != 1:
            ambiguous.append(key)
        else:
            rows.append(candidates[0])
    if rows:
        # A refresh can never overwrite a human decision, or silently alter a proposal.
        client.table("adjustment_factors").upsert(rows, on_conflict="symbol,exchange,ex_date", ignore_duplicates=True).execute()
    return {"proposals_found": len(rows), "ambiguous_groups": ambiguous}


def refresh(client, years):
    from jugaad_data.holidays import holidays

    overrides = yaml.safe_load((ROOT / "config/calendar.yaml").read_text())["overrides"]
    rows = [row for year in years for row in year_rows(year, holidays(year=year), overrides)]
    bulk_upsert(client, "trading_calendar", rows, "exchange,day")
    # Cross-check all stored sessions; missing candles are not silently called holidays.
    observed = defaultdict(set)
    for offset in range(0, 100000, 500):
        page = client.table("candles").select("symbol,ts").eq("exchange", "NSE").eq("timeframe", "1d").order("ts").order("symbol").range(offset, offset+499).execute().data
        for row in page:
            session = datetime.fromisoformat(row["ts"]).astimezone(ZoneInfo("Asia/Kolkata")).date()
            observed[session.isoformat()].add(row["symbol"])
        if len(page) < 500:
            break
    conflicts = [r["day"] for r in rows if not r["is_trading_day"] and observed.get(r["day"])]
    client.table("health_checks").insert({"check_key": "calendar_conflict", "subject": "NSE",
        "status": "warn" if conflicts else "ok", "value": len(conflicts), "detail": {"dates": conflicts}}).execute()
    return {"days": len(rows), "conflicting_observed_sessions": conflicts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["calendar", "propose"])
    parser.add_argument("--years", default=str(date.today().year))
    args = parser.parse_args(argv)
    client, run_id = get_client(), str(uuid4())
    try:
        result = refresh(client, [int(y) for y in args.years.split(",")]) if args.command == "calendar" else propose(client)
        print(json.dumps(result))
        log_event(run_id, "ingest", args.command, "success", meta=result)
        return 0
    except Exception as exc:
        log_event(run_id, "ingest", args.command, "failed", error=type(exc).__name__)
        print(f"Hardening failed: {type(exc).__name__}; inspect source coverage and database connectivity")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
