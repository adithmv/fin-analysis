from evidence.refs import resolve_pack
from data.asof_db import instant

DISCLAIMER = "Research analysis only, not investment advice or a recommendation to buy or sell."


def strength(pack, cited, stance, horizon, config):
    keys = set()
    for eid in cited:
        try:
            item = resolve_pack(pack, eid)
        except ValueError:
            continue
        r = item["row"]
        if item["ref"]["type"] == "signal":
            keys.add(r["signal_key"])
        if item["ref"]["type"] == "signal_stats":
            keys.add(r["signal_key"])
        if item["ref"]["type"] == "news_event":
            keys.add("news:" + r["event_type"])
    stats = [
        i["row"]
        for i in pack["items"]
        if i["section"] == "track_records"
        and i["row"]["signal_key"] in keys
        and i["row"]["horizon_days"] == horizon
    ]
    if not stats:
        return "none", ["No cited item has statistics at the report horizon"]
    direction = "bullish" if stance == "bullish" else "bearish" if stance == "bearish" else None
    qualified = []
    reasons = []
    for key in sorted(keys):
        if key.startswith(("news:", "sentiment:")):
            reasons.append(f"{key}: human accuracy review pending; cannot establish moderate/strong evidence")
            continue
        relevant = [
            r
            for r in stats
            if r["signal_key"] == key
            and r["scope"] == "POOLED"
            and r["direction"] == direction
            and not r.get("abnormal")
        ]
        good = {}
        for r in relevant:
            if (
                r.get("stats_run_id")
                and r["sufficient_sample"]
                and r["n_independent"] >= config["min_independent_events"]
                and r["edge"] is not None
                and float(r["edge"]) > 0
            ):
                good.setdefault(r["stats_run_id"], set()).add(r["sample"])
        if any({"in_sample", "out_of_sample"} <= samples for samples in good.values()):
            qualified.append(key)
            reasons.append(f"{key}: sufficient independent evidence and positive IS/OOS edge")
    if not qualified:
        return "weak", reasons + ["No cited directional item meets the sufficient positive IS/OOS rule"]
    families = {("candlestick" if k.startswith("cdl_") else k.split("_")[0]) for k in qualified}
    trend = next(
        (
            i["row"].get("details", {}).get("trend_state")
            for i in pack["items"]
            if i["section"] == "signals" and i["row"]["signal_key"] == "trend_state"
        ),
        None,
    )
    aligned = (stance == "bullish" and trend in ("uptrend", "up", "bullish")) or (
        stance == "bearish" and trend in ("downtrend", "down", "bearish")
    )
    if len(families) >= config["strong_requires_signals"] and aligned:
        return "strong", reasons + [
            "Distinct signal families align with stored trend; correlation can still remain"
        ]
    return "moderate", reasons


def build_report(output, verification, pack, config, messages):
    accepted = {r["claim_id"] for r in verification["claims"] if r["status"] in ("verified", "partial")}
    factual = [c for c in output.claims if c.id in accepted]
    stance = output.stance
    directions = {
        i["row"].get("direction")
        for i in pack["items"]
        if i["section"] == "signals" and i["evidence_id"] in {c.evidence_id for c in factual}
    }
    if {"bullish", "bearish"} <= directions:
        stance = "mixed"
    if len(factual) < 2 or verification["severe"] or verification["notes"]:
        stance = "neutral"
    cited = {c.evidence_id for c in factual if c.evidence_id}
    horizon = config["agents"]["horizon_days_default"]
    level, why = strength(pack, cited, stance, horizon, config["verification"]["evidence_strength"])
    confidence = "low" if level in ("none", "weak") or verification["severe"] else output.confidence

    def points(values):
        if verification["notes"] or verification["severe"]:
            return []
        return [
            {
                "text": p.text,
                "claim_ids": p.claim_ids,
                "evidence": [
                    resolve_pack(pack, c.evidence_id)["ref"]
                    for c in factual
                    if c.id in p.claim_ids and c.evidence_id
                ],
            }
            for p in values
            if p.claim_ids and set(p.claim_ids) <= accepted
        ]

    previous = next((i["row"] for i in pack["items"] if i["section"] == "previous_report"), None)
    counts = {
        s: sum(m.get("verification_status") == s for m in messages)
        for s in ("verified", "partial", "unverified", "not_applicable")
    }
    counts["severe"] = verification["severe"] or any(
        m.get("_verification", {}).get("severe") for m in messages
    )
    # Unverified free prose is withheld from the final report, even when some structured facts pass.
    summary = "\n".join(c.text for c in factual) or "No verified factual summary is available."
    return dict(
        symbol=pack["symbol"],
        as_of_date=pack["latest_session"][:10],
        stance=stance,
        confidence=confidence,
        horizon_days=horizon,
        summary_md=summary,
        key_points=points(output.key_points),
        risks=points(output.risks),
        invalidation=points(output.invalidation),
        what_changed={
            "previous_stance": previous["stance"] if previous else None,
            "current_stance": stance,
            "latest_session": pack["latest_session"],
            "previous_trend": previous.get("what_changed", {}).get("current_trend") if previous else None,
            "current_trend": next(
                (
                    i["row"].get("details", {}).get("trend_state")
                    for i in pack["items"]
                    if i["section"] == "signals" and i["row"].get("signal_key") == "trend_state"
                ),
                None,
            ),
            "new_signals": [
                i["evidence_id"]
                for i in pack["items"]
                if previous
                and i["section"] == "signals"
                and i["row"].get("ts")
                and instant(i["row"]["ts"]) > instant(previous["created_at"])
            ],
            "new_events": [
                i["evidence_id"]
                for i in pack["items"]
                if previous
                and i["section"] == "events"
                and i["row"].get("published_at")
                and instant(i["row"]["published_at"]) > instant(previous["created_at"])
            ],
        },
        evidence_strength=level,
        evidence_strength_why=why,
        data_quality_notes=pack["quality_notes"],
        verification_summary=counts,
        disclaimer=DISCLAIMER,
    )
