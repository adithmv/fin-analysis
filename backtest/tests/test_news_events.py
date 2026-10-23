from copy import deepcopy
import numpy as np
import pandas as pd
import pytest
from backtest.tests.test_backtest import frame, CONFIG, event
from backtest.news_events import study, occurrences, bucket, pool


def test_known_next_open_abnormal_absolute_and_missing_benchmark():
    f = frame(12)
    b = frame(12)
    b["open"] = 100.0
    b["close"] = 102.0
    c = deepcopy(CONFIG)
    c["horizons_days"] = [1, 3]
    events = [
        dict(
            key="news:earnings_result",
            direction="neutral",
            date=f.ts[i].tz_convert("Asia/Kolkata").date().isoformat(),
            published_at=(f.ts[i] + pd.Timedelta(hours=8)).isoformat(),
        )
        for i in (0, 1, 2, 5, 8)
    ]
    rows = study("TCS", f, [], events, b, c)
    r = next(r for r in rows if r["sample"] == "all" and r["horizon_days"] == 1 and r["abnormal"])
    assert r["n_events"] == 5 and r["n_independent"] == 4
    from backtest.costs import net_return

    assert r["mean_return"] == pytest.approx(
        np.mean([net_return(f.open[i], f.close[i], c) - 0.02 for i in (0, 2, 5, 8)])
    )
    assert r["mean_abs_return"] == pytest.approx(
        np.mean([abs(f.close[i] / f.open[i] - 1 - 0.02) for i in (0, 2, 5, 8)])
    )
    assert r["edge"] == pytest.approx(r["mean_return"] - r["baseline_mean"])
    missing = study("TCS", f, [], events, b.drop(index=2), c)
    assert (
        next(r for r in missing if r["sample"] == "all" and r["horizon_days"] == 1 and r["abnormal"])[
            "n_events"
        ]
        == 4
    )
    excluded = study("TCS", f, [event(f, 0, key="possible_split_or_bonus", kind="data_flag")], events, b, c)
    assert all(r["n_events"] == 0 for r in excluded)
    assert len(pool(rows, c)) == len(rows)
    late = [{**events[0], "published_at": (f.ts[0] + pd.Timedelta(hours=10)).isoformat()}]
    assert study("TCS", f, [], late, b, c) == []


def test_adapter_deduplicates_groups_and_rejects_assumed_or_weak_links():
    cfg = {
        "linking": {"min_confidence_for_events": 0.7},
        "processing": {"linker_version": "1", "events_logic_version": "1"},
        "benchmark": "NIFTY50",
        "sentiment": {
            "model": "m",
            "revision": "r",
            "scope": "title_summary",
            "buckets": {"very_negative": -0.6, "negative": -0.2, "positive": 0.2, "very_positive": 0.6},
        },
    }
    articles = [
        dict(
            id=str(i),
            is_duplicate=False,
            published_at_assumed=i == 2,
            dedupe_group_id="group",
            published_at="2026-01-01T01:00:00Z",
            processing={"classify": {"version": "1"}},
        )
        for i in range(4)
    ]
    links = [
        dict(article_id=str(i), symbol="TCS", confidence=0.3 if i == 3 else 1, linker_version="1")
        for i in range(4)
    ]
    events = [
        dict(
            article_id=str(i),
            symbol="TCS",
            published_at="2026-01-01T01:00:00Z",
            logic_version="1",
            event_type="earnings_result",
            effective_trading_date="2026-01-01",
        )
        for i in range(4)
    ]
    assert len(occurrences(articles, links, events, [], cfg, "news")["TCS"]) == 1
    assert bucket(-0.9, cfg["sentiment"]["buckets"]) == ("very_negative", "bearish")
    assert bucket(0, cfg["sentiment"]["buckets"]) == ("neutral", "neutral")
