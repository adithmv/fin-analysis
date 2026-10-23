import numpy as np
import talib


def compute(frame, config):
    volume = frame.volume.to_numpy(dtype=float)
    result = {f"volume_avg_{p}": frame.volume.rolling(p).mean().to_numpy(float) for p in config["volume_avg"]}
    if config["obv"]:
        # Missing volume has no defensible contribution; do not fabricate zeros.
        result["obv"] = (
            talib.OBV(frame.close.to_numpy(float), volume)
            if np.isfinite(volume).all()
            else np.full(len(frame), np.nan)
        )
    return result
