from datetime import datetime, timezone
from pathlib import Path
import yaml
import pytest
from news.normalize import article, clean_url, deduplicate, timestamp
from news.linking.linker import link
from news.events.classifier import effective_date, classify
from news.collect.corporate_actions import parse
from news.collect.rss import fetch, due

ROOT = Path(__file__).resolve().parents[2]
ALIASES = yaml.safe_load((ROOT / "config/aliases.yaml").read_text())
RULES = yaml.safe_load((ROOT / "config/news_events.yaml").read_text())


def item(
    title="TCS reports net profit", url="https://example.com/a", published="Fri, 23 Oct 2026 08:00:00 +0530"
):
    return article("test", url, title, "", published)


def test_timestamps_and_urls():
    assert timestamp("Fri, 23 Oct 2026 08:00:00 +0530")[0] == "2026-10-23T02:30:00+00:00"
    assert timestamp("2026-10-23T08:00:00")[2] == "timezone_missing_assumed_IST"
    assert timestamp("19-Oct-2026 11:30:08")[0] == "2026-10-19T06:00:08+00:00"
    assert timestamp(None, datetime(2026, 1, 1, tzinfo=timezone.utc))[1]
    assert clean_url("https://EXAMPLE.com/a/?utm_source=x&b=1#top") == "https://example.com/a?b=1"
    with pytest.raises(ValueError):
        clean_url("javascript:alert(1)")


def test_dedupe_preserves_different_numbers_and_earliest_publication():
    a = item()
    b = item(url="https://b.example/a", published="Fri, 23 Oct 2026 09:00:00 +0530")
    c = item("TCS reports net profit of Rs 300 crore", url="https://c.example/a")
    d = item("TCS reports net profit of Rs 400 crore", url="https://d.example/a")
    result = deduplicate([b, d, c, a], {"window_hours": 48, "title_similarity_threshold": 0.92})
    by_id = {r["id"]: r for r in result}
    assert by_id[b["id"]]["dedupe_group_id"] == a["id"]
    assert by_id[b["id"]]["is_duplicate"] and not by_id[a["id"]]["is_duplicate"]
    assert by_id[c["id"]]["dedupe_group_id"] != by_id[d["id"]]["dedupe_group_id"]


def test_linking_precision_and_macro():
    assert {r["symbol"] for r in link(item("Tata Consultancy Services wins a contract"), ALIASES, "1")} == {
        "TCS"
    }
    assert not link(item("Reliance on foreign oil is declining"), ALIASES, "1")
    assert not link(item("Reliance Power issues shares"), ALIASES, "1")
    assert {r["symbol"] for r in link(item("RBI cuts repo rate; HDFC Bank in focus"), ALIASES, "1")} == {
        "MARKET",
        "HDFCBANK",
    }
    assert not link(item("the tcs code is invalid"), ALIASES, "1")


def test_effective_sessions_no_lookahead():
    sessions = ["2026-10-23", "2026-10-26", "2026-10-28"]
    assert effective_date("2026-10-23T08:59:00+05:30", sessions) == "2026-10-23"
    for hour in ("09:15", "12:00", "17:00"):
        assert effective_date(f"2026-10-23T{hour}:00+05:30", sessions) == "2026-10-26"
    assert effective_date("2026-10-24T10:00:00+05:30", sessions) == "2026-10-26"
    assert effective_date("2026-10-27T10:00:00+05:30", sessions) == "2026-10-28"
    assert effective_date("2026-10-28T10:00:00+05:30", sessions) is None
    assert effective_date("2026-10-23T08:00:00+05:30", sessions, True) is None


def test_classifier_and_unclear_actions():
    a = item()
    a["dedupe_group_id"] = a["id"]
    result = classify(a, link(a, ALIASES, "1"), RULES, {"TCS": ["2026-10-23"]})
    assert result[0]["event_type"] == "earnings_result"
    assert parse("Bonus 1:1") == ("bonus", {"new_shares": 1, "existing_shares": 1}, "parsed")
    assert parse("Bonus ratio subject to approval")[2] == "needs_review"
    assert parse("Dividend - Rs 9 Per Share")[1] == {"amount_inr_per_share": 9.0}
    assert parse("Split proposed")[2] == "needs_review"


def test_conditional_feed_and_bad_xml():
    from types import SimpleNamespace

    source = {
        "source_key": "test",
        "url": "https://example.com/rss",
        "etag": "abc",
        "last_modified": None,
        "enabled": True,
        "poll_interval_minutes": 30,
    }
    seen = []

    def request(url, **kwargs):
        seen.append(kwargs)
        return SimpleNamespace(status_code=304)

    assert fetch(source, {"user_agent": "test", "timeout_seconds": 1}, request=request)[2]
    assert seen[0]["headers"]["If-None-Match"] == "abc"
    assert due(source)
    source["last_fetched_at"] = datetime.now(timezone.utc).isoformat()
    assert not due(source)
    response = SimpleNamespace(status_code=200, content=b"not xml", headers={}, raise_for_status=lambda: None)
    with pytest.raises(ValueError):
        fetch(source, {"user_agent": "test", "timeout_seconds": 1}, request=lambda *a, **kw: response)


def test_label_mapping_language_and_attachment_fallback():
    from news.scoring.sentiment import decode, english
    from news.collect.announcements import attachment_url

    assert decode([0.8, 0.15, 0.05], {0: "negative", 1: "neutral", 2: "positive"})["score"] == pytest.approx(
        -0.75
    )
    assert not english({"title": "१२३ हिंदी खबर", "language": "hi"})
    assert attachment_url("-", "https://example.com/announcement") == "https://example.com/announcement"
    assert len(item("TCS reports profit", "https://example.com/x")["summary"]) == 0


@pytest.mark.parametrize("status", [403, 429])
def test_feed_backoff(status):
    from types import SimpleNamespace
    import requests

    waits = []

    def fail():
        raise requests.HTTPError("limited")

    response = SimpleNamespace(status_code=status, headers={"Retry-After": "2"}, raise_for_status=fail)
    with pytest.raises(requests.HTTPError):
        fetch(
            {"url": "https://example.com/feed"},
            {"user_agent": "test", "timeout_seconds": 1},
            request=lambda *a, **k: response,
            sleep=waits.append,
        )
    assert waits == [2, 2]
