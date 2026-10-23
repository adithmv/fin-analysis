from datetime import datetime, time
from zoneinfo import ZoneInfo
from ..linking.linker import match


def effective_date(published, sessions, assumed=False):
    if assumed or not published:
        return None
    dt = datetime.fromisoformat(published)
    if dt.tzinfo is None:
        raise ValueError("Publication timestamp must be timezone-aware")
    for day in sorted(set(sessions)):
        opened = datetime.combine(datetime.fromisoformat(day).date(), time(9, 15), ZoneInfo("Asia/Kolkata"))
        if opened > dt:
            return day
    return None


def classify(article, links, config, sessions, tier=2, group_size=1, minimum=0.7):
    title = article["title"]
    category = article.get("raw", {}).get("category", "")
    matches = []
    mapped = config["exchange_category_map"].get(category)
    if mapped:
        matches = [(mapped, "exchange_category", category)]
    else:
        for key, rule in config["event_types"].items():
            found = next((p for p in rule["patterns"] if match(p.strip(), title)), None)
            if found:
                matches.append((key, "rules", found))
    if not matches:
        matches = [("other", "rules", "no_matching_rule")]
    output = []
    for linked in links:
        if linked["confidence"] < minimum:
            continue
        for key, method, rule in matches:
            definition = config["event_types"][key]
            if definition.get("scope") == "MARKET" and linked["symbol"] != "MARKET":
                continue
            bumps = config["importance"]
            importance = min(
                5,
                definition["importance"]
                + (bumps["trusted_bump"] if tier <= bumps["trusted_tier_max"] else 0)
                + (bumps["coverage_bump"] if group_size >= bumps["coverage_min"] else 0),
            )
            output.append(
                dict(
                    article_id=article["id"],
                    symbol=linked["symbol"],
                    exchange="NSE",
                    event_type=key,
                    importance=importance,
                    published_at=article["published_at"],
                    effective_trading_date=effective_date(
                        article["published_at"],
                        sessions.get(linked["symbol"], []),
                        article["published_at_assumed"],
                    ),
                    classifier=method,
                    matched_rule=rule,
                    details={
                        "link_confidence": linked["confidence"],
                        "dedupe_group_id": article["dedupe_group_id"],
                    },
                    logic_version=config["logic_version"],
                )
            )
    return output
