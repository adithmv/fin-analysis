import re


def match(phrase, text, case=False):
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text, 0 if case else re.I)


def link(article, aliases, version, minimum=0.5):
    title = article["title"]
    text = title + " " + (article.get("summary") or "")
    tagged = article.get("raw", {}).get("exchange_symbol")
    result = []
    for symbol, config in aliases.items():
        candidates = []
        if tagged == symbol:
            candidates.append((1.0, "exchange_tag", symbol))
        for name in config.get("names", []):
            if match(name, text):
                candidates.append((0.98 if match(name, title) else 0.9, "company_name", name))
        for alias in config.get("aliases", []):
            if not match(alias, text, alias == symbol):
                continue
            if alias in config.get("ambiguous_aliases", []):
                supported = any(match(c, text) for c in config.get("context", []))
                confidence = 0.8 if supported else 0.3
            else:
                confidence = 0.85 if match(alias, title, alias == symbol) else 0.75
            candidates.append((confidence, "alias", alias))
        if match(symbol, text, True):
            candidates.append((0.8 if len(symbol) > 3 else 0.65, "ticker", symbol))
        if candidates:
            confidence, kind, matched = max(candidates)
            if confidence >= minimum:
                result.append(
                    dict(
                        article_id=article["id"],
                        symbol=symbol,
                        exchange="NSE",
                        confidence=confidence,
                        match_type=kind,
                        matched_text=matched,
                        in_title=bool(match(matched, title)),
                        linker_version=version,
                    )
                )
    for phrase in (
        "RBI",
        "repo rate",
        "monetary policy",
        "Union Budget",
        "global markets",
        "Federal Reserve",
        "Nifty",
        "Sensex",
    ):
        if match(phrase, title):
            result.append(
                dict(
                    article_id=article["id"],
                    symbol="MARKET",
                    exchange="NSE",
                    confidence=0.95,
                    match_type="macro_rule",
                    matched_text=phrase,
                    in_title=True,
                    linker_version=version,
                )
            )
            break
    return result
