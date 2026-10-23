import numpy as np
import pandas as pd


def crossed(left, right, above=True):
    a, b = pd.Series(left), pd.Series(right, index=range(len(left)))
    valid = a.notna() & b.notna() & a.shift().notna() & b.shift().notna()
    return valid & ((a > b) & (a.shift() <= b.shift()) if above else (a < b) & (a.shift() >= b.shift()))


def became(condition, ready):
    condition = pd.Series(condition).fillna(False)
    return condition & ~condition.shift(fill_value=False) & pd.Series(ready).shift(fill_value=False)


def compute(frame, values, config):
    rules = config["rules"]
    n = len(frame)
    tests = []

    def add(key, mask, direction, description):
        tests.append((key, mask, direction, description))

    add(
        "sma_50_200_golden_cross",
        crossed(values["sma_50"], values["sma_200"]),
        "bullish",
        "SMA 50 crossed above SMA 200",
    )
    add(
        "sma_50_200_death_cross",
        crossed(values["sma_50"], values["sma_200"], False),
        "bearish",
        "SMA 50 crossed below SMA 200",
    )
    m = config["indicators"]["macd"]
    suffix = f"{m['fast']}_{m['slow']}_{m['signal']}"
    for above, direction in ((True, "bullish"), (False, "bearish")):
        add(
            "macd_bull_cross" if above else "macd_bear_cross",
            crossed(values[f"macd_line_{suffix}"], values[f"macd_signal_{suffix}"], above),
            direction,
            "MACD crossed its signal line",
        )
    for key, threshold, above, direction in [
        ("rsi_14_oversold", rules["rsi_oversold"], False, "bullish"),
        ("rsi_14_overbought", rules["rsi_overbought"], True, "bearish"),
    ]:
        add(
            key,
            crossed(values["rsi_14"], np.full(n, threshold), above),
            direction,
            f"RSI 14 crossed {threshold}",
        )
    b = config["indicators"]["bollinger"]
    suffix = f"{b['period']}_{b['stddev']:g}"
    for bound, above, direction in [("lower", False, "bullish"), ("upper", True, "bearish")]:
        add(
            f"bb_{bound}_touch",
            crossed(frame.close, values[f"bb_{bound}_{suffix}"], above),
            direction,
            f"Close crossed the {bound} Bollinger band",
        )
    w = rules["breakout_window_days"]
    high = frame.close.rolling(w).max()
    low = frame.close.rolling(w).min()
    for side, extreme, direction in [("high", high, "bullish"), ("low", low, "bearish")]:
        add(
            f"new_{w}d_{side}",
            became(frame.close == extreme, extreme.notna()),
            direction,
            f"Close reached its {w}-session {side}",
        )
    avg = pd.Series(values["volume_avg_20"])
    condition = frame.volume > avg * rules["volume_spike_multiple"]
    add(
        "volume_spike",
        became(condition, avg.notna()),
        "neutral",
        "Volume exceeded configured multiple of its 20-session average",
    )
    return [
        dict(
            index=int(i),
            signal_key=key,
            signal_type="indicator",
            direction=direction,
            raw_value=1,
            description=description,
            details={},
        )
        for key, mask, direction, description in tests
        for i in np.flatnonzero(mask)
    ]
