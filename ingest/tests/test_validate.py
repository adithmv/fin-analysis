from datetime import date
import pandas as pd
import pytest
from ingest.validate import validate, session_timestamp
from ingest.sources.base import SourceError


def sample():
    return pd.DataFrame([dict(ts="2026-01-05", open=100, high=110, low=90, close=105, volume=100)])


@pytest.mark.parametrize(
    "column,value",
    [("high", 99), ("low", 106), ("open", 0), ("close", None), ("close", float("inf")), ("ts", "bad")],
)
def test_invalid_row_rejected(column, value):
    frame = sample()
    frame[column] = value
    with pytest.raises(SourceError):
        validate(frame, date(2026, 1, 5), date(2026, 1, 5))


def test_duplicate_and_nullable_volume():
    frame = pd.concat([sample(), sample()], ignore_index=True)
    frame["volume"] = None
    result = validate(frame, date(2026, 1, 5), date(2026, 1, 5))
    assert len(result.frame) == 1
    assert len(result.warnings) == 2
    assert pd.isna(result.frame.iloc[0].volume)


def test_jump_and_missing_weekday():
    frame = pd.concat([sample(), sample()], ignore_index=True)
    frame.loc[1, ["ts", "open", "high", "low", "close"]] = ["2026-01-07", 200, 210, 190, 205]
    result = validate(frame, date(2026, 1, 5), date(2026, 1, 7))
    assert any("weekdays" in w for w in result.warnings)
    assert any("20%" in w for w in result.warnings)


def test_timezone_and_out_of_range():
    assert session_timestamp("2026-01-05").isoformat() == "2026-01-04T18:30:00+00:00"
    assert session_timestamp("2026-01-04T18:30:00Z") == session_timestamp("2026-01-05")
    with pytest.raises(SourceError):
        validate(sample(), date(2026, 1, 6), date(2026, 1, 7))


@pytest.mark.parametrize("volume", [-1, 1.5, float("inf")])
def test_bad_volume_is_cleared(volume):
    frame = sample()
    frame["volume"] = volume
    result = validate(frame, date(2026, 1, 5), date(2026, 1, 5))
    assert pd.isna(result.frame.iloc[0].volume)


def test_empty_rejected():
    with pytest.raises(SourceError):
        validate(pd.DataFrame(), date(2026, 1, 5), date(2026, 1, 5))
