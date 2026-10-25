from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from contextlib import nullcontext
import sys
import pytest
from news.main import settings, collect
from news.pipeline import process
from news.tests.test_news import item, ALIASES, RULES
from news.events.classifier import classify
from news.linking.linker import link


class Client:
    def __init__(self):
        self.writes = []

    def table(self, name):
        self.table_name = name
        return self

    def update(self, value):
        self.value = value
        return self

    def eq(self, key, value):
        self.writes.append((self.table_name, self.value, key, value))
        return self


def test_linking_is_offline_idempotent_and_versioned(monkeypatch):
    import news.pipeline as p

    cfg, aliases, rules, feeds = settings()
    row = item()
    row.update(processing={}, is_duplicate=False, dedupe_group_id=None)
    state = {"articles": [row], "article_symbols": []}
    calls = []
    monkeypatch.setattr(p, "read", lambda c, t, *a, **k: deepcopy(state.get(t, [])))
    monkeypatch.setattr(p, "log_event", lambda *a, **k: None)

    class RPC:
        def rpc(self, name, args):
            return args

    def execute(args):
        calls.append(args)
        state["articles"][0]["processing"].update(args["p_processing"])
        state["article_symbols"] = args["p_links"]
        return []

    monkeypatch.setattr(p, "execute", execute)
    for _ in range(2):
        assert process(RPC(), cfg, aliases, rules, feeds, "offline", "link")["failed"] == 0
    assert len(calls) == 1 and calls[0]["p_events"] == []
    cfg["processing"]["linker_version"] = "2.0.0"
    process(RPC(), cfg, aliases, rules, feeds, "offline", "link")
    assert len(calls) == 2

def test_invalid_source_does_not_stop_others_and_circuit_breaks(monkeypatch):
    import news.main as main
    from news.collect import rss

    client = Client()
    logs = []
    sources = {
        k: dict(
            source_key=k,
            source_type="rss",
            enabled=True,
            consecutive_failures=4 if k == "broken" else 0,
            poll_interval_minutes=30,
            last_fetched_at=None,
        )
        for k in ["broken", "healthy"]
    }
    monkeypatch.setattr(main, "sources", lambda *a: sources)
    monkeypatch.setattr(main, "execute", lambda q: [])
    monkeypatch.setattr(main, "store_articles", lambda c, r: len(r))
    monkeypatch.setattr(main, "log_event", lambda *a, **k: logs.append((a, k)))

    def fetch(source, *a, **k):
        if source["source_key"] == "broken":
            raise ValueError("Invalid XML")
        return [item()], {}, False

    monkeypatch.setattr(rss, "fetch", fetch)
    args = SimpleNamespace(since=date(2026, 1, 1), symbols="TCS", source=None, command="fetch")
    result = collect(client, args, ALIASES, {"max_consecutive_failures_before_disable": 5}, "test")
    assert result == {"stored": 1, "failed": 1}
    assert any(w[1].get("enabled") is False for w in client.writes)
    assert any(a[2] == "disable_source" for a, k in logs)


def test_rss_fetch_never_calls_exchange_sources(monkeypatch):
    import news.main as main
    from news.collect import announcements, rss
    from unittest.mock import Mock
    monkeypatch.setattr(main,"sources",lambda *a: {
        "exchange":dict(source_type="exchange_api",enabled=True),
        "feed":dict(source_type="rss",enabled=True,source_key="feed",consecutive_failures=0)})
    monkeypatch.setattr(rss,"due",lambda *a:True)
    monkeypatch.setattr(rss,"fetch",lambda *a,**k:([],{},False))
    forbidden=Mock(side_effect=AssertionError("exchange called"))
    monkeypatch.setattr(announcements,"fetch",forbidden)
    monkeypatch.setattr(main,"execute",lambda *a:[])
    monkeypatch.setattr(main,"store_articles",lambda *a:0)
    monkeypatch.setattr(main,"log_event",lambda *a,**k:None)
    args=SimpleNamespace(since=date(2026,1,1),symbols="TCS",source=None,command="fetch")
    assert collect(Client(),args,ALIASES,{},"test")=={"stored":0,"failed":0}
    forbidden.assert_not_called()


def test_missing_model_records_failure_and_no_scores(monkeypatch):
    import news.pipeline as p
    import news.scoring.sentiment as sentiment

    cfg, aliases, rules, feeds = settings()
    row = item()
    row.update(is_duplicate=False, processing={})
    monkeypatch.setattr(p, "read", lambda client, table, *a, **k: [row] if table == "articles" else [])
    monkeypatch.setattr(sentiment, "english", lambda r: True)

    def unavailable(*a, **k):
        raise OSError("Cache missing in offline mode")

    monkeypatch.setattr(sentiment, "Sentiment", unavailable)
    writes = []
    logs = []
    monkeypatch.setattr(p, "upsert", lambda *a: writes.append(a))
    monkeypatch.setattr(p, "log_event", lambda *a, **k: logs.append((a, k)))
    result = process(Client(), cfg, aliases, rules, feeds, "test", "sentiment")
    assert result["failed"] == 1 and not writes
    assert any("download-models" in k.get("error", "") for a, k in logs)


def test_sentiment_truncates_batches_and_uses_config_label_order(monkeypatch):
    from news.scoring.sentiment import Sentiment

    captured = []
    scorer = object.__new__(Sentiment)
    scorer.config = {"batch_size": 2, "max_tokens": 10000}
    scorer.labels = {0: "neutral", 1: "positive", 2: "negative"}

    def tokenize(texts, **kwargs):
        captured.append((texts, kwargs))
        return {"n": len(texts)}

    scorer.tokenizer = tokenize
    scorer.model = lambda n: SimpleNamespace(logits=n)
    fake = SimpleNamespace(
        inference_mode=nullcontext,
        softmax=lambda n, dim: SimpleNamespace(
            cpu=lambda: SimpleNamespace(tolist=lambda: [[0.1, 0.8, 0.1]] * n)
        ),
    )
    monkeypatch.setitem(sys.modules, "torch", fake)
    result = scorer.score(["profits " * 3000, "", "profits"])
    assert len(result) == 3 and result[0]["label"] == "positive"
    assert [len(t) for t, k in captured] == [2, 1]
    assert all(k["truncation"] and k["max_length"] == 512 for t, k in captured)


@pytest.mark.parametrize(
    "event_type,definition", [(k, v) for k, v in RULES["event_types"].items() if k != "other"]
)
def test_every_event_rule_has_positive_and_negative_case(event_type, definition):
    cfg = deepcopy(RULES)
    cfg["event_types"] = {event_type: definition, "other": RULES["event_types"]["other"]}
    phrase = definition["patterns"][0]
    a = item(f"TCS discusses {phrase}")
    a["dedupe_group_id"] = a["id"]
    links = link(a, ALIASES, "1")
    if definition.get("scope") == "MARKET":
        links.append(dict(symbol="MARKET", confidence=0.9))
    result = classify(a, links, cfg, {"TCS": ["2026-10-23"], "MARKET": ["2026-10-23"]})
    assert event_type in {r["event_type"] for r in result}
    a["title"] = "TCS publishes its office directory"
    a["summary"] = ""
    assert event_type not in {r["event_type"] for r in classify(a, links, cfg, {"TCS": ["2026-10-23"]})}
