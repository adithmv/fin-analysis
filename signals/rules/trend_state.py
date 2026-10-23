import numpy as np


def compute(frame, values, config):
    fast, slow = values["sma_50"], values["sma_200"]
    adx = values["adx_14"]
    states, rows = [], []
    for i, close in enumerate(frame.close):
        ready = all(np.isfinite(x) for x in (fast[i], slow[i], adx[i]))
        state = "unknown" if not ready else "sideways"
        if ready and adx[i] > config["trend_state"]["adx_threshold"]:
            if close > fast[i] > slow[i]:
                state = "uptrend"
            elif close < fast[i] < slow[i]:
                state = "downtrend"
        states.append(state)
        rows.append(
            dict(
                index=i,
                signal_key="trend_state",
                signal_type="trend",
                direction="neutral",
                raw_value=None,
                description=f"Trend state: {state}",
                details={
                    "state": state,
                    "close": float(close),
                    "sma_50": float(fast[i]) if np.isfinite(fast[i]) else None,
                    "sma_200": float(slow[i]) if np.isfinite(slow[i]) else None,
                    "adx_14": float(adx[i]) if np.isfinite(adx[i]) else None,
                    "adx_threshold": config["trend_state"]["adx_threshold"],
                },
            )
        )
    return states, rows
