import pandas as pd
import talib
from .base import Strategy


class SMACross(Strategy):
    def decisions(self, frame, signals, parameters):
        close = frame.close.to_numpy(float)
        fast = pd.Series(talib.SMA(close, parameters["fast"]))
        slow = pd.Series(talib.SMA(close, parameters["slow"]))
        entry = (fast > slow) & (fast.shift() <= slow.shift())
        exit = (fast < slow) & (fast.shift() >= slow.shift())
        return entry.to_numpy(bool), exit.to_numpy(bool), None
