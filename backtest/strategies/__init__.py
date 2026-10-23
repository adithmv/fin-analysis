from .sma_cross import SMACross
from .rsi_reversion import RSIReversion
from .pattern_trend import PatternTrend
from .buy_and_hold import BuyAndHold

STRATEGIES = {
    "sma_cross": SMACross,
    "rsi_reversion": RSIReversion,
    "pattern_trend": PatternTrend,
    "buy_and_hold": BuyAndHold,
}
