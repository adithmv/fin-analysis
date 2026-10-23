"""Next-open event returns, non-overlapping evidence and matched baselines."""

from collections import defaultdict
import numpy as np
import pandas as pd
from .costs import net_return
from .splits import samples, exclusion_mask


def summarize(outcomes, baseline, n_events, minimum):
    values = np.asarray(outcomes, dtype=float)
    mean = float(values.mean()) if len(values) else None
    base = float(np.mean(baseline)) if len(baseline) else None
    return dict(
        n_events=n_events,
        n_independent=len(values),
        mean_return=mean,
        median_return=float(np.median(values)) if len(values) else None,
        win_rate=float((values > 0).mean()) if len(values) else None,
        baseline_mean=base,
        edge=mean - base if mean is not None and base is not None else None,
        sufficient_sample=len(values) >= minimum,
    )


def study_symbol(symbol, frame, signals, config, signal_key=None):
    positions = {ts: i for i, ts in enumerate(frame.ts)}
    groups = defaultdict(list)
    for row in signals:
        if row["signal_type"] not in ("pattern", "indicator") or row["direction"] not in (
            "bullish",
            "bearish",
        ):
            continue
        if signal_key and row["signal_key"] != signal_key:
            continue
        i = positions.get(pd.Timestamp(row["ts"]))
        if i is not None:
            groups[(row["signal_key"], row["direction"])].append(i)
    excluded, _ = exclusion_mask(frame, signals, config)
    rows = []
    for sample, (a, b) in samples(len(frame), config["sample_split"]["in_sample_fraction"]).items():
        for (key, direction), occurrences in sorted(groups.items()):
            for horizon in config["horizons_days"]:
                # h=1 enters next open and exits that same session's close.
                def eligible(i):
                    return a <= i and i + horizon < b and not excluded[i : i + horizon + 1].any()

                def outcome(i):
                    return net_return(
                        float(frame.iloc[i + 1].open), float(frame.iloc[i + horizon].close), config, direction
                    )

                valid = sorted(set(i for i in occurrences if eligible(i)))
                independent = []
                last = -(10**9)
                for i in valid:
                    if i - last > horizon:
                        independent.append(i)
                        last = i
                values = [outcome(i) for i in independent]
                baseline = [outcome(i) for i in range(a, b) if eligible(i)]
                rows.append(
                    dict(
                        signal_key=key,
                        direction=direction,
                        scope=symbol,
                        sample=sample,
                        horizon_days=horizon,
                        period_start=frame.iloc[a].ts.tz_convert("Asia/Kolkata").date().isoformat(),
                        period_end=frame.iloc[b - 1].ts.tz_convert("Asia/Kolkata").date().isoformat(),
                        **summarize(values, baseline, len(valid), config["min_independent_events"]),
                        _outcomes=values,
                        _baseline=baseline,
                    )
                )
    return rows


def pooled(rows, config):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["signal_key"], row["direction"], row["sample"], row["horizon_days"])].append(row)
    result = []
    for (key, direction, sample, horizon), items in sorted(groups.items()):
        outcomes = [v for r in items for v in r["_outcomes"]]
        # Weight each stock's baseline by its independent event count; this keeps
        # the baseline stock composition equal to the pooled event composition.
        base = [
            r["baseline_mean"]
            for r in items
            for _ in range(r["n_independent"])
            if r["baseline_mean"] is not None
        ]
        result.append(
            dict(
                signal_key=key,
                direction=direction,
                scope="POOLED",
                sample=sample,
                horizon_days=horizon,
                period_start=min(r["period_start"] for r in items),
                period_end=max(r["period_end"] for r in items),
                **summarize(
                    outcomes, base, sum(r["n_events"] for r in items), config["min_independent_events"]
                ),
            )
        )
    return result
