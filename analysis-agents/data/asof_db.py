"""All market-data reads are allowlisted, bounded, and checked against a cutoff."""

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

DATES = {
    "candles": "ts",
    "indicator_values": "ts",
    "signals": "ts",
    "signal_stats": "computed_at",
    "articles": "published_at",
    "news_events": "published_at",
    "corporate_actions": "announced_at",
    "article_sentiment": "computed_at",
    "analysis_reports": "created_at",
    "report_outcomes": "graded_at",
    "agent_events": "ts",
}
KEYS = {
    "candles": ["symbol", "exchange", "timeframe", "ts"],
    "indicator_values": ["symbol", "exchange", "timeframe", "ts", "series_key"],
    "signals": ["symbol", "exchange", "timeframe", "ts", "signal_key"],
    "article_symbols": ["article_id", "symbol", "exchange"],
    "article_sentiment": ["article_id", "scope", "model_key", "model_revision"],
    "report_outcomes": ["report_id", "horizon_days"],
}


def instant(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


class FutureData(ValueError):
    pass


def guard(table, row, cutoff):
    if table not in DATES and table != "article_symbols":
        raise ValueError("Table not permitted")
    fields = [DATES.get(table)]
    if table in ("candles", "articles", "corporate_actions"):
        fields.append("fetched_at")
    if table in ("indicator_values", "signals", "news_events"):
        fields.append("computed_at")
    if table == "signal_stats":
        fields.append("period_end")
    if table == "report_outcomes":
        fields.append("exit_date")
    for field in fields:
        if field and row.get(field) and instant(row[field]) > cutoff:
            raise FutureData(f"{table}.{field} after cutoff")
    if table == "corporate_actions" and not row.get("announced_at"):
        # Unknown announcement time cannot establish historical availability; fetched_at is explicit.
        if not row.get("fetched_at"):
            raise FutureData("Corporate action availability unknown")
    if table in ("candles", "indicator_values", "signals"):
        day = instant(row["ts"]).astimezone(ZoneInfo("Asia/Kolkata")).date()
        if datetime.combine(day, time(15, 30), ZoneInfo("Asia/Kolkata")) > cutoff:
            raise FutureData("Daily session not complete at cutoff")
    return row


class AsOfDB:
    def __init__(self, client, cutoff):
        self._client = client
        self.cutoff = instant(cutoff)

    def rows(self, table, filters=None, since=None, limit=5000):
        if table not in DATES and table != "article_symbols":
            raise ValueError("Table not permitted")
        result = []
        for offset in range(0, 100000, 500):
            query = self._client.table(table).select("*")
            for key, value in (filters or {}).items():
                query = query.eq(key, value)
            dated = DATES.get(table)
            if dated and table != "corporate_actions":
                query = query.lte(dated, self.cutoff.isoformat())
                if since:
                    query = query.gte(dated, since)
            if dated:
                query = query.order(dated, desc=True)
            for key in KEYS.get(table, ["id"]):
                if key != dated:
                    query = query.order(key)
            page = query.range(offset, offset + 499).execute().data
            for row in page:
                try:
                    guard(table, row, self.cutoff)
                except FutureData:
                    continue
                if table == "articles" and row["published_at_assumed"]:
                    continue
                result.append(row)
                if len(result) >= limit:
                    return result
            if len(page) < 500:
                return result
        raise ValueError("Read exceeded archive bound")

    def resolve(self, ref):
        kind = ref.get("type")
        tables = {
            "candle": "candles",
            "indicator": "indicator_values",
            "signal": "signals",
            "signal_stats": "signal_stats",
            "article": "articles",
            "news_event": "news_events",
            "corporate_action": "corporate_actions",
            "report": "analysis_reports",
            "agent_event": "agent_events",
        }
        if kind not in tables:
            raise ValueError("Unknown evidence type")
        table = tables[kind]
        filters = {k: v for k, v in ref.items() if k != "type"}
        permitted = set(KEYS.get(table, ["id"]))
        if not filters or set(filters) - permitted:
            raise ValueError("Malformed evidence reference")
        found = self.rows(table, filters, limit=2)
        if len(found) != 1:
            raise ValueError("Evidence unavailable or ambiguous at cutoff")
        return found[0]
