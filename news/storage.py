"""Small news-owned database helpers; no dependencies on sibling modules."""

import time
import httpx


def execute(query):
    for attempt in range(3):
        try:
            return query.execute().data
        except (httpx.ConnectError, httpx.ConnectTimeout):
            if attempt == 2:
                raise
            time.sleep(0.5 * 2**attempt)


def read(client, table, filters=None, columns="*"):
    rows = []
    keys = {
        "news_sources": ["source_key"],
        "article_symbols": ["article_id", "symbol", "exchange"],
        "article_sentiment": ["article_id", "scope", "model_key", "model_revision"],
        "article_embeddings": ["article_id", "model_key"],
        "candles": ["symbol", "ts"],
        "signals": ["symbol", "ts", "signal_key"],
        "watchlist": ["symbol", "exchange"],
    }
    for offset in range(0, 1000000, 500):
        query = client.table(table).select(columns)
        for k, v in (filters or {}).items():
            query = query.eq(k, v)
        for key in keys.get(table, ["id"]):
            query = query.order(key)
        page = execute(query.range(offset, offset + 499))
        rows.extend(page)
        if len(page) < 500:
            return rows
    raise ValueError("Archive exceeds supported local batch size")


def upsert(client, table, rows, conflict, ignore=False):
    for start in range(0, len(rows), 100):
        execute(
            client.table(table).upsert(
                rows[start : start + 100], on_conflict=conflict, ignore_duplicates=ignore
            )
        )


def store_articles(client, rows):
    # Existing articles retain first-fetch and processing state. No duplicated URL can be inserted.
    existing = {r["url_hash"] for r in read(client, "articles", columns="id,url_hash")}
    new = list({r["url_hash"]: r for r in rows if r["url_hash"] not in existing}.values())
    upsert(client, "articles", new, "url_hash", True)
    return len(new)
