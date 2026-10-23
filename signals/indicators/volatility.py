import talib


def compute(frame, config):
    close = frame.close.to_numpy(float)
    b = config["bollinger"]
    bands = talib.BBANDS(
        close, timeperiod=b["period"], nbdevup=float(b["stddev"]), nbdevdn=float(b["stddev"])
    )
    result = {
        f"bb_{key}_{b['period']}_{b['stddev']:g}": value
        for key, value in zip(("upper", "middle", "lower"), bands)
    }
    for p in config["atr"]:
        result[f"atr_{p}"] = talib.ATR(frame.high.to_numpy(float), frame.low.to_numpy(float), close, p)
    return result
