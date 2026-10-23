import talib


def compute(frame, config):
    close = frame.close.to_numpy(float)
    result = {f"rsi_{p}": talib.RSI(close, p) for p in config["rsi"]}
    s = config["stochastic"]
    k, d = talib.STOCH(
        frame.high.to_numpy(float),
        frame.low.to_numpy(float),
        close,
        fastk_period=s["k"],
        slowk_period=s["smooth"],
        slowd_period=s["d"],
    )
    suffix = f"{s['k']}_{s['smooth']}_{s['d']}"
    result[f"stoch_k_{suffix}"], result[f"stoch_d_{suffix}"] = k, d
    return result
