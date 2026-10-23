import numpy as np
import pandas as pd
from .base import Strategy


class PatternTrend(Strategy):
    def decisions(self, frame, signals, parameters):
        entry = np.zeros(len(frame), dtype=bool)
        positions = {ts: i for i, ts in enumerate(frame.ts)}
        for row in signals:
            if (
                row["signal_key"] == parameters["pattern"]
                and row["direction"] == "bullish"
                and row["details"].get("trend_state") == parameters["trend"]
            ):
                i = positions.get(pd.Timestamp(row["ts"]))
                if i is not None:
                    entry[i] = True
        return entry, np.zeros(len(frame), dtype=bool), parameters["hold_days"]
