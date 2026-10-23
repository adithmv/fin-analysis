import pandas as pd
from .base import PriceSource, SourceError, normalize


class JugaadSource(PriceSource):
    name = "jugaad"
    url = "https://www.nseindia.com/report-detail/eq_security"

    def fetch_daily(self, symbol, start, end):
        from jugaad_data.nse import stock_raw

        rows = stock_raw(symbol=symbol, from_date=start, to_date=end, series="EQ")
        if not rows:
            raise SourceError("NSE returned no candles")
        frame = pd.DataFrame(rows)
        if not {"CH_SYMBOL", "CH_SERIES", "CH_TIMESTAMP"}.issubset(frame.columns):
            raise SourceError("NSE response is missing identity or timestamps")
        frame = frame[(frame.CH_SYMBOL == symbol) & (frame.CH_SERIES == "EQ")].copy()
        # stock_df strips timezone information from UTC timestamps in this version.
        # Preserve the raw timezone so midnight IST does not shift to yesterday.
        frame["CH_TIMESTAMP"] = pd.to_datetime(frame.CH_TIMESTAMP, utc=True)
        return normalize(
            frame,
            {
                "CH_TIMESTAMP": "ts",
                "CH_OPENING_PRICE": "open",
                "CH_TRADE_HIGH_PRICE": "high",
                "CH_TRADE_LOW_PRICE": "low",
                "CH_CLOSING_PRICE": "close",
                "CH_TOT_TRADED_QTY": "volume",
            },
        )
