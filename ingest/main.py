"""Manual daily ingestion. Each symbol fails independently."""

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd
import yaml
from shared.db import bulk_upsert, get_client
from shared.logbook import log_event, sanitize

if __package__:
    from .sources.base import SourceError
    from .sources.runner import create_source, fetch_bounded
    from .validate import validate
    from .hardening import read_calendar
else:
    from sources.base import SourceError
    from sources.runner import create_source, fetch_bounded
    from validate import validate
    from hardening import read_calendar

ROOT = Path(__file__).resolve().parents[1]
IST = ZoneInfo("Asia/Kolkata")


def completed_date(now=None, calendar=None):
    # Conservative: today's candle is only eligible after 18:00 IST.
    now = now or datetime.now(IST)
    now = now.astimezone(IST)
    day = now.date() if now.hour >= 18 else now.date() - timedelta(days=1)
    if calendar is not None:
        for _ in range(15):
            if day not in calendar:
                raise ValueError("Exchange calendar missing; refresh before ingestion")
            if calendar[day]["is_trading_day"]:
                return day
            day -= timedelta(days=1)
        raise ValueError("No recent exchange session in calendar")
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


class Pipeline:
    def __init__(self, client, config, *, fetcher=fetch_bounded, logger=log_event, sleep=time.sleep, calendar=None):
        self.client, self.config = client, config
        self.fetcher, self.logger, self.sleep = fetcher, logger, sleep
        self.run_id = str(uuid4())
        self.blocked = set()
        self.warnings = 0
        self.calendar = calendar

    def event(self, action, status, **fields):
        if status == "warning":
            self.warnings += 1
        self.logger(self.run_id, "ingest", action, status, **fields)

    def fetch(self, name, symbol, start, end):
        if name in self.config.get("disabled_sources", []):
            raise SourceError("Source disabled by terms review; see docs/SOURCES_TERMS.md", blocked=True)
        if name in self.blocked:
            self.event(
                "fetch_candles",
                "skipped",
                tool=name,
                symbol=symbol,
                output_summary="Source blocked earlier in this run",
            )
            raise SourceError("Source disabled for this run", blocked=True)
        source = create_source(name)
        for attempt in range(1, self.config["retries"] + 1):
            began = time.monotonic()
            self.event(
                "fetch_candles",
                "started",
                tool=name,
                symbol=symbol,
                input_summary=f"{start} through {end}; attempt {attempt}",
                source_urls=[source.url],
            )
            try:
                raw = self.fetcher(name, symbol, start, end, self.config["source_timeout_seconds"])
                result = validate(raw, start, end, self.calendar)
                self.event(
                    "fetch_candles",
                    "success",
                    tool=name,
                    symbol=symbol,
                    output_summary=f"{len(raw)} rows fetched",
                    api_calls=1,
                    duration_ms=int((time.monotonic() - began) * 1000),
                    source_urls=[source.url],
                )
                self.event(
                    "validate_candles",
                    "warning" if result.warnings else "success",
                    tool=name,
                    symbol=symbol,
                    output_summary=f"{len(result.frame)} valid rows",
                    meta={"warnings": result.warnings},
                )
                return result.frame
            except SourceError as exc:
                self.event(
                    "fetch_candles",
                    "failed",
                    tool=name,
                    symbol=symbol,
                    error=str(exc),
                    api_calls=1,
                    duration_ms=int((time.monotonic() - began) * 1000),
                    source_urls=[source.url],
                )
                if exc.blocked:
                    self.blocked.add(name)
                    self.event(
                        "source_disabled",
                        "warning",
                        tool=name,
                        symbol=symbol,
                        output_summary="Blocking response; no more requests to this source this run",
                    )
                if exc.blocked or not exc.transient or attempt == self.config["retries"]:
                    raise
                delay = self.config["retry_backoff_seconds"] * 2 ** (attempt - 1)
                self.event(
                    "fetch_candles",
                    "retried",
                    tool=name,
                    symbol=symbol,
                    output_summary=f"Retrying in {delay}s",
                )
                self.sleep(delay)

    def sync_watchlist(self, watchlist):
        indices = set(watchlist.get("indices", []))
        symbols = list(dict.fromkeys(s.upper().strip() for s in watchlist["symbols"] + list(indices)))
        if watchlist["exchange"] != "NSE" or any(not re.fullmatch(r"[A-Z0-9&._-]{1,40}", s) for s in symbols):
            raise ValueError("Phase 1 supports valid NSE symbols only")
        existing = self.client.table("watchlist").select("symbol").eq("exchange", "NSE").execute().data
        rows = [{"symbol": s, "exchange": "NSE", "active": True, "kind": "index" if s in indices else "equity"} for s in symbols]
        rows += [
            {"symbol": r["symbol"], "exchange": "NSE", "active": False}
            for r in existing
            if r["symbol"] not in symbols
        ]
        bulk_upsert(self.client, "watchlist", rows, "symbol,exchange")
        self.event("sync_watchlist", "success", output_summary=f"{len(symbols)} active NSE symbols")

    def process(self, symbol, end, *, since=None, days=None, sources=None):
        latest = (
            self.client.table("candles")
            .select("ts,source,adjusted")
            .eq("symbol", symbol)
            .eq("exchange", "NSE")
            .eq("timeframe", "1d")
            .order("ts", desc=True)
            .limit(1)
            .execute()
            .data
        )
        start = since or (end - timedelta(days=days - 1) if days else None)
        if start is None:
            start = (
                pd.Timestamp(latest[0]["ts"]).tz_convert("Asia/Kolkata").date() + timedelta(days=1)
                if latest
                else end - timedelta(days=self.config["default_lookback_days"] - 1)
            )
        if start > end or not len(pd.bdate_range(start, end)):
            self.event(
                "fetch_candles",
                "skipped",
                symbol=symbol,
                output_summary="Stored candles are current through the last eligible session",
            )
            return "skipped", 0
        priorities = sources or (self.config.get("index_source_priority", ["yfinance"]) if symbol == "NIFTY50" else self.config["source_priority"])
        frame = None
        chosen = None
        for name in priorities:
            try:
                candidate = self.fetch(name, symbol, start, end)
                source = create_source(name)
                # Do not silently append a differently adjusted series.
                if latest and bool(latest[0]["adjusted"]) != source.adjusted:
                    self.event(
                        "adjustment_mismatch",
                        "warning",
                        tool=name,
                        symbol=symbol,
                        output_summary="Rejected source: adjustment basis differs from stored candles",
                    )
                    continue
                frame, chosen = candidate, source
                break
            except SourceError:
                continue
        if frame is None:
            self.event(
                "symbol_end",
                "failed",
                symbol=symbol,
                output_summary="No source supplied compatible valid candles",
            )
            return "failed", 0
        fetched_at = datetime.now(timezone.utc).isoformat()
        rows = []
        for candle in frame.itertuples(index=False):
            rows.append(
                dict(
                    symbol=symbol,
                    exchange="NSE",
                    timeframe="1d",
                    ts=candle.ts.isoformat(),
                    open=str(candle.open),
                    high=str(candle.high),
                    low=str(candle.low),
                    close=str(candle.close),
                    volume=None if pd.isna(candle.volume) else int(candle.volume),
                    source=chosen.name,
                    adjusted=chosen.adjusted,
                    fetched_at=fetched_at,
                )
            )
        try:
            count = bulk_upsert(self.client, "candles", rows, "symbol,exchange,timeframe,ts")
        except Exception as exc:
            self.event(
                "write_candles",
                "failed",
                symbol=symbol,
                error=str(exc),
                output_summary="Write failed; earlier successful batches remain valid and can be retried",
            )
            raise
        self.event(
            "write_candles",
            "success",
            symbol=symbol,
            tool=chosen.name,
            output_summary=f"{count} candles stored",
        )
        if self.config["crosscheck"]["enabled"]:
            self.crosscheck(symbol, frame, chosen, priorities)
        return "success", count

    def crosscheck(self, symbol, frame, chosen, priorities):
        candidates = [n for n in priorities if n != chosen.name and n not in self.blocked]
        if not candidates:
            self.event("crosscheck", "skipped", symbol=symbol, output_summary="No second source available")
            return
        for name in candidates:
            tail = frame.tail(5)
            start = tail.iloc[0].ts.tz_convert("Asia/Kolkata").date()
            end = tail.iloc[-1].ts.tz_convert("Asia/Kolkata").date()
            try:
                other = self.fetch(name, symbol, start, end)
                joined = tail[["ts", "close"]].merge(
                    other[["ts", "close"]], on="ts", suffixes=("_primary", "_other")
                )
                if joined.empty:
                    raise SourceError("No overlapping dates for comparison")
                joined["difference_percent"] = (
                    (joined.close_primary - joined.close_other).abs() / joined.close_primary
                ) * 100
                bad = joined[joined.difference_percent > self.config["crosscheck"]["tolerance_percent"]]
                details = [
                    {
                        "ts": r.ts.isoformat(),
                        "primary": float(r.close_primary),
                        "secondary": float(r.close_other),
                        "difference_percent": float(r.difference_percent),
                    }
                    for r in bad.itertuples()
                ]
                self.event(
                    "crosscheck",
                    "warning" if len(bad) else "success",
                    symbol=symbol,
                    tool=name,
                    output_summary=f"{len(joined)} overlapping sessions; {len(bad)} differences above tolerance",
                    meta={
                        "primary_source": chosen.name,
                        "secondary_source": name,
                        "differences": details,
                        "different_adjustment_basis": chosen.adjusted != create_source(name).adjusted,
                    },
                )
                return
            except SourceError as exc:
                self.event(
                    "crosscheck",
                    "warning",
                    symbol=symbol,
                    tool=name,
                    error=str(exc),
                    output_summary="Cross-check unavailable; kept primary candles",
                )

    def run(self, symbols, end, **kwargs):
        totals = {"success": 0, "failed": 0, "skipped": 0, "candles": 0}
        self.event("run_start", "started", input_summary=f"{len(symbols)} symbols through {end}")
        for index, symbol in enumerate(symbols):
            if index:
                self.sleep(self.config["delay_between_symbols_seconds"])
            try:
                status, count = self.process(symbol, end, **kwargs)
                totals[status] += 1
                totals["candles"] += count
            except Exception as exc:
                totals["failed"] += 1
                self.event("symbol_end", "failed", symbol=symbol, error=str(exc))
        status = (
            "failed"
            if totals["failed"] == len(symbols) and symbols
            else "warning"
            if totals["failed"] or self.warnings
            else "success"
        )
        self.event("run_end", status, output_summary=json.dumps(totals), meta=totals)
        return totals


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch and validate completed daily NSE candles")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--symbols")
    dates = parser.add_mutually_exclusive_group()
    dates.add_argument("--days", type=int)
    dates.add_argument("--since", type=date.fromisoformat)
    parser.add_argument("--source", choices=["jugaad", "openchart", "yfinance"])
    parser.add_argument("--config", type=Path, default=ROOT / "config/ingest.yaml")
    args = parser.parse_args(argv)
    if args.days is not None and args.days < 1:
        parser.error("--days must be positive")
    if args.since and args.since > completed_date():
        parser.error("--since is after the last completed session")
    try:
        config = yaml.safe_load(args.config.read_text())
        if config["retries"] < 1 or config["source_timeout_seconds"] <= 0:
            raise ValueError("Invalid retry or timeout configuration")
        for source in config["source_priority"]:
            create_source(source)
        client = get_client()
        # Fail clearly before source requests if the DB credentials are invalid.
        client.table("watchlist").select("symbol").limit(1).execute()
        calendar = read_calendar(client, args.since or date.today()-timedelta(days=1500), date.today())
        end = completed_date(calendar=calendar)
        pipeline = Pipeline(client, config, calendar=calendar)
        pipeline.sync_watchlist(yaml.safe_load((ROOT / "config/watchlist.yaml").read_text()))
        symbols = (
            [
                r["symbol"]
                for r in client.table("watchlist")
                .select("symbol")
                .eq("exchange", "NSE")
                .eq("active", True)
                .execute()
                .data
            ]
            if args.all
            else list(dict.fromkeys(s.strip().upper() for s in args.symbols.split(",")))
        )
        if not symbols or any(not re.fullmatch(r"[A-Z0-9&._-]{1,40}", s) for s in symbols):
            raise ValueError("Provide valid NSE symbols")
        totals = pipeline.run(
            symbols,
            end,
            since=args.since,
            days=args.days,
            sources=[args.source] if args.source else None,
        )
        print(f"Run {pipeline.run_id}: {json.dumps(totals)}")
        return 1 if totals["failed"] else 0
    except Exception as exc:
        print(f"Ingestion failed: {sanitize(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
