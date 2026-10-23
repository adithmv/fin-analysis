"""Verified NSE date windows and BSE's documented paginated API; no documents fetched."""

from datetime import datetime, timedelta
from pathlib import Path
import time
from ..normalize import article, plain


def fetch(symbol, exchange, since, until, aliases):
    rows = []
    if exchange == "NSE":
        from dalal.nse import NSESession

        session = NSESession()
        start = since
        while start <= until:
            end = min(start + timedelta(days=89), until)
            data = session.fetch(
                "/corporate-announcements",
                params={
                    "index": "equities",
                    "symbol": symbol,
                    "from_date": start.strftime("%d-%m-%Y"),
                    "to_date": end.strftime("%d-%m-%Y"),
                },
            )
            if not isinstance(data, list):
                raise ValueError("Unexpected NSE announcement response")
            for item in data:
                if item.get("symbol") != symbol:
                    continue
                external = str(item.get("seq_id") or item.get("dt"))
                url = (
                    item.get("attchmntFile")
                    or f"https://www.nseindia.com/companies-listing/corporate-filings-announcements?symbol={symbol}&id={external}"
                )
                summary = plain(item.get("attchmntText"))
                rows.append(
                    article(
                        "nse_announcements",
                        url,
                        f"{symbol}: {summary or item.get('desc', 'Announcement')}",
                        summary,
                        item.get("exchdisstime") or item.get("an_dt"),
                        raw={
                            "exchange_symbol": symbol,
                            "category": item.get("desc"),
                            "origin_exchange": "NSE",
                        },
                        external_id=external,
                    )
                )
            start = end + timedelta(days=1)
            time.sleep(0.4)
    else:
        from bse import BSE

        folder = Path(__file__).resolve().parents[1] / ".cache"
        folder.mkdir(exist_ok=True)
        with BSE(download_folder=folder) as session:
            page = 1
            received = 0
            while True:
                data = session.announcements(
                    scripcode=aliases[symbol]["bse_code"],
                    page_no=page,
                    from_date=datetime.combine(since, datetime.min.time()),
                    to_date=datetime.combine(until, datetime.min.time()),
                )
                items = data.get("Table", [])
                for item in items:
                    if str(item.get("SCRIP_CD")) != aliases[symbol]["bse_code"]:
                        continue
                    external = str(item["NEWSID"])
                    url = (
                        "https://www.bseindia.com/xml-data/corpfiling/AttachLive/" + item["ATTACHMENTNAME"]
                        if item.get("ATTACHMENTNAME")
                        else f"https://www.bseindia.com/corporates/ann.html?newsid={external}"
                    )
                    title = plain(item.get("HEADLINE") or item.get("NEWSSUB"))
                    rows.append(
                        article(
                            "bse_announcements",
                            url,
                            f"{symbol}: {title}",
                            item.get("NEWSSUB", ""),
                            item.get("DissemDT") or item.get("DT_TM"),
                            raw={
                                "exchange_symbol": symbol,
                                "category": item.get("SUBCATNAME") or item.get("CATEGORYNAME"),
                                "origin_exchange": "BSE",
                            },
                            external_id=external,
                        )
                    )
                received += len(items)
                total = int((data.get("Table1") or [{"ROWCNT": received}])[0].get("ROWCNT", received))
                if not items or received >= total:
                    break
                page += 1
                if page > 1000:
                    raise ValueError("BSE pagination exceeded safety limit")
                time.sleep(0.4)
    return rows
