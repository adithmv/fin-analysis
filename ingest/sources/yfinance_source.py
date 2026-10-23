from datetime import timedelta
from .base import PriceSource, normalize


class YFinanceSource(PriceSource):
    name = 'yfinance'
    # Yahoo's historical OHLC is split-adjusted even with auto_adjust=False.
    adjusted = True
    url = 'https://finance.yahoo.com/'

    def fetch_daily(self, symbol, start, end):
        import yfinance as yf
        frame = yf.Ticker(f'{symbol}.NS').history(
            start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(),
            interval='1d', auto_adjust=False, back_adjust=False, actions=False,
            repair=False, timeout=15,
        )
        return normalize(frame)
