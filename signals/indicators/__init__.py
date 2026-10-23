"""TA-Lib indicator adapters."""

from . import trend, momentum, volatility, volume


def compute(frame, config):
    values = {}
    for module in (trend, momentum, volatility, volume):
        values.update(module.compute(frame, config["indicators"]))
    return values
