from datetime import timedelta
import hashlib
import json
from data.asof_db import AsOfDB
from .refs import reference


def build(db: AsOfDB, symbol, config):
    cfg = config["agents"]["evidence_pack"]
    items = []
    notes = []
    seen = set()

    def add(table, row, section):
        ref = reference(table, row)
        identity = json.dumps(ref, sort_keys=True)
        if identity in seen:
            return
        seen.add(identity)
        excluded = {
            "raw",
            "provenance",
            "config",
            "processing",
            "embedding",
            "input_summary",
            "error",
            "meta",
        }
        clean = {k: v for k, v in row.items() if k not in excluded}
        if table == "articles":
            clean = {
                k: clean[k]
                for k in (
                    "id",
                    "title",
                    "summary",
                    "url",
                    "source_key",
                    "published_at",
                    "published_at_assumed",
                    "fetched_at",
                    "is_duplicate",
                    "dedupe_group_id",
                )
                if k in clean
            }
            clean["untrusted_text"] = True
        items.append({"evidence_id": f"e{len(items) + 1:04d}", "section": section, "ref": ref, "row": clean})

    def since(days):
        return (db.cutoff - timedelta(days=days)).isoformat()

    candles = db.rows(
        "candles", {"symbol": symbol, "exchange": "NSE", "timeframe": "1d"}, limit=cfg["candles_days"]
    )
    if not candles:
        raise ValueError("No candles available before cutoff, including ingestion time")
    candles.sort(key=lambda r: r["ts"])
    for r in candles:
        add("candles", r, "prices")
    latest = candles[-1]
    indicators = db.rows(
        "indicator_values",
        {"symbol": symbol, "ts": latest["ts"], "exchange": "NSE", "timeframe": "1d"},
        limit=100,
    )
    for r in indicators:
        add("indicator_values", r, "indicators")
    signals = db.rows(
        "signals",
        {"symbol": symbol, "exchange": "NSE", "timeframe": "1d"},
        since(cfg["signals_days"]),
        limit=1000,
    )
    # Keep newest instance of each signal/direction, plus all recent quality flags.
    unique = set()
    chosen = []
    for r in signals:
        key = (r["signal_key"], r["direction"])
        if key not in unique or r["signal_type"] == "data_flag":
            chosen.append(r)
            unique.add(key)
    for r in chosen:
        add("signals", r, "quality" if r["signal_type"] == "data_flag" else "signals")
        if r["signal_type"] == "data_flag":
            notes.append(f"{r['signal_key']}: {r.get('description', 'Stored data-quality flag')}")
    links = db.rows("article_symbols", {"symbol": symbol}, limit=10000)
    article_ids = {r["article_id"] for r in links if float(r["confidence"]) >= 0.7}
    articles = db.rows("articles", since=since(cfg["news_days"]), limit=2000)
    articles = [r for r in articles if r["id"] in article_ids and not r["is_duplicate"]][
        : cfg["max_news_items"]
    ]
    events = []
    for a in articles:
        add("articles", a, "news")
        for r in db.rows("article_sentiment", {"article_id": a["id"]}, limit=1):
            # Sentiment is attached as metadata to the source article, not an invented ref type.
            items[-1]["row"]["sentiment"] = {
                k: r[k] for k in ("model_key", "model_revision", "label", "score", "computed_at")
            }
        for e in db.rows("news_events", {"article_id": a["id"], "symbol": symbol}, limit=15):
            events.append(e)
            add("news_events", e, "events")
    if not articles:
        notes.append("No company news available at this cutoff; do not invent coverage.")
    notes.append(
        "Phase 3 human accuracy review is pending; news labels and sentiment are unverified features."
    )
    actions = db.rows("corporate_actions", {"symbol": symbol, "exchange": "NSE"}, limit=100)
    for r in actions:
        day = r.get("ex_date")
        if day and abs((db.cutoff.date() - __import__("datetime").date.fromisoformat(day)).days) <= 45:
            add("corporate_actions", r, "actions")
    keys = {r["signal_key"] for r in chosen} | {"news:" + r["event_type"] for r in events}
    stats = db.rows("signal_stats", limit=30000)
    statkeys = set()
    for r in stats:
        if (
            r["signal_key"] not in keys
            or r["scope"] not in (symbol, "POOLED")
            or r["horizon_days"] != config["agents"]["horizon_days_default"]
        ):
            continue
        key = tuple(r[k] for k in ("signal_key", "direction", "scope", "sample", "horizon_days", "abnormal"))
        if key in statkeys:
            continue
        statkeys.add(key)
        add("signal_stats", r, "track_records")
    if not statkeys:
        notes.append("No historical statistics available before cutoff.")
    for r in db.rows("candles", {"symbol": "NIFTY50", "exchange": "NSE", "timeframe": "1d"}, limit=5):
        add("candles", r, "market")
    for r in db.rows("news_events", {"symbol": "MARKET"}, since(cfg["news_days"]), limit=10):
        add("news_events", r, "macro")
    previous = db.rows("analysis_reports", {"symbol": symbol}, limit=1)
    if previous:
        add("analysis_reports", previous[0], "previous_report")
    # Public data allowlist: no questions, users, credentials, request metadata or log messages enter prompts.
    pack = {
        "symbol": symbol,
        "cutoff": db.cutoff.isoformat(),
        "items": items,
        "quality_notes": notes,
        "latest_session": latest["ts"],
        "schema_version": "v1",
        "public_market_data_only": True,
    }
    encoded = json.dumps(pack, sort_keys=True, ensure_ascii=True, allow_nan=False)
    if len(encoded) > cfg["max_pack_characters"]:
        raise ValueError("Evidence pack exceeds configured size; narrow limits explicitly")
    return pack, hashlib.sha256(encoded.encode()).hexdigest()
