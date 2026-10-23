"""Plain-text snippets, stable identities, and explicit timezone assumptions."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo
from uuid import UUID, uuid5

IST = ZoneInfo("Asia/Kolkata")
NAMESPACE = UUID("7c435a90-d8bd-4010-ab51-b0e446832602")


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain(value, limit=600):
    parser = Text()
    parser.feed(str(value or ""))
    return " ".join(unescape(" ".join(parser.parts)).split())[:limit]


def clean_url(value):
    p = urlsplit(value.strip())
    if p.scheme.lower() not in ("https", "http") or not p.hostname or p.username or p.password:
        raise ValueError("Article URL must be a public HTTP(S) link")
    query = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid", "ref", "source", "cmpid")
    ]
    return urlunsplit(
        (p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/") or "/", urlencode(sorted(query)), "")
    )


def title_normalized(value):
    value = re.sub(
        r"\s*[|–—]\s*(moneycontrol|mint|livemint|business standard|the hindu|economic times).*$",
        "",
        plain(value, 1000),
        flags=re.I,
    )
    return " ".join(re.sub(r"[^\w\s]", " ", unicodedata.normalize("NFKC", value).lower()).split())


def timestamp(value, fetched_at=None):
    fetched_at = fetched_at or datetime.now(timezone.utc)
    dt = None
    if isinstance(value, datetime):
        dt = value
    elif value:
        text = str(value).strip()
        try:
            dt = parsedate_to_datetime(text)
        except (ValueError, TypeError):
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
                    try:
                        dt = datetime.strptime(text, fmt)
                        break
                    except ValueError:
                        pass
    if dt is None:
        return fetched_at.astimezone(timezone.utc).isoformat(), True, "missing_or_invalid"
    assumption = "timezone_missing_assumed_IST" if dt.tzinfo is None else None
    dt = dt.replace(tzinfo=IST) if dt.tzinfo is None else dt
    return dt.astimezone(timezone.utc).isoformat(), False, assumption


def article(
    source, url, title, summary="", published=None, raw=None, external_id=None, language="en", fetched=None
):
    title = plain(title, 500)
    if not title:
        raise ValueError("Empty article title")
    url = clean_url(url)
    fetched = fetched or datetime.now(timezone.utc)
    published_at, assumed, reason = timestamp(published, fetched)
    metadata = dict(raw or {})
    if reason:
        metadata["time_assumption"] = reason
    return dict(
        id=str(uuid5(NAMESPACE, url)),
        source_key=source,
        url=url,
        url_hash=sha256(url.encode()).hexdigest(),
        title=title,
        summary=plain(summary),
        published_at=published_at,
        published_at_assumed=assumed,
        fetched_at=fetched.isoformat(),
        language=language,
        title_hash=sha256(title_normalized(title).encode()).hexdigest(),
        external_id=external_id,
        raw=metadata,
        provenance={
            k: v
            for k, v in metadata.items()
            if k in ("exchange_symbol", "category", "origin_exchange", "time_assumption")
        },
    )


def same_story(a, b, threshold=0.92):
    from rapidfuzz.fuzz import ratio

    left, right = title_normalized(a["title"]), title_normalized(b["title"])
    if left == right:
        return True

    # Distinct amounts, dates, quarters, negations or opposite outcomes are not duplicates.
    def tokens(s):
        return set(
            re.findall(r"\d+(?:\.\d+)?|\b(?:q[1-4]|not|no|rise|falls|rises|fall|profit|loss|cuts|hikes)\b", s)
        )

    return tokens(left) == tokens(right) and ratio(left, right) / 100 >= threshold


def deduplicate(rows, config):
    ordered = sorted(rows, key=lambda r: (r["published_at"], r["fetched_at"], r["id"]))
    groups = []
    for row in ordered:
        dt = datetime.fromisoformat(row["published_at"])
        found = None
        for representative in reversed(groups):
            delta = (dt - datetime.fromisoformat(representative["published_at"])).total_seconds() / 3600
            if delta > config["window_hours"]:
                break
            if same_story(row, representative, config["title_similarity_threshold"]):
                found = representative
                break
        row["dedupe_group_id"] = found["id"] if found else row["id"]
        row["is_duplicate"] = found is not None
        if not found:
            groups.append(row)
    return ordered
