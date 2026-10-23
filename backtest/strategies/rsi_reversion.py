import talib
from .base import Strategy


class RSIReversion(Strategy):
    def decisions(self, frame, signals, parameters):
        rsi = talib.RSI(frame.close.to_numpy(float), parameters.get("period", 14))
        return rsi < parameters["entry_below"], rsi > parameters["exit_above"], parameters["max_hold_days"]
