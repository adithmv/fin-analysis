import math
import re
from data.asof_db import guard, instant, FutureData
from evidence.refs import resolve_pack

TABLES = {
    "candle": "candles",
    "indicator": "indicator_values",
    "signal": "signals",
    "signal_stats": "signal_stats",
    "article": "articles",
    "news_event": "news_events",
    "corporate_action": "corporate_actions",
    "report": "analysis_reports",
}


def numbers(text):
    # Dates and indicator periods are identifiers, not measured financial values.
    text = re.sub(
        r"\b\d{4}-\d{2}-\d{2}(?:T[^ ]+)?\b|\be\d{4}\b|\b(?:RSI|SMA|EMA|ATR|ADX|MACD)\s*\(?\d+(?:[,_/-]\d+)*\)?",
        "",
        text,
        flags=re.I,
    )
    return [float(s.replace(",", "")) for s in re.findall(r"(?<![A-Za-z_])[-+]?\d[\d,]*(?:\.\d+)?", text)]


def verify(output, pack, config):
    tolerance = config["numeric_tolerance"]
    notes = []
    results = []
    allowed = []
    severe = False
    for claim in output.claims:
        c = claim.model_dump()
        status = "verified"
        reasons = []
        ref = None
        try:
            if c["kind"] == "opinion":
                if numbers(c["text"]):
                    raise ValueError("Opinion contains an unverified number")
                status = "not_applicable"
            else:
                item = resolve_pack(pack, c["evidence_id"])
                ref = item["ref"]
                r = item["row"]
                guard(TABLES[ref["type"]], r, instant(pack["cutoff"]))
                if c["kind"] == "numeric":
                    actual = r.get(c["metric"])
                    if isinstance(actual, bool) or actual is None or c["value"] is None:
                        raise ValueError("Numeric metric missing")
                    actual = float(actual)
                    limit = max(abs(actual) * tolerance["relative"], tolerance["absolute_small_values"])
                    if not math.isfinite(actual) or abs(actual - c["value"]) > limit:
                        raise ValueError(f"Value mismatch: stated {c['value']}; stored {actual}")
                    for value in numbers(c["text"]):
                        if abs(value - c["value"]) > limit:
                            raise ValueError("Claim text contains a number not supported by its metric")
                    allowed.append(c["value"])
                elif c["kind"] == "historical_performance":
                    if ref["type"] != "signal_stats" or r.get("edge") is None:
                        raise ValueError("No measured edge cited")
                    edge = float(r["edge"])
                    direction = "positive" if edge > 0 else "negative" if edge < 0 else "zero"
                    if c["relation"] != direction:
                        raise ValueError("Claim direction differs from stored edge")
                    if not r["sufficient_sample"]:
                        status = "partial"
                        reasons.append("Insufficient independent sample")
                    if r["sample"] != "out_of_sample":
                        status = "partial"
                        reasons.append("No out-of-sample support in this reference")
                    if numbers(c["text"]):
                        raise ValueError("Put historical numerical assertions in separate numeric claims")
                elif c["kind"] == "event":
                    if ref["type"] not in ("news_event", "corporate_action"):
                        raise ValueError("Event reference required")
                    kind = r.get("event_type", r.get("action_type"))
                    day = str(r.get("published_at") or r.get("announced_at") or r.get("ex_date"))[:10]
                    if c["event_type"] != kind or c["event_date"] != day:
                        raise ValueError("Event type/date mismatch")
                    status = "partial"
                    reasons.append(
                        "Stored event checked; source/classification accuracy is not independently verified"
                    )
                else:
                    if numbers(c["text"]):
                        raise ValueError("Observation has numbers: use a numeric claim")
                    status = "partial"
                    reasons.append("Reference exists; descriptive interpretation is not verified by code")
        except FutureData as exc:
            status = "unverified"
            reasons.append(str(exc))
            severe = True
        except (ValueError, TypeError, KeyError) as exc:
            status = "unverified"
            reasons.append(str(exc))
        results.append(dict(claim_id=c["id"], status=status, reasons=reasons, evidence_ref=ref))
    prose = " ".join(
        [output.content_md, output.counter_argument]
        + [p.text for p in output.key_points + output.risks + output.invalidation]
    )
    for value in numbers(prose):
        if not any(
            abs(value - v) <= max(abs(v) * tolerance["relative"], tolerance["absolute_small_values"])
            for v in allowed
        ):
            notes.append({"reason": "Unreferenced number in prose", "value": value})
    facts = [r for r in results if r["status"] != "not_applicable"]
    passed = [r for r in facts if r["status"] in ("verified", "partial")]
    if severe or (facts and not passed) or (not facts and notes):
        status = "unverified"
    elif notes or any(r["status"] != "verified" for r in facts):
        status = "partial"
    elif facts:
        status = "verified"
    else:
        status = "not_applicable"
    # Factual prose cannot become "verified" merely by supplying no claims.
    if not facts and not output.content_md.lower().startswith(("opinion:", "no evidence available")):
        notes.append({"reason": "No structured factual claims; prose has not been verified"})
        status = "unverified"
    return {"status": status, "claims": results, "notes": notes, "severe": severe}
