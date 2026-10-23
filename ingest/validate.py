"""Validate candles before any database write."""
from dataclasses import dataclass
from datetime import date
import numpy as np
import pandas as pd

try:
    from .sources.base import SourceError
except ImportError:
    from sources.base import SourceError


@dataclass
class ValidationResult:
    frame: pd.DataFrame
    warnings: list[str]


def session_timestamp(value):
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        return pd.NaT
    if ts.tzinfo is None:
        ts = ts.tz_localize('Asia/Kolkata')
    else:
        ts = ts.tz_convert('Asia/Kolkata')
    return ts.normalize().tz_convert('UTC')


def validate(frame, start: date, end: date):
    required = {'ts', 'open', 'high', 'low', 'close', 'volume'}
    if frame is None or frame.empty:
        raise SourceError('Source returned no candles')
    if not required.issubset(frame.columns):
        raise SourceError('Missing required candle columns')
    result = frame.copy()
    warnings = []
    def safe_ts(value):
        try:
            return session_timestamp(value)
        except (ValueError, TypeError, OverflowError):
            return pd.NaT
    result['ts'] = pd.to_datetime(result['ts'].map(safe_ts), utc=True)
    prices = ['open', 'high', 'low', 'close']
    for column in prices:
        result[column] = pd.to_numeric(result[column], errors='coerce')
    valid = result['ts'].notna() & np.isfinite(result[prices]).all(axis=1) & (result[prices] > 0).all(axis=1)
    valid &= (result.high >= result[['open','close']].max(axis=1)) & (result.low <= result[['open','close']].min(axis=1))
    valid &= result.ts.between(session_timestamp(start), session_timestamp(end))
    if count := int((~valid).sum()):
        warnings.append(f'Dropped {count} invalid or out-of-range candles')
    result = result[valid].copy()
    duplicates = int(result.duplicated('ts').sum())
    if duplicates:
        warnings.append(f'Removed {duplicates} duplicate timestamps; kept last')
        result = result.drop_duplicates('ts', keep='last')
    if result.empty:
        raise SourceError('No valid candles remain after validation')
    volume = pd.to_numeric(result.volume, errors='coerce')
    invalid_volume = volume.notna() & (~np.isfinite(volume) | (volume < 0) | (volume % 1 != 0) | (volume > 9223372036854775807))
    if invalid_volume.any():
        warnings.append(f'Cleared {int(invalid_volume.sum())} invalid volume values')
    result['volume'] = volume.mask(invalid_volume).astype('Int64')
    if result.volume.isna().mean() >= 0.2:
        warnings.append('Volume missing for at least 20% of candles')
    result = result.sort_values('ts').reset_index(drop=True)
    expected = set(pd.bdate_range(start, end).date)
    actual = set(result.ts.dt.tz_convert('Asia/Kolkata').dt.date)
    if missing := len(expected - actual):
        warnings.append(f'{missing} weekdays without candles; may include market holidays')
    if (result.close.pct_change().abs() > 0.20).any():
        warnings.append('Price jump above 20%; possible split/bonus, data may be unadjusted')
    return ValidationResult(result, warnings)
