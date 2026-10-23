from datetime import date
from unittest.mock import MagicMock
import pandas as pd
import pytest
from ingest.sources.base import normalize, SourceError
from ingest.sources.jugaad_source import JugaadSource
from ingest.sources.openchart_source import OpenChartSource
from ingest.sources.yfinance_source import YFinanceSource


def test_normalize_empty():
    with pytest.raises(SourceError):
        normalize(pd.DataFrame())


def test_jugaad(monkeypatch):
    import jugaad_data.nse
    raw = pd.DataFrame([{'DATE': date(2026, 1, 2), 'OPEN': 100, 'HIGH': 105, 'LOW': 99, 'CLOSE': 102, 'VOLUME': 500}])
    monkeypatch.setattr(jugaad_data.nse, 'stock_df', lambda **kwargs: raw)
    frame = JugaadSource().fetch_daily('TCS', date(2026,1,1), date(2026,1,3))
    assert list(frame.columns) == ['ts','open','high','low','close','volume']
    assert frame.iloc[0]['close'] == 102


def test_yfinance_inclusive_end_and_adjustment(monkeypatch):
    import yfinance
    ticker = MagicMock()
    ticker.history.return_value = pd.DataFrame({'Open':[100], 'High':[105], 'Low':[99], 'Close':[102], 'Volume':[500]}, index=pd.DatetimeIndex(['2026-01-02'],name='Date'))
    monkeypatch.setattr(yfinance, 'Ticker', lambda symbol: ticker)
    frame = YFinanceSource().fetch_daily('TCS', date(2026,1,1), date(2026,1,3))
    assert ticker.history.call_args.kwargs['end'] == '2026-01-04'
    assert ticker.history.call_args.kwargs['auto_adjust'] is False
    assert len(frame) == 1
    assert YFinanceSource.adjusted


def test_openchart_rejects_fuzzy_match(monkeypatch):
    import openchart
    nse = MagicMock()
    nse.search.return_value = pd.DataFrame({'symbol':['OTHER-EQ']})
    monkeypatch.setattr(openchart, 'NSEData', lambda: nse)
    with pytest.raises(SourceError, match='exact'):
        OpenChartSource().fetch_daily('TCS',date(2026,1,1),date(2026,1,3))
    nse.historical.assert_not_called()
