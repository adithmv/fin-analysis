import talib


def compute(frame, config):
    close = frame.close.to_numpy(dtype=float)
    result = {f"sma_{p}": talib.SMA(close, p) for p in config["sma"]}
    result.update({f"ema_{p}": talib.EMA(close, p) for p in config["ema"]})
    m = config["macd"]
    macd = talib.MACD(close, fastperiod=m["fast"], slowperiod=m["slow"], signalperiod=m["signal"])
    for key, values in zip(("line", "signal", "hist"), macd):
        result[f"macd_{key}_{m['fast']}_{m['slow']}_{m['signal']}"] = values
    for p in config["adx"]:
        result[f"adx_{p}"] = talib.ADX(frame.high.to_numpy(float), frame.low.to_numpy(float), close, p)
    return result
