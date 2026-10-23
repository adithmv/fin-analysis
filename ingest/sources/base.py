from abc import ABC, abstractmethod
from datetime import date
import pandas as pd


class SourceError(Exception):
    def __init__(self, message, *, blocked=False, transient=False):
        super().__init__(message)
        self.blocked = blocked
        self.transient = transient


class PriceSource(ABC):
    name: str
    adjusted = False
    url: str

    @abstractmethod
    def fetch_daily(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """Inclusive dates. Return ts/open/high/low/close/volume. Raise SourceError."""


def normalize(frame, mapping=None):
    if frame is None or frame.empty:
        raise SourceError('Source returned no candles')
    frame = frame.reset_index().rename(columns=mapping or {})
    frame.columns = [str(c).lower() for c in frame.columns]
    frame = frame.rename(columns={'date': 'ts', 'timestamp': 'ts', 'datetime': 'ts'})
    if 'volume' not in frame:
        frame['volume'] = None
    required = ['ts', 'open', 'high', 'low', 'close', 'volume']
    if not set(required).issubset(frame.columns):
        raise SourceError('Source response is missing required price columns')
    return frame[required].copy()


def source_error(exc):
    status = getattr(getattr(exc, 'response', None), 'status_code', None)
    message = str(exc)
    blocked = status in (403, 429) or any(x in message.lower() for x in ('429', '403', 'too many requests', 'rate limit'))
    transient = status in (500, 502, 503, 504) or any(x in (type(exc).__name__ + message).lower() for x in ('timeout', 'connection', 'temporarily'))
    return SourceError(message, blocked=blocked, transient=transient)
