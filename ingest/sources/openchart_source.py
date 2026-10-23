from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from .base import PriceSource, SourceError, normalize


class OpenChartSource(PriceSource):
    name = "openchart"
    url = "https://github.com/marketcalls/openchart"

    def fetch_daily(self, symbol, start, end):
        from openchart import NSEData

        nse = NSEData()
        # The library otherwise silently takes the first fuzzy search result.
        results = nse.search(symbol, "EQ")
        if results.empty or "symbol" not in results:
            raise SourceError(f"No exact OpenChart match for {symbol}")
        exact = results[results["symbol"].str.upper().isin([symbol.upper(), f"{symbol.upper()}-EQ"])]
        if exact.empty:
            raise SourceError(f"No exact OpenChart match for {symbol}")
        tz = ZoneInfo("Asia/Kolkata")
        return normalize(
            nse.historical(
                str(exact.iloc[0]["symbol"]),
                "EQ",
                datetime.combine(start, time.min, tz),
                datetime.combine(end + timedelta(days=1), time.min, tz),
                "1d",
            )
        )
