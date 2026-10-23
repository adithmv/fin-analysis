from copy import deepcopy
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import yaml
from backtest.costs import net_return
from backtest.engine import simulate
from backtest.event_study import study_symbol, pooled
from backtest.splits import samples, exclusion_mask
from backtest.strategies.base import Strategy
from backtest.strategies import STRATEGIES

CONFIG = yaml.safe_load((Path(__file__).resolve().parents[2] / "config/backtest.yaml").read_text())


def test_transient_reads_retry_but_do_not_hide_persistent_failure(monkeypatch):
    import httpx
    from types import SimpleNamespace
    from backtest.main import read_query

    monkeypatch.setattr("backtest.main.time.sleep", lambda _: None)

    class Query:
        calls = 0

        def execute(self):
            self.calls += 1
            if self.calls < 3:
                raise httpx.ConnectError("temporary connection reset")
            return SimpleNamespace(data=[{"symbol": "TCS"}])

    query = Query()
    assert read_query(query) == [{"symbol": "TCS"}]
    assert query.calls == 3

    class Broken:
        def execute(self):
            raise httpx.ConnectError("persistent failure")

    with pytest.raises(httpx.ConnectError):
        read_query(Broken())


def frame(n=12):
    return pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=n, freq="B", tz="Asia/Kolkata").tz_convert("UTC"),
            "open": np.arange(n) * 10.0 + 100,
            "close": np.arange(n) * 10.0 + 105,
            "high": np.arange(n) * 10.0 + 108,
            "low": np.arange(n) * 10.0 + 98,
            "volume": 100.0,
        }
    )


def event(f, i, key="test", direction="bullish", kind="indicator"):
    return {
        "ts": f.ts[i].isoformat(),
        "signal_key": key,
        "direction": direction,
        "signal_type": kind,
        "details": {},
    }


def test_event_timing_costs_independence_baseline_and_split():
    f = frame()
    c = deepcopy(CONFIG)
    c["horizons_days"] = [1, 3]
    c["sample_split"]["in_sample_fraction"] = 0.5
    rows = study_symbol("TCS", f, [event(f, i) for i in (0, 1, 2, 4, 5, 8)], c)
    one = next(r for r in rows if r["sample"] == "all" and r["horizon_days"] == 1)
    independent = [0, 2, 4, 8]
    manual = [net_return(f.open[i + 1], f.close[i + 1], c) for i in independent]
    assert one["n_events"] == 6 and one["n_independent"] == 4
    assert one["mean_return"] == pytest.approx(np.mean(manual))
    assert one["baseline_mean"] == pytest.approx(
        np.mean([net_return(f.open[i + 1], f.close[i + 1], c) for i in range(11)])
    )
    assert one["edge"] == pytest.approx(one["mean_return"] - one["baseline_mean"])
    inside = next(r for r in rows if r["sample"] == "in_sample" and r["horizon_days"] == 3)
    assert inside["n_events"] == 3  # only signals 0,1,2 have outcomes wholly inside first six bars
    assert not inside["sufficient_sample"]


def test_bearish_costs_never_improve_returns():
    c = deepcopy(CONFIG)
    free = deepcopy(c)
    free["costs"]["fees_pct_per_side"] = 0
    free["costs"]["slippage_pct_per_side"] = 0
    assert net_return(100, 90, c, "bearish") < net_return(100, 90, free, "bearish")
    assert net_return(100, 100, c, "bearish") < 0


def test_next_open_and_manual_benchmark():
    class Known(Strategy):
        def decisions(self, f, s, p):
            return np.array([True, False, False, False]), np.array([False, False, True, False]), None

    STRATEGIES["test_known"] = Known
    f = frame(4)
    c = deepcopy(CONFIG)
    metrics, curve, trades, _ = simulate(f, [], c, "test_known", {}, (0, 4))
    assert trades[0]["entry_ts"] == f.ts[1].isoformat()
    assert trades[0]["exit_ts"] == f.ts[3].isoformat()
    expected = net_return(110, 130, c)
    assert metrics["total_return"] == pytest.approx(expected)
    benchmark, _, bt, _ = simulate(f, [], c, "buy_and_hold", {}, (0, 4))
    assert benchmark["total_return"] == pytest.approx(net_return(100, 135, c))
    assert bt[-1]["exit_reason"] == "end_of_data"
    del STRATEGIES["test_known"]


def test_exclusions_remove_entire_outcome_window():
    f = frame(40)
    c = deepcopy(CONFIG)
    c["exclusions"]["around_split_flag_days"] = 2
    c["horizons_days"] = [3]
    signals = [event(f, 20, "possible_split_or_bonus", "neutral", "data_flag"), event(f, 16), event(f, 24)]
    mask, _ = exclusion_mask(f, signals, c)
    assert mask[18:23].all() and not mask[17]
    all_row = next(r for r in study_symbol("X", f, signals, c) if r["sample"] == "all")
    assert all_row["n_events"] == 1


def test_splits_and_repeatability():
    assert samples(10, 0.7) == {"all": (0, 10), "in_sample": (0, 7), "out_of_sample": (7, 10)}
    f = frame(30)
    first = simulate(f, [], CONFIG, "buy_and_hold", {}, (0, 30))
    assert first == simulate(f, [], CONFIG, "buy_and_hold", {}, (0, 30))


def test_pool_weights_baseline_to_event_composition():
    rows = [
        dict(
            signal_key="x",
            direction="bullish",
            sample="all",
            horizon_days=1,
            scope="A",
            period_start="2026-01-01",
            period_end="2026-02-01",
            n_events=2,
            n_independent=2,
            _outcomes=[0.1, 0.2],
            baseline_mean=0.05,
        ),
        dict(
            signal_key="x",
            direction="bullish",
            sample="all",
            horizon_days=1,
            scope="B",
            period_start="2026-01-01",
            period_end="2026-02-01",
            n_events=1,
            n_independent=1,
            _outcomes=[0.3],
            baseline_mean=0.02,
        ),
    ]
    result = pooled(rows, CONFIG)[0]
    assert result["baseline_mean"] == pytest.approx(0.04)
    assert result["mean_return"] == pytest.approx(0.2)
