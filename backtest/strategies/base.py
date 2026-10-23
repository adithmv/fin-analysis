from abc import ABC, abstractmethod


class Strategy(ABC):
    @abstractmethod
    def decisions(self, frame, signals, parameters):
        """Return close-known entry/exit masks and optional max holding sessions."""
