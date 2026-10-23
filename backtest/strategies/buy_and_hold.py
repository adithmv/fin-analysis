import numpy as np
from .base import Strategy


class BuyAndHold(Strategy):
    def decisions(self, frame, signals, parameters):
        # Benchmark is a predeclared allocation, entered at the first eligible open.
        return np.ones(len(frame), dtype=bool), np.zeros(len(frame), dtype=bool), None
