import json
from data.asof_db import KEYS

TYPES = {
    "candles": "candle",
    "indicator_values": "indicator",
    "signals": "signal",
    "signal_stats": "signal_stats",
    "articles": "article",
    "news_events": "news_event",
    "corporate_actions": "corporate_action",
    "analysis_reports": "report",
}


def reference(table, row):
    return {"type": TYPES[table], **{k: row[k] for k in KEYS.get(table, ["id"])}}


def canonical(ref):
    return json.dumps(ref, sort_keys=True, separators=(",", ":"))


def resolve_pack(pack, evidence_id):
    item = next((x for x in pack["items"] if x["evidence_id"] == evidence_id), None)
    if item is None:
        raise ValueError("Reference not found in frozen evidence pack")
    return item
