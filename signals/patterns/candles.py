import talib


def compute(frame, names, states):
    result = []
    allowed = set(talib.get_function_groups()["Pattern Recognition"])
    for name in names:
        if name not in allowed:
            raise ValueError(f"Unsupported pattern function: {name}")
        values = getattr(talib, name)(*[frame[c].to_numpy(float) for c in ("open", "high", "low", "close")])
        for i, raw in enumerate(values):
            if raw:
                direction = "bullish" if raw > 0 else "bearish"
                result.append(
                    dict(
                        index=i,
                        signal_key="cdl_" + name[3:].lower(),
                        signal_type="pattern",
                        direction=direction,
                        raw_value=int(raw),
                        description=f"{direction.title()} {name[3:].lower()} (raw value {raw:+d})",
                        details={"trend_state": states[i]},
                    )
                )
    return result
