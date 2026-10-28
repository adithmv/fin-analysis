"""Compute deterministic daily research signals and atomically replace changed days."""

import argparse
from collections import defaultdict
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

import numpy as np
import pandas as pd
import yaml
from shared.db import get_client
from shared.logbook import log_event, sanitize

if __package__:
    from .indicators import compute as indicators
    from .patterns.candles import compute as patterns
    from .rules import crossovers, levels, trend_state
    from .quality import compute as quality
else:
    from indicators import compute as indicators
    from patterns.candles import compute as patterns
    from rules import crossovers, levels, trend_state
    from quality import compute as quality

ROOT = Path(__file__).resolve().parents[1]


def read_rows(client, table, symbol, columns="*"):
    rows = []
    for offset in range(0, 1000000, 500):
        query = (
            client.table(table)
            .select(columns)
            .eq("symbol", symbol)
            .eq("exchange", "NSE")
            .eq("timeframe", "1d")
            .order("ts")
        )
        if table == "indicator_values":
            query = query.order("series_key")
        elif table == "signals":
            query = query.order("signal_key")
        page = query.range(offset, offset + 499).execute().data
        rows.extend(page)
        if len(page) < 500:
            return rows
    raise RuntimeError("Unexpectedly large symbol history")


def prepare(rows):
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["ts"] = pd.to_datetime(frame.ts, utc=True)
    frame = frame.sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    for key in ("open", "high", "low", "close", "volume"):
        frame[key] = pd.to_numeric(frame[key], errors="coerce").astype(float)
    if not np.isfinite(frame[["open", "high", "low", "close"]]).all().all():
        raise ValueError("Invalid candle prices")
    return frame


def config_hash(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def compute(frame, config):
    values = indicators(frame, config)
    states, rows = trend_state.compute(frame, values, config)
    rows += patterns(frame, config["patterns"], states)
    rows += crossovers.compute(frame, values, config)
    rows += levels.compute(frame, config["levels"]["swing_window"])
    rows += quality(frame, config)
    digest = hashlib.sha256()
    signatures = []
    for candle in frame.itertuples():
        digest.update(
            json.dumps(
                [
                    candle.ts.isoformat(),
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    None if pd.isna(candle.volume) else candle.volume,
                ],
                allow_nan=False,
            ).encode()
        )
        signatures.append(digest.hexdigest())
    for row in rows:
        if row["signal_key"] == "trend_state":
            row["details"].update(config_hash=config_hash(config), input_hash=signatures[row["index"]],
                                  price_basis=config.get("price_basis", "raw"))
    return values, rows


def target_days(
    frame, values, rows, existing_indicators, existing_signals, config, recompute=False, since=None
):
    available = defaultdict(set)
    for row in existing_indicators:
        available[pd.Timestamp(row["ts"])].add(row["series_key"])
    markers = {pd.Timestamp(r["ts"]): r for r in existing_signals if r["signal_key"] == "trend_state"}
    fresh = {r["index"]: r for r in rows if r["signal_key"] == "trend_state"}
    expected = set(values)
    targets = []
    for i, ts in enumerate(frame.ts):
        marker = markers.get(ts)
        if (
            marker
            and marker["logic_version"] == config["logic_version"]
            and marker["details"].get("config_hash") != config_hash(config)
        ):
            raise ValueError("Signal configuration changed without a logic_version bump")
        stale = (
            not marker
            or marker["logic_version"] != config["logic_version"]
            or marker["details"].get("input_hash") != fresh[i]["details"]["input_hash"]
        )
        forced = recompute or (since is not None and ts.tz_convert("Asia/Kolkata").date() >= since)
        if forced or stale or available[ts] != expected:
            targets.append(i)
    return targets


def read_calendar(client):
    calendar = []
    for offset in range(0, 10000, 500):
        page = client.table("trading_calendar").select("day,is_trading_day").eq("exchange", "NSE").order("day").range(offset, offset+499).execute().data
        calendar.extend(page)
        if len(page) < 500:
            return {date.fromisoformat(r["day"]): r["is_trading_day"] for r in calendar}
    raise ValueError("Calendar range too large")


def run_symbol(client, symbol, config, run_id, recompute=False, since=None):
    def event(action, status, **fields):
        log_event(run_id, "signals", action, status, symbol=symbol, **fields)

    basis = config.get("price_basis", "raw")
    if basis not in ("raw", "adjusted"):
        raise ValueError("Invalid price_basis")
    frame = prepare(read_rows(client, "candles_adjusted" if basis == "adjusted" else "candles", symbol))
    if frame.empty:
        event("load_candles", "skipped", output_summary="No stored candles")
        return {"status": "skipped", "days": 0}
    event("load_candles", "success", output_summary=f"{len(frame)} candles loaded")
    if len(frame) < max(config["indicators"]["sma"]):
        event(
            "load_candles",
            "skipped",
            output_summary="Short history: long-period indicators remain null; short-history flags retained",
        )
    frame.attrs["calendar"] = read_calendar(client)
    values, rows = compute(frame, config)
    for action in ("compute_indicators", "compute_patterns", "compute_rules"):
        event(action, "success", output_summary=f"{len(values)} series; {len(rows)} dated signals")
    flags = sum(r["signal_type"] == "data_flag" for r in rows)
    event(
        "quality_check", "warning" if flags else "success", output_summary=f"{flags} historical quality flags"
    )
    existing_values = read_rows(client, "indicator_values", symbol, "ts,series_key")
    existing_signals = read_rows(client, "signals", symbol, "ts,signal_key,logic_version,details")
    targets = target_days(frame, values, rows, existing_values, existing_signals, config, recompute, since)
    if not targets:
        event("write_signals", "skipped", output_summary="All stored days are complete and current")
        return {"status": "skipped", "days": 0}
    now = datetime.now(timezone.utc).isoformat()
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["index"]].append(row)
    for start in range(0, len(targets), 40):
        batch = targets[start : start + 40]
        iv = []
        sr = []
        for i in batch:
            base = {
                "symbol": symbol,
                "exchange": "NSE",
                "timeframe": "1d",
                "ts": frame.iloc[i].ts.isoformat(),
                "computed_at": now,
            }
            iv.extend(
                {**base, "series_key": key, "value": float(v[i]) if np.isfinite(v[i]) else None}
                for key, v in values.items()
            )
            for row in grouped[i]:
                sr.append(
                    {
                        **base,
                        **{k: v for k, v in row.items() if k != "index"},
                        "logic_version": config["logic_version"],
                    }
                )
        client.rpc(
            "replace_signal_days",
            {
                "p_symbol": symbol,
                "p_dates": [frame.iloc[i].ts.isoformat() for i in batch],
                "p_indicators": iv,
                "p_signals": sr,
            },
        ).execute()
    event(
        "write_signals",
        "success",
        output_summary=f"{len(targets)} days replaced atomically in batches",
        meta={"days": len(targets), "logic_version": config["logic_version"]},
    )
    return {"status": "success", "days": len(targets)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compute daily indicators and research signals")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("--symbols")
    parser.add_argument("--recompute", action="store_true")
    parser.add_argument("--since", type=date.fromisoformat)
    parser.add_argument("--config", type=Path, default=ROOT / "config/signals.yaml")
    args = parser.parse_args(argv)
    run_id = str(uuid4())
    try:
        config = yaml.safe_load(args.config.read_text())
        client = get_client()
        active_symbols = {
            row["symbol"]
            for row in client.table("watchlist")
            .select("symbol")
            .eq("active", True)
            .eq("exchange", "NSE")
            .eq("kind", "equity")
            .execute()
            .data
        }
        symbols = (
            sorted(active_symbols)
            if args.all
            else list(dict.fromkeys(s.strip().upper() for s in args.symbols.split(",")))
        )
        if not symbols or any(symbol not in active_symbols for symbol in symbols):
            raise ValueError("Select active NSE equities from the watchlist")
        if config["timeframe"] != "1d":
            raise ValueError("Only daily signals supported")
        log_event(run_id, "signals", "run_start", "started", input_summary=f"{len(symbols)} symbols")
        totals = {"success": 0, "skipped": 0, "failed": 0, "days": 0}
        for symbol in symbols:
            try:
                result = run_symbol(client, symbol, config, run_id, args.recompute, args.since)
                totals[result["status"]] += 1
                totals["days"] += result["days"]
            except Exception as exc:
                totals["failed"] += 1
                log_event(run_id, "signals", "write_signals", "failed", symbol=symbol, error=str(exc))
                print(f"{symbol} failed: {sanitize(exc)}", file=sys.stderr)
        log_event(
            run_id,
            "signals",
            "run_end",
            "warning" if totals["failed"] else "success",
            output_summary=json.dumps(totals),
            meta=totals,
        )
        print(f"Run {run_id}: {totals}")
        return 1 if totals["failed"] else 0
    except Exception as exc:
        print(f"Signals failed: {sanitize(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
