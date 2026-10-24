from datetime import date, datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
import pytest
from ingest.hardening import propose_factor, year_rows


def action(kind, parsed):
    return dict(id=1, symbol="TEST", exchange="NSE", ex_date="2026-01-05", action_type=kind, parsed=parsed)


def test_bonus_split_and_invalid_ratios():
    assert Decimal(propose_factor(action("bonus", {"new_shares": 1, "existing_shares": 1}))["factor"]) == Decimal("0.5")
    assert Decimal(propose_factor(action("split", {"old_face_value": 10, "new_face_value": 2}))["factor"]) == Decimal("0.2")
    assert propose_factor(action("split", {"old_face_value": 0, "new_face_value": 2})) is None
    assert propose_factor(action("bonus", None)) is None
    assert propose_factor(action("dividend", {"amount": 10})) is None


def test_calendar_unknown_year_is_not_assumed_trading():
    with pytest.raises(ValueError, match="complete"):
        year_rows(2027, [], {})


def test_special_session_overrides_weekend_and_holiday_stays_closed():
    holidays = [date(2026, 1, d) for d in (1, 2, 5, 6, 7)]
    rows = {r["day"]: r for r in year_rows(2026, holidays, {"2026-01-04": {
        "is_trading_day": True, "note": "Special", "source": "https://example.test/official"}})}
    assert rows["2026-01-04"]["is_trading_day"]
    assert not rows["2026-01-05"]["is_trading_day"]


def test_completed_date_handles_holiday_and_special_sunday():
    from ingest.main import completed_date

    calendar = {date(2026, 11, 8): {"is_trading_day": True}, date(2026, 11, 9): {"is_trading_day": False}}
    assert completed_date(datetime(2026, 11, 9, 19, tzinfo=ZoneInfo("Asia/Kolkata")), calendar) == date(2026, 11, 8)
    with pytest.raises(ValueError, match="missing"):
        completed_date(datetime(2027, 1, 1, 19, tzinfo=ZoneInfo("Asia/Kolkata")), calendar)
