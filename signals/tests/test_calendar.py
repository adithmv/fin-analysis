from datetime import date
import pandas as pd
from signals.quality import compute


def test_holiday_is_not_missing_and_unknown_is_visible():
    frame = pd.DataFrame({"ts": pd.to_datetime(["2026-10-19T18:30:00Z", "2026-10-21T18:30:00Z"]),
                          "close": [100, 101], "volume": [100, 100]})
    config = {"indicators": {"sma": [1]}, "quality": {"split_jump_threshold_percent": 20,
              "max_missing_weekdays_in_row": 0, "zero_volume_streak_days": 3}}
    frame.attrs["calendar"] = {date(2026, 10, 21): False}
    assert not compute(frame, config)
    frame.attrs["calendar"] = {date(2026, 10, 21): True}
    assert compute(frame, config)[0]["signal_key"] == "gap_in_data"
    frame.attrs["calendar"] = {}
    assert compute(frame, config)[0]["signal_key"] == "calendar_unknown"
