from copy import deepcopy
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import yaml
from signals.main import compute, target_days
from signals.rules.crossovers import crossed
from signals.rules.levels import compute as levels
from signals.patterns.candles import compute as patterns
from signals.quality import compute as quality

CONFIG = yaml.safe_load((Path(__file__).resolve().parents[2] / "config/signals.yaml").read_text())


def candles(n=430):
    close = 100 + np.arange(n) * 0.2 + np.sin(np.arange(n) / 3)
    return pd.DataFrame(
        {
            "ts": pd.date_range("2023-01-02", periods=n, freq="B", tz="Asia/Kolkata").tz_convert("UTC"),
            "open": close - 0.2,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": np.full(n, 100.0),
        }
    )


def test_indicators_match_independent_calculations():
    f = candles()
    values, _ = compute(f, CONFIG)
    np.testing.assert_allclose(values["sma_50"][49:], f.close.rolling(50).mean()[49:], rtol=1e-10)
    np.testing.assert_allclose(
        values["bb_upper_20_2"][19:],
        (f.close.rolling(20).mean() + 2 * f.close.rolling(20).std(ddof=0))[19:],
        rtol=1e-9,
    )
    assert np.isnan(values["sma_200"][:199]).all()
    # Wilder RSI with an explicit simple seed, then recursive smoothing.
    changes = f.close.diff().to_numpy()
    gain = np.maximum(changes, 0)
    loss = np.maximum(-changes, 0)
    g, l = np.mean(gain[1:15]), np.mean(loss[1:15])
    expected = [100 - 100 / (1 + g / l)]
    for i in range(15, len(f)):
        g = (g * 13 + gain[i]) / 14
        l = (l * 13 + loss[i]) / 14
        expected.append(100 - 100 / (1 + g / l))
    np.testing.assert_allclose(values["rsi_14"][14:], expected, rtol=1e-10)
    ema = np.empty(len(f))
    ema[:] = np.nan
    ema[11] = f.close[:12].mean()
    for i in range(12, len(f)):
        ema[i] = ema[i - 1] + 2 / 13 * (f.close[i] - ema[i - 1])
    np.testing.assert_allclose(values["ema_12"][11:], ema[11:], rtol=1e-10)


def test_crossings_are_one_day_events():
    assert list(crossed([1, 2, 4, 5, 6], [3] * 5)) == [False, False, True, False, False]


def test_levels_only_confirm_after_future_window():
    f = candles(9)
    f["high"] = [1, 2, 3, 4, 10, 4, 3, 2, 1]
    rows = levels(f, 2)
    high = [r for r in rows if r["signal_key"] == "swing_high"]
    assert high[0]["index"] == 6 and high[0]["details"]["swing_ts"] == f.ts[4].isoformat()
    assert not [r for r in levels(f.iloc[:6], 2) if r["signal_key"] == "swing_high"]


def test_pattern_raw_sign_and_doji():
    f = candles(30)
    f.loc[29, ["open", "close"]] = [105, 105]
    rows = patterns(f, ["CDLDOJI"], ["sideways"] * 30)
    assert any(r["index"] == 29 and r["raw_value"] > 0 for r in rows)
    f.loc[28, ["open", "close", "high", "low"]] = [110, 108, 111, 107]
    f.loc[29, ["open", "close", "high", "low"]] = [107, 112, 113, 106]
    assert any(
        r["index"] == 29 and r["direction"] == "bullish"
        for r in patterns(f, ["CDLENGULFING"], ["downtrend"] * 30)
    )
    f.loc[29, ["open", "close", "high", "low"]] = [108.5, 109, 110, 108]
    assert not any(r["index"] == 29 for r in patterns(f, ["CDLENGULFING"], ["downtrend"] * 30))


def test_quality_flags_and_clean_control():
    clean = candles()
    assert not [r for r in quality(clean, CONFIG) if r["signal_key"] != "short_history"]
    f = clean.copy()
    f.loc[210, "close"] *= 0.5
    f.loc[220:224, "volume"] = 0
    f.loc[300:, "ts"] += pd.Timedelta(days=15)
    keys = {r["signal_key"] for r in quality(f, CONFIG)}
    assert keys == {"short_history", "possible_split_or_bonus", "zero_volume_streak", "gap_in_data"}


def test_incremental_matches_full_and_repairs_deleted_day():
    f = candles()
    v, r = compute(f, CONFIG)
    existing = [{"ts": ts, "series_key": key} for ts in f.ts for key in v]
    markers = [
        {**row, "ts": f.ts[row["index"]], "logic_version": CONFIG["logic_version"]}
        for row in r
        if row["signal_key"] == "trend_state"
    ]
    assert target_days(f, v, r, existing, markers, CONFIG) == []
    assert target_days(f, v, r, existing, markers[:-1], CONFIG) == [len(f) - 1]
    f2 = candles(431)
    v2, r2 = compute(f2, CONFIG)
    assert target_days(f2, v2, r2, existing, markers, CONFIG) == [430]
    assert np.allclose(v["obv"], v2["obv"][:-1], equal_nan=True)
    changed = deepcopy(CONFIG)
    changed["rules"]["rsi_oversold"] = 25
    with pytest.raises(ValueError, match="logic_version"):
        target_days(f, v, r, existing, markers, changed)


def test_future_candles_do_not_change_past_signals():
    f = candles()
    v, r = compute(f, CONFIG)
    short_v, short_r = compute(f.iloc[:300].copy(), CONFIG)
    for key in v:
        np.testing.assert_allclose(v[key][:300], short_v[key], equal_nan=True)
    assert [x for x in r if x["index"] < 300] == short_r
