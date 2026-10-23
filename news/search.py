from datetime import datetime
from zoneinfo import ZoneInfo
from .storage import execute, read
from .events.classifier import effective_date

_embedder = None


def search(client, config, query, symbol=None, k=10, from_date=None, to_date=None, event=None):
    global _embedder
    if not query.strip() or len(query) > 500:
        raise ValueError("Search requires 1–500 characters")
    if _embedder is None:
        from .embeddings.embedder import Embedder

        _embedder = Embedder(config["embeddings"])
    vector = _embedder.encode([query])[0]
    rows = execute(
        client.rpc(
            "search_news",
            {
                "query_embedding": vector,
                "requested_model": _embedder.key,
                "result_limit": min(50, max(1, k)),
                "filter_symbol": symbol,
                "from_date": from_date,
                "to_date": to_date,
                "filter_event": event,
            },
        )
    )
    for row in rows:
        row["symbols"] = execute(
            client.table("article_symbols").select("symbol,confidence").eq("article_id", row["article_id"])
        )
        cfg = config["sentiment"]
        row["sentiment"] = execute(
            client.table("article_sentiment")
            .select("label,score")
            .eq("article_id", row["article_id"])
            .eq("model_key", cfg["model"])
            .eq("model_revision", cfg["revision"])
            .eq("scope", cfg["scope"])
        )
    return rows


def similar(client, config, article_id, symbol=None, k=5):
    article = execute(client.table("articles").select("*").eq("id", article_id).limit(1))
    if not article:
        raise ValueError("Article not found")
    article = article[0]
    key = config["embeddings"]["model"] + "@" + config["embeddings"]["revision"]
    embedding = execute(
        client.table("article_embeddings")
        .select("embedding")
        .eq("article_id", article_id)
        .eq("model_key", key)
        .limit(1)
    )
    if not embedding:
        return {
            "label": "Anecdotal similarity, not statistical evidence",
            "items": [],
            "reason": "This article has no stored embedding",
        }
    import json

    vector = embedding[0]["embedding"]
    if isinstance(vector, str):
        vector = json.loads(vector)
    results = execute(
        client.rpc(
            "search_news",
            {
                "query_embedding": vector,
                "requested_model": key,
                "result_limit": k,
                "filter_symbol": symbol,
                "to_date": article["published_at"],
            },
        )
    )
    cached = {}
    for row in results:
        links = execute(
            client.table("article_symbols").select("symbol,confidence").eq("article_id", row["article_id"])
        )
        outcomes = []
        original = execute(
            client.table("articles").select("published_at_assumed").eq("id", row["article_id"]).limit(1)
        )[0]
        for link in links:
            stock = link["symbol"]
            if stock == "MARKET":
                stock = config["benchmark"]
            if link["confidence"] < config["linking"]["min_confidence_for_events"]:
                continue
            if stock not in cached:
                candles = read(client, "candles", {"symbol": stock, "exchange": "NSE", "timeframe": "1d"})
                candles.sort(key=lambda c: c["ts"])
                dates = [
                    datetime.fromisoformat(c["ts"]).astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()
                    for c in candles
                ]
                flags = read(
                    client,
                    "signals",
                    {"symbol": stock, "signal_type": "data_flag"},
                    columns="symbol,ts,signal_key",
                )
                excluded = set()
                for flag in flags:
                    day = (
                        datetime.fromisoformat(flag["ts"])
                        .astimezone(ZoneInfo("Asia/Kolkata"))
                        .date()
                        .isoformat()
                    )
                    if day in dates:
                        i = dates.index(day)
                        excluded.update(
                            range(max(0, i - 20), min(len(dates), i + 21))
                            if flag["signal_key"] == "possible_split_or_bonus"
                            else [i]
                        )
                cached[stock] = (candles, dates, excluded)
            candles, dates, excluded = cached[stock]
            entry = effective_date(row["published_at"], dates, original["published_at_assumed"])
            if not entry:
                continue
            i = dates.index(entry)
            moves = {
                str(h): float(candles[i + h - 1]["close"]) / float(candles[i]["open"]) - 1
                if i + h <= len(candles) and not any(j in excluded for j in range(i, i + h))
                else None
                for h in (1, 5, 20)
            }
            outcomes.append({"symbol": stock, "entry_date": entry, "price_moves_before_costs": moves})
        row["outcomes"] = outcomes
    return {
        "label": "Anecdotal similarity, not statistical evidence. Price moves are before costs; unavailable or excluded outcomes are blank.",
        "items": results,
    }
