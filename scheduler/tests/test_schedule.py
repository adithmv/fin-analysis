from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from scheduler.schedule import latest_due, field_values


def test_laptop_wake_catches_latest_occurrence_without_poll_storm():
    now = datetime(2026, 10, 23, 19, 12, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert latest_due("0 17 * * *", now, 2160).hour == 17
    due = latest_due("*/30 6-23 * * *", now, 30)
    assert (due.hour, due.minute) == (19, 0)
    assert latest_due("0 17 * * *", now, 60) is None


def test_weekday_mapping_and_weekly_catchup():
    sunday = datetime(2026, 10, 25, 3, 5, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert latest_due("0 3 * * 0", sunday, 60).date() == sunday.date()
    assert latest_due("0 17 * * 1-5", sunday, 60) is None


@pytest.mark.parametrize("cron", ["0 25 * * *", "*/0 * * * *", "0 1 2 * *", "0 1 * 2 *", "60 * * * *"])
def test_bad_schedules_fail_clearly(cron):
    with pytest.raises(ValueError):
        latest_due(cron, datetime.now(), 60)


def test_ranges_and_lists():
    assert field_values("1-3,5", 0, 6) == {1, 2, 3, 5}
