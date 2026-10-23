"""Run reproducible research against stored candles and signals only."""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import numpy as np
import pandas as pd
import yaml
import httpx
from shared.db import get_client, bulk_upsert
from shared.logbook import log_event, sanitize

ROOT = Path(__file__).resolve().parents[1]
if not __package__:
    sys.path.insert(0, str(ROOT))
from backtest.engine import simulate  # noqa: E402
from backtest.event_study import study_symbol, pooled  # noqa: E402
from backtest.splits import samples, exclusion_mask  # noqa: E402
from backtest.strategies import STRATEGIES  # noqa: E402
from backtest.costs import rates  # noqa: E402


def read_query(query):
    """Retry only idempotent reads after a transient connection failure."""
    for attempt in range(3):
        try:
            return query.execute().data
        except httpx.TransportError:
            if attempt == 2:
                raise
            time.sleep(0.5 * 2**attempt)


def read_rows(client, table, symbol):
    rows = []
    for offset in range(0, 1000000, 500):
        query = (
            client.table(table)
            .select("*")
            .eq("symbol", symbol)
            .eq("exchange", "NSE")
            .eq("timeframe", "1d")
            .order("ts")
        )
        if table == "signals":
            query = query.order("signal_key")
        page = read_query(query.range(offset, offset + 499))
        rows.extend(page)
        if len(page) < 500:
            return rows
    raise ValueError("History exceeds supported size")


def load_symbol(client, symbol):
    frame = pd.DataFrame(read_rows(client, "candles", symbol))
    if len(frame) < 2:
        raise ValueError(f"{symbol}: need at least two candles")
    frame["ts"] = pd.to_datetime(frame.ts, utc=True)
    frame = frame.sort_values("ts").reset_index(drop=True)
    for key in ("open", "high", "low", "close", "volume"):
        frame[key] = pd.to_numeric(frame[key], errors="coerce").astype(float)
    if (
        frame.ts.duplicated().any()
        or not np.isfinite(frame[["open", "high", "low", "close"]]).all().all()
        or (frame[["open", "high", "low", "close"]] <= 0).any().any()
    ):
        raise ValueError(f"{symbol}: invalid prices or duplicate dates")
    signals = read_rows(client, "signals", symbol)
    markers = {pd.Timestamp(r["ts"]): r for r in signals if r["signal_key"] == "trend_state"}
    digest = hashlib.sha256()
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
        marker = markers.get(candle.ts)
        if marker is None or marker["details"].get("input_hash") != digest.hexdigest():
            raise ValueError(f"{symbol}: missing or stale signals; run signals first")
    versions = sorted({r["logic_version"] for r in signals})
    if len(versions) != 1:
        raise ValueError(f"{symbol}: mixed signal versions; recompute signals")
    stable = [{k: v for k, v in r.items() if k not in ("id", "computed_at")} for r in signals]
    digest.update(json.dumps(stable, sort_keys=True, allow_nan=False).encode())
    return frame, signals, digest.hexdigest(), versions[0]


def provenance(config, data):
    metadata = dict(config)
    sources = hashlib.sha256()
    for path in sorted((ROOT / "backtest").rglob("*.py")):
        if ".venv" not in path.parts and "tests" not in path.parts:
            sources.update(path.relative_to(ROOT).as_posix().encode())
            sources.update(path.read_bytes())
    metadata.update(
        source_hash=sources.hexdigest(),
        working_tree_dirty=subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", "backtest", "config/backtest.yaml"], cwd=ROOT
        ).returncode
        != 0,
        code_version=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        input_hashes={s: item[2] for s, item in data.items()},
        signal_versions={s: item[3] for s, item in data.items()},
        packages={p: importlib.metadata.version(p) for p in ("vectorbt", "numpy", "pandas", "TA-Lib")},
        combinations_tested=1,
        horizon_definition="Signal at close i; entry open i+1; exit close i+h; h=1 is one session",
        exclusion_policy="Retrospective data filter; identical strategy and benchmark windows; not a tradable forecast",
        splits={
            s: {
                name: [f.iloc[a].ts.date().isoformat(), f.iloc[b - 1].ts.date().isoformat()]
                for name, (a, b) in samples(len(f), config["sample_split"]["in_sample_fraction"]).items()
            }
            for s, (f, *_rest) in data.items()
        },
    )
    return metadata


def execute(args):
    config = yaml.safe_load(args.config.read_text())
    rates(config)
    if config["timing"] != {"entry": "next_open", "exit_for_events": "horizon_close"}:
        raise ValueError("Only next-open entries and horizon-close event exits are supported")
    if (
        any(not isinstance(h, int) or h < 1 for h in config["horizons_days"])
        or config["initial_capital"] <= 0
    ):
        raise ValueError("Invalid horizons or starting capital")
    client = get_client()
    run_id = str(uuid4())
    log_event(run_id, "backtest", "run_start", "started", input_summary=args.mode)
    try:
        symbols = (
            sorted(set(s.strip().upper() for s in args.symbols.split(",") if s.strip()))
            if args.symbols
            else sorted(
                r["symbol"]
                for r in read_query(
                    client.table("watchlist").select("symbol").eq("active", True).eq("exchange", "NSE")
                )
            )
        )
        if not symbols:
            raise ValueError("No symbols selected")
        data = {}
        for symbol in symbols:
            data[symbol] = load_symbol(client, symbol)
            frame, signals, *_ = data[symbol]
            log_event(
                run_id,
                "backtest",
                "load_data",
                "success",
                symbol=symbol,
                output_summary=f"{len(frame)} candles; {len(signals)} signals",
            )
            mask, windows = exclusion_mask(frame, signals, config)
            if mask.any():
                log_event(
                    run_id,
                    "backtest",
                    "apply_exclusions",
                    "warning",
                    symbol=symbol,
                    output_summary=f"{int(mask.sum())} bars excluded; {len(windows)} split/gap windows",
                    meta={"windows": windows},
                )
        metadata = provenance(config, data)
        if args.mode == "events":
            rows = []
            for symbol, (frame, signals, *_rest) in data.items():
                result = study_symbol(symbol, frame, signals, config, args.signal)
                rows.extend(result)
                log_event(
                    run_id,
                    "backtest",
                    "event_study",
                    "success",
                    symbol=symbol,
                    output_summary=f"{len(result)} signal/sample/horizon results",
                )
            rows += pooled(rows, config)
            for row in rows:
                row.pop("_outcomes", None)
                row.pop("_baseline", None)
                row.update(
                    stats_run_id=run_id,
                    config=metadata,
                    logic_version=";".join(sorted(set(item[3] for item in data.values()))),
                )
            bulk_upsert(
                client,
                "signal_stats",
                rows,
                "stats_run_id,signal_key,direction,scope,sample,horizon_days,abnormal",
                batch_size=100,
            )
            count = len(rows)
        else:
            results, trades = [], []
            parameters = config["strategies"].get(args.strategy, {})
            metadata["parameters"] = parameters
            for symbol, (frame, signals, *_rest) in data.items():
                for sample, bounds in samples(
                    len(frame), config["sample_split"]["in_sample_fraction"]
                ).items():
                    metrics, curve, transactions, _ = simulate(
                        frame, signals, config, args.strategy, parameters, bounds
                    )
                    benchmark, bench_curve, _, _ = simulate(
                        frame, signals, config, "buy_and_hold", {}, bounds
                    )
                    results.append(
                        dict(
                            run_id=run_id,
                            symbol=symbol,
                            sample=sample,
                            metrics=metrics,
                            benchmark_metrics=benchmark,
                            equity_curve=curve,
                            benchmark_equity_curve=bench_curve,
                        )
                    )
                    trades.extend(
                        dict(run_id=run_id, symbol=symbol, sample=sample, **t) for t in transactions
                    )
                log_event(
                    run_id,
                    "backtest",
                    "run_strategy",
                    "success",
                    symbol=symbol,
                    output_summary="Computed all, in-sample and out-of-sample with matched benchmark",
                )
            client.table("backtest_runs").insert(
                dict(
                    id=run_id,
                    name=args.strategy.replace("_", " "),
                    strategy_key=args.strategy,
                    config=metadata,
                    symbols=symbols,
                    period_start=min(f.iloc[0].ts.date().isoformat() for f, *_ in data.values()),
                    period_end=max(f.iloc[-1].ts.date().isoformat() for f, *_ in data.values()),
                    fees_pct=config["costs"]["fees_pct_per_side"],
                    slippage_pct=config["costs"]["slippage_pct_per_side"],
                    code_version=metadata["code_version"],
                )
            ).execute()
            try:
                bulk_upsert(client, "backtest_results", results, "run_id,symbol,sample")
                bulk_upsert(client, "backtest_trades", trades, "run_id,symbol,sample,entry_ts,exit_ts")
            except Exception:
                client.table("backtest_runs").delete().eq("id", run_id).execute()
                raise
            count = len(results)
        log_event(run_id, "backtest", "write_results", "success", output_summary=f"Saved {count} results")
        log_event(
            run_id,
            "backtest",
            "run_end",
            "success",
            output_summary=f"{count} results; 1 parameter combination",
            meta={"combinations_tested": 1},
        )
        print(f"Run {run_id}: {count} results")
        return run_id
    except Exception as exc:
        if args.mode == "events":
            client.table("signal_stats").delete().eq("stats_run_id", run_id).execute()
        log_event(run_id, "backtest", "run_end", "failed", error=str(exc))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    for mode in ("events", "strategy"):
        sub = commands.add_parser(mode)
        if mode == "strategy":
            sub.add_argument("strategy", choices=STRATEGIES)
        else:
            sub.add_argument("--signal")
        group = sub.add_mutually_exclusive_group()
        group.add_argument("--all", action="store_true")
        group.add_argument("--symbols")
        sub.add_argument("--config", type=Path, default=ROOT / "config/backtest.yaml")
    try:
        execute(parser.parse_args(argv))
        return 0
    except Exception as exc:
        print(f"Backtest failed: {sanitize(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
