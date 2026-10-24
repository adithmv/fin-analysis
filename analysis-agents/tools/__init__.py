"""Bounded, read-only views over a thread's already cutoff-checked snapshot."""

from copy import deepcopy
from datetime import timedelta
import httpx
from data.asof_db import instant, guard
from verifier import TABLES
from shared.logbook import log_event


class ResearchTools:
    def __init__(self, pack, run_id, max_calls=12, search_client=httpx):
        self.pack, self.run_id = pack, run_id
        self.calls, self.max_calls = 0, max_calls
        self.event_ids = []
        self.search_client = search_client

    def _read(self, name, sections, symbol=None, days=None, predicate=lambda row: True, limit=50):
        if self.calls >= self.max_calls:
            raise ValueError("Read-only tool call limit reached")
        self.calls += 1
        if symbol and symbol != self.pack["symbol"]:
            raise ValueError("Tool scope is this discussion's stock")
        if not 1 <= limit <= 50 or (days is not None and not 1 <= days <= 365):
            raise ValueError("Tool row/day limit exceeded")
        cutoff = instant(self.pack["cutoff"])
        result = []
        for item in self.pack["items"]:
            if item["section"] not in sections or not predicate(item["row"]):
                continue
            row = item["row"]
            guard(TABLES[item["ref"]["type"]], row, cutoff)
            stamp = row.get("ts") or row.get("published_at") or row.get("created_at")
            if days and stamp and instant(stamp) < cutoff - timedelta(days=days):
                continue
            result.append(item)
        event = log_event(
            self.run_id,
            "analysis-agents",
            "tool_call",
            "success",
            tool=name,
            output_summary=f"{min(len(result), limit)} frozen evidence references",
            return_id=True,
        )
        if isinstance(event, int) and not isinstance(event, bool):
            self.event_ids.append(event)
        return deepcopy(result[-limit:])

    def get_candles(self, symbol, days=30):
        return self._read("get_candles", {"prices"}, symbol, days)

    def get_indicators(self, symbol, series_keys=(), days=30):
        return self._read(
            "get_indicators",
            {"indicators"},
            symbol,
            days,
            lambda r: not series_keys or r["series_key"] in series_keys,
        )

    def get_signals(self, symbol, days=30, types=()):
        return self._read(
            "get_signals", {"signals"}, symbol, days, lambda r: not types or r["signal_type"] in types
        )

    def get_signal_stats(self, signal_key, scope="POOLED"):
        return self._read(
            "get_signal_stats",
            {"track_records"},
            predicate=lambda r: r["signal_key"] == signal_key and r["scope"] == scope,
        )

    def get_news(self, symbol, days=14, min_importance=1):
        ids = {
            i["row"].get("article_id")
            for i in self.pack["items"]
            if i["section"] == "events" and i["row"]["importance"] >= min_importance
        }
        return self._read("get_news", {"news"}, symbol, days, lambda r: r["id"] in ids)

    def get_corporate_actions(self, symbol):
        return self._read("get_corporate_actions", {"actions"}, symbol)

    def get_data_quality(self, symbol):
        return {
            "items": self._read("get_data_quality", {"quality"}, symbol),
            "notes": list(self.pack["quality_notes"]),
            "latest_session": self.pack["latest_session"],
        }

    def get_past_reports(self, symbol, k=5):
        return self._read("get_past_reports", {"previous_report"}, symbol, limit=k)

    def search_similar_news(self, query, symbol, k=5):
        if not 1 <= len(query) <= 500 or not 1 <= k <= 20:
            raise ValueError("Search size limit exceeded")
        # Only the local stored-embedding service is reachable; its rows are intersected
        # with the original snapshot so late ingestion can never enter a replay.
        candidates = self._read("search_similar_news", {"news"}, symbol)
        response = self.search_client.get(
            "http://127.0.0.1:8766/search",
            params={"q": query, "symbol": symbol, "k": 20, "end": self.pack["cutoff"]},
            timeout=30,
        )
        response.raise_for_status()
        found = response.json()
        ids = [r["article_id"] for r in (found if isinstance(found, list) else found["items"])]
        lookup = {i["row"]["id"]: i for i in candidates}
        return {
            "label": "Anecdotal similarity within frozen evidence only; not statistical evidence",
            "items": [lookup[i] for i in ids if i in lookup][:k],
        }
