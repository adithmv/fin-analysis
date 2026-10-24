"""Immutable report outcomes using matching stock/index sessions and next-open entry."""

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from uuid import uuid4
import math

from shared.db import get_client
from shared.logbook import log_event

IST = ZoneInfo("Asia/Kolkata")


def timestamp(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def session(row):
    return timestamp(row["ts"]).astimezone(IST).date()


def grade(report, thread, stock, benchmark, horizon, blocked_dates=(), now=None):
    if horizon not in (1, 3, 5, 10, 20):
        raise ValueError("Unsupported research horizon")
    now = now or datetime.now(timezone.utc)
    cutoff = timestamp(thread["data_cutoff_ts"])
    if not thread.get("config", {}).get("replay"):
        cutoff = max(cutoff, timestamp(report["created_at"]))
    prices = sorted(stock, key=session)
    if len({session(r) for r in prices}) != len(prices):
        raise ValueError("Duplicate stock sessions")
    indexes = {session(r): r for r in benchmark}
    if len(indexes) != len(benchmark):
        raise ValueError("Duplicate benchmark sessions")
    first = next(
        (i for i, r in enumerate(prices) if datetime.combine(session(r), time(9, 15), IST) > cutoff), None
    )
    if first is None or first + horizon > len(prices):
        return None
    window = prices[first : first + horizon]
    start, end = session(window[0]), session(window[-1])
    benchmark_start = min(
        (d for d in indexes if datetime.combine(d, time(9, 15), IST) > cutoff), default=None
    )
    if benchmark_start != start:
        return None
    if datetime.combine(end, time(15, 30), IST) > now:
        return None
    # A missing stock/index session must not silently shift the horizon.
    if {session(r) for r in window} != {d for d in indexes if start <= d <= end}:
        return None
    if any(start <= d <= end for d in blocked_dates):
        return None
    values = [window[0]["open"], window[-1]["close"], indexes[start]["open"], indexes[end]["close"]]
    if any(not math.isfinite(float(v)) or float(v) <= 0 for v in values):
        return None
    entry, exit_price, index_entry, index_exit = map(float, values)
    realized, baseline = exit_price / entry - 1, index_exit / index_entry - 1
    excess = realized - baseline
    stance = report["stance"]
    return dict(
        report_id=report["id"],
        horizon_days=horizon,
        entry_date=start.isoformat(),
        exit_date=end.isoformat(),
        realized_return=realized,
        benchmark_return=baseline,
        excess_return=excess,
        directional_hit=excess > 0 if stance == "bullish" else excess < 0 if stance == "bearish" else None,
    )


def rows(client, table, order="id"):
    result = []
    for offset in range(0, 1000000, 500):
        page = client.table(table).select("*").order(order).range(offset, offset + 499).execute().data
        result.extend(page)
        if len(page) < 500:
            return result
    raise ValueError("Row limit reached")


def execute():
    from backtest.main import read_rows
    from datetime import timedelta
    import yaml
    from pathlib import Path

    client, run_id = get_client(), str(uuid4())
    log_event(run_id, "backtest", "grade_reports", "started")
    try:
        reports = rows(client, "analysis_reports")
        threads = {r["id"]: r for r in rows(client, "threads")}
        existing = {(r["report_id"], r["horizon_days"]) for r in rows(client, "report_outcomes", "report_id")}
        benchmark = read_rows(client, "candles", "NIFTY50")
        config = yaml.safe_load((Path(__file__).resolve().parents[1] / "config/backtest.yaml").read_text())
        cache, count = {}, 0
        for report in reports:
            symbol = report["symbol"]
            if symbol not in cache:
                candles = read_rows(client, "candles", symbol)
                signals = read_rows(client, "signals", symbol)
                blocked = set()
                for signal in signals:
                    day = session(signal)
                    if signal["signal_key"] in ("gap_in_data", "short_history"):
                        blocked.update((day, day - timedelta(days=1)))
                    if signal["signal_key"] == "possible_split_or_bonus":
                        ordered = sorted(session(r) for r in candles)
                        if day in ordered:
                            i = ordered.index(day)
                            width = config["exclusions"]["around_split_flag_days"]
                            blocked.update(ordered[max(0, i - width) : i + width + 1])
                cache[symbol] = candles, blocked
            candles, blocked = cache[symbol]
            for horizon in config["horizons_days"]:
                if (report["id"], horizon) in existing:
                    continue
                result = grade(report, threads[report["thread_id"]], candles, benchmark, horizon, blocked)
                if result:
                    # Ignore concurrent duplicate inserts; never revise a previous outcome.
                    client.table("report_outcomes").upsert(
                        result, on_conflict="report_id,horizon_days", ignore_duplicates=True
                    ).execute()
                    count += 1
        log_event(
            run_id, "backtest", "grade_reports", "success", output_summary=f"Saved {count} mature outcomes"
        )
        print(f"Saved {count} mature outcomes; immature or unmatched sessions remain pending")
    except Exception as exc:
        log_event(run_id, "backtest", "grade_reports", "failed", error=str(exc))
        raise
