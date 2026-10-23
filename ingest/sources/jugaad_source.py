from .base import PriceSource, normalize


class JugaadSource(PriceSource):
    name = 'jugaad'
    url = 'https://www.nseindia.com/report-detail/eq_security'

    def fetch_daily(self, symbol, start, end):
        from jugaad_data.nse import stock_df
        frame = stock_df(symbol=symbol, from_date=start, to_date=end, series='EQ')
        return normalize(frame, {'DATE': 'ts', 'OPEN': 'open', 'HIGH': 'high',
                                 'LOW': 'low', 'CLOSE': 'close', 'VOLUME': 'volume'})
