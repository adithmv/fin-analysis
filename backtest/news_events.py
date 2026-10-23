"""Stored-table adapters. No dependency on the news application or its models."""

from collections import defaultdict
import hashlib
import json
import numpy as np
import pandas as pd
from .costs import net_return
from .splits import samples, exclusion_mask
from .event_study import summarize


def read_archive(client, table, keys):
    from .main import read_query

    rows = []
    for offset in range(0, 1000000, 500):
        query = client.table(table).select("*")
        for key in keys:
            query = query.order(key)
        page = read_query(query.range(offset, offset + 499))
        rows.extend(page)
        if len(page) < 500:
            return rows
    raise ValueError("Archive exceeds supported batch size")


def bucket(score, thresholds):
    if score <= thresholds["very_negative"]:
        return "very_negative", "bearish"
    if score < thresholds["negative"]:
        return "negative", "bearish"
    if score >= thresholds["very_positive"]:
        return "very_positive", "bullish"
    if score > thresholds["positive"]:
        return "positive", "bullish"
    return "neutral", "neutral"


def occurrences(articles, links, events, scores, config, source, event_type=None):
    """Canonical groups, current classifier/link versions, known publication times only."""
    valid = {
        r["id"]: r
        for r in articles
        if not r["is_duplicate"] and not r["published_at_assumed"] and r.get("processing", {}).get("classify")
    }
    linked = {
        (r["article_id"], r["symbol"]): r
        for r in links
        if float(r["confidence"]) >= config["linking"]["min_confidence_for_events"]
        and r["linker_version"] == config["processing"]["linker_version"]
    }
    cfg = config["sentiment"]
    scored = {
        r["article_id"]: r
        for r in scores
        if r["model_key"] == cfg["model"]
        and r["model_revision"] == cfg["revision"]
        and r["scope"] == cfg["scope"]
    }
    result = defaultdict(list)
    seen = set()
    for event in sorted(events, key=lambda r: r["published_at"]):
        a = valid.get(event["article_id"])
        if not a or not event["effective_trading_date"] or (a["id"], event["symbol"]) not in linked:
            continue
        if event["logic_version"] != config["processing"]["events_logic_version"]:
            continue
        if source == "news":
            if event_type and event["event_type"] != event_type:
                continue
            key, direction = "news:" + event["event_type"], "neutral"
        else:
            if a["id"] not in scored:
                continue
            label, direction = bucket(float(scored[a["id"]]["score"]), cfg["buckets"])
            key = "sentiment:" + label
        symbol = config["benchmark"] if event["symbol"] == "MARKET" else event["symbol"]
        identity = (a["dedupe_group_id"] or a["id"], symbol, key)
        if identity in seen:
            continue
        seen.add(identity)
        result[symbol].append(
            dict(
                key=key,
                direction=direction,
                date=event["effective_trading_date"],
                published_at=a["published_at"],
                group=identity[0],
            )
        )
    return dict(result)


def load(client, config, source, event_type=None):
    tables = [
        read_archive(client, t, k)
        for t, k in (
            ("articles", ["id"]),
            ("article_symbols", ["article_id", "symbol", "exchange"]),
            ("news_events", ["id"]),
            ("article_sentiment", ["article_id", "scope", "model_key", "model_revision"]),
        )
    ]
    # Include the entire persisted input and current configuration in reproducibility metadata.
    digest = hashlib.sha256(json.dumps(tables, sort_keys=True, default=str).encode()).hexdigest()
    return occurrences(*tables, config, source, event_type), digest


def study(symbol, frame, signals, events, benchmark, config):
    dates = [ts.tz_convert("Asia/Kolkata").date().isoformat() for ts in frame.ts]
    indexes = {day: i for i, day in enumerate(dates)}
    groups = defaultdict(list)
    for e in events:
        i = indexes.get(e["date"])
        # Defensively verify publication precedes the actual entry open.
        if i is not None and pd.Timestamp(e["published_at"]) < pd.Timestamp(
            e["date"] + " 09:15", tz="Asia/Kolkata"
        ):
            groups[(e["key"], e["direction"])].append(i)
    excluded, _ = exclusion_mask(frame, signals, config)
    bench = (
        {}
        if benchmark is None
        else {
            ts.tz_convert("Asia/Kolkata").date().isoformat(): (float(o), float(c))
            for ts, o, c in zip(benchmark.ts, benchmark.open, benchmark.close)
        }
    )
    rows = []
    for sample, (a, b) in samples(len(frame), config["sample_split"]["in_sample_fraction"]).items():
        for (key, direction), positions in sorted(groups.items()):
            for h in config["horizons_days"]:
                for abnormal in [False, True] if bench else [False]:

                    def eligible(i):
                        if not a <= i or i + h > b or excluded[i : i + h].any():
                            return False
                        # Every stock session must exist in the index; never shift a missing date.
                        return not abnormal or all(day in bench for day in dates[i : i + h])

                    def outcome(i):
                        gross = float(frame.close.iloc[i + h - 1] / frame.open.iloc[i] - 1)
                        market = bench[dates[i + h - 1]][1] / bench[dates[i]][0] - 1 if abnormal else 0
                        sign = -1 if direction == "bearish" else 1
                        net = (
                            float(
                                net_return(
                                    frame.open.iloc[i],
                                    frame.close.iloc[i + h - 1],
                                    config,
                                    "bearish" if sign < 0 else "bullish",
                                )
                            )
                            - sign * market
                        )
                        return net, abs(gross - market)

                    valid = sorted(set(i for i in positions if eligible(i)))
                    independent = []
                    last = -(10**9)
                    for i in valid:
                        if i - last > h:
                            independent.append(i)
                            last = i
                    values = [outcome(i) for i in independent]
                    baseline = [outcome(i) for i in range(a, b) if eligible(i)]
                    net = [v[0] for v in values]
                    base = [v[0] for v in baseline]
                    absolute = [v[1] for v in values]
                    base_abs = [v[1] for v in baseline]
                    rows.append(
                        dict(
                            signal_key=key,
                            direction=direction,
                            scope=symbol,
                            sample=sample,
                            horizon_days=h,
                            abnormal=abnormal,
                            period_start=dates[a],
                            period_end=dates[b - 1],
                            **summarize(net, base, len(valid), config["min_independent_events"]),
                            mean_abs_return=float(np.mean(absolute)) if absolute else None,
                            baseline_mean_abs=float(np.mean(base_abs)) if base_abs else None,
                            _outcomes=net,
                            _absolute=absolute,
                        )
                    )
    return rows


def pool(rows, config):
    groups = defaultdict(list)
    for row in rows:
        groups[
            (row["signal_key"], row["direction"], row["sample"], row["horizon_days"], row["abnormal"])
        ].append(row)
    result = []
    for (key, direction, sample, horizon, abnormal), items in sorted(groups.items()):
        values = [v for r in items for v in r["_outcomes"]]
        base = [
            r["baseline_mean"]
            for r in items
            for _ in range(r["n_independent"])
            if r["baseline_mean"] is not None
        ]
        absolute = [v for r in items for v in r["_absolute"]]
        base_abs = [
            r["baseline_mean_abs"]
            for r in items
            for _ in range(r["n_independent"])
            if r["baseline_mean_abs"] is not None
        ]
        result.append(
            dict(
                signal_key=key,
                direction=direction,
                scope="POOLED",
                sample=sample,
                horizon_days=horizon,
                abnormal=abnormal,
                period_start=min(r["period_start"] for r in items),
                period_end=max(r["period_end"] for r in items),
                **summarize(
                    values, base, sum(r["n_events"] for r in items), config["min_independent_events"]
                ),
                mean_abs_return=float(np.mean(absolute)) if absolute else None,
                baseline_mean_abs=float(np.mean(base_abs)) if base_abs else None,
            )
        )
    return result
