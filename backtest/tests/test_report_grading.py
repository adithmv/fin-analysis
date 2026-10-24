from datetime import datetime, timezone, date
import pytest
from backtest.report_grading import grade


def candle(day, opening=100, close=110):
    return {"ts": f"2026-10-{day:02}T00:00:00+05:30", "open": opening, "close": close}


REPORT = {"id": "report", "created_at": "2026-10-21T17:00:00+05:30", "stance": "bullish"}
THREAD = {"data_cutoff_ts": "2026-10-20T17:00:00+05:30", "config": {}}
NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)


def test_live_entry_cannot_precede_report_creation():
    prices = [candle(d) for d in (21, 22, 23)]
    result = grade(REPORT, THREAD, prices, prices, 1, now=NOW)
    assert result["entry_date"] == result["exit_date"] == "2026-10-22"
    assert result["excess_return"] == 0 and result["directional_hit"] is False


def test_replay_uses_historical_cutoff_and_exact_benchmark():
    prices = [candle(d) for d in (21, 22, 23)]
    benchmark = [candle(d, close=105) for d in (21, 22, 23)]
    result = grade(REPORT, {**THREAD, "config": {"replay": True}}, prices, benchmark, 3, now=NOW)
    assert result["entry_date"] == "2026-10-21" and result["exit_date"] == "2026-10-23"
    assert result["excess_return"] == pytest.approx(0.05) and result["directional_hit"]


def test_immature_missing_index_and_flagged_windows_remain_pending():
    prices = [candle(d) for d in (21, 22, 23)]
    assert grade(REPORT, THREAD, prices, prices, 3, now=NOW) is None
    assert grade(REPORT, THREAD, prices, [prices[0]], 1, now=NOW) is None
    assert grade(REPORT, THREAD, prices, prices, 1, [date(2026, 10, 22)], now=NOW) is None
    assert (
        grade(REPORT, THREAD, prices, prices, 1, now=datetime(2026, 10, 22, 4, tzinfo=timezone.utc)) is None
    )


def test_neutral_has_no_directional_score_and_missing_stock_session_rejected():
    prices = [candle(d) for d in (21, 22, 23, 26)]
    assert (
        grade({**REPORT, "stance": "neutral"}, THREAD, prices, prices, 1, now=NOW)["directional_hit"] is None
    )
    assert grade(REPORT, THREAD, [prices[0], prices[1], prices[3]], prices, 3, now=NOW) is None
