from datetime import date, datetime
from zoneinfo import ZoneInfo
import pandas as pd
from ingest.main import Pipeline, completed_date
from ingest.sources.base import SourceError


class Result:
    def __init__(self, data):
        self.data = data


class FakeDB:
    def __init__(self):
        self.rows = {}
        self.fail_write = False

    def table(self, name):
        return Query(self, name)


class Query:
    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.filters = {}
        self.payload = None
        self.desc = False
        self.maximum = None

    def select(self, *args):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, key, desc=False):
        self.desc = desc
        return self

    def limit(self, n):
        self.maximum = n
        return self

    def upsert(self, rows, **kwargs):
        self.payload = rows
        return self

    def execute(self):
        if self.payload is not None:
            if self.db.fail_write:
                raise RuntimeError("database unavailable")
            for r in self.payload:
                key = (r["symbol"], r["exchange"], r.get("timeframe"), r.get("ts"))
                self.db.rows[key] = r
            return Result(self.payload)
        rows = [r for r in self.db.rows.values() if all(r.get(k) == v for k, v in self.filters.items())]
        rows = sorted(rows, key=lambda r: r.get("ts", ""), reverse=self.desc)
        return Result(rows[: self.maximum] if self.maximum else rows)


def frame(close=102):
    return pd.DataFrame([dict(ts="2026-01-05", open=100, high=110, low=90, close=close, volume=100)])


def make(fetcher):
    events = []
    config = dict(
        source_priority=["jugaad", "openchart"],
        retries=2,
        source_timeout_seconds=1,
        retry_backoff_seconds=0,
        delay_between_symbols_seconds=0,
        default_lookback_days=30,
        crosscheck=dict(enabled=False, tolerance_percent=0.5),
    )
    pipeline = Pipeline(
        FakeDB(),
        config,
        fetcher=fetcher,
        logger=lambda *a, **kw: events.append((a, kw)),
        sleep=lambda _: None,
    )
    return pipeline, events


def test_fallback_and_incremental_idempotency():
    calls = []

    def fetch(name, *args):
        calls.append(name)
        if name == "jugaad":
            raise SourceError("primary down")
        return frame()

    pipeline, events = make(fetch)
    assert pipeline.run(["TCS"], date(2026, 1, 5))["success"] == 1
    assert calls == ["jugaad", "openchart"]
    assert pipeline.run(["TCS"], date(2026, 1, 5))["skipped"] == 1
    assert len(pipeline.client.rows) == 1
    assert len(calls) == 2
    assert any(a[2:4] == ("fetch_candles", "failed") for a, kw in events)


def test_invalid_symbol_does_not_stop_next_symbol():
    def fetch(name, symbol, *args):
        if symbol == "NOTASTOCK":
            raise SourceError("not found")
        return frame()

    pipeline, events = make(fetch)
    result = pipeline.run(["NOTASTOCK", "TCS"], date(2026, 1, 5))
    assert result["failed"] == 1 and result["success"] == 1
    assert events[-1][0][3] == "warning"


def test_blocking_disables_source_for_run():
    calls = []

    def fetch(name, *args):
        calls.append(name)
        if name == "jugaad":
            raise SourceError("429", blocked=True)
        return frame()

    pipeline, _ = make(fetch)
    pipeline.run(["TCS", "INFY"], date(2026, 1, 5))
    assert calls.count("jugaad") == 1
    assert calls.count("openchart") == 2


def test_network_failure_retries_without_garbage():
    calls = []

    def fetch(name, *args):
        calls.append(name)
        raise SourceError("network offline", transient=True)

    pipeline, events = make(fetch)
    assert pipeline.run(["TCS"], date(2026, 1, 5))["failed"] == 1
    assert len(calls) == 4
    assert not pipeline.client.rows
    assert any(a[3] == "retried" for a, kw in events)


def test_write_failure_is_not_success():
    pipeline, events = make(lambda *args: frame())
    pipeline.client.fail_write = True
    assert pipeline.run(["TCS"], date(2026, 1, 5))["failed"] == 1
    assert any(a[2:4] == ("write_candles", "failed") for a, kw in events)


def test_crosscheck_reports_both_values():
    pipeline, events = make(lambda name, *args: frame(102 if name == "jugaad" else 105))
    pipeline.config["crosscheck"]["enabled"] = True
    pipeline.run(["TCS"], date(2026, 1, 5))
    cross = [(a, kw) for a, kw in events if a[2] == "crosscheck"][0]
    assert cross[0][3] == "warning"
    assert cross[1]["meta"]["differences"][0]["secondary"] == 105


def test_adjustment_mismatch_does_not_mix_series():
    pipeline, events = make(lambda *args: frame())
    pipeline.client.rows[("TCS", "NSE", "1d", "old")] = dict(
        symbol="TCS",
        exchange="NSE",
        timeframe="1d",
        ts="2026-01-01T18:30:00Z",
        adjusted=True,
        source="yfinance",
    )
    assert pipeline.run(["TCS"], date(2026, 1, 5))["failed"] == 1
    assert any(a[2] == "adjustment_mismatch" for a, kw in events)


def test_current_session_waits_until_evening():
    tz = ZoneInfo("Asia/Kolkata")
    assert completed_date(datetime(2026, 1, 5, 12, tzinfo=tz)) == date(2026, 1, 2)
    assert completed_date(datetime(2026, 1, 5, 18, tzinfo=tz)) == date(2026, 1, 5)
