from datetime import datetime
import hashlib
import re
from ..normalize import timestamp


def parse(subject):
    low = subject.lower()
    kind = next(
        (
            kind
            for phrase, kind in [
                ("demerger", "demerger"),
                ("merger", "merger"),
                ("bonus", "bonus"),
                ("split", "split"),
                ("sub-division", "split"),
                ("dividend", "dividend"),
                ("rights", "rights"),
                ("buyback", "buyback"),
            ]
            if phrase in low
        ),
        "other",
    )
    value = None
    if kind == "bonus":
        ratios = re.findall(r"\b(\d+)\s*:\s*(\d+)\b", subject)
        if len(ratios) == 1 and all(int(n) > 0 for n in ratios[0]):
            value = {"new_shares": int(ratios[0][0]), "existing_shares": int(ratios[0][1])}
    elif kind == "dividend":
        amounts = re.findall(
            r"(?:Rs\.?|INR|₹)\s*(\d+(?:\.\d+)?)\s*(?:/-)?\s*(?:per share|per equity share)", subject, re.I
        )
        if len(amounts) == 1:
            value = {"amount_inr_per_share": float(amounts[0])}
    elif kind == "split":
        result = re.search(
            r"from\s*(?:Rs\.?)?\s*(\d+(?:\.\d+)?)\s*/?-?\s*(?:per share)?\s*to\s*(?:Rs\.?)?\s*(\d+(?:\.\d+)?)",
            subject,
            re.I,
        )
        if result and all(float(n) > 0 for n in result.groups()):
            value = {"old_face_value": float(result[1]), "new_face_value": float(result[2])}
    return kind, value, "parsed" if value else "needs_review"


def date_value(value):
    if not value or value == "-":
        return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def fetch(symbol, since, until):
    from dalal.nse import NSESession

    data = NSESession().fetch(
        "/corporates-corporateActions",
        params={
            "index": "equities",
            "symbol": symbol,
            "from_date": since.strftime("%d-%m-%Y"),
            "to_date": until.strftime("%d-%m-%Y"),
        },
    )
    if not isinstance(data, list):
        raise ValueError("Unexpected NSE corporate-action response")
    rows = []
    for item in data:
        if item.get("symbol") != symbol:
            continue
        subject = item.get("subject", "")
        kind, parsed, status = parse(subject)
        ex = date_value(item.get("exDate"))
        identity = "|".join((symbol, "NSE", kind, ex or "1900-01-01", "NSE"))
        rows.append(
            dict(
                identity_key=hashlib.sha256(identity.encode()).hexdigest(),
                symbol=symbol,
                exchange="NSE",
                action_type=kind,
                ex_date=ex,
                record_date=date_value(item.get("recDate")),
                announced_at=timestamp(item["caBroadcastDate"])[0] if item.get("caBroadcastDate") else None,
                ratio_text=subject,
                parsed=parsed,
                parse_status=status,
                source="NSE",
                source_ref=f"https://www.nseindia.com/companies-listing/corporate-filings-actions?symbol={symbol}",
            )
        )
    return rows
