from copy import deepcopy
import pytest
from gating import decide
from test_verification import pack, CONFIG


@pytest.mark.parametrize(
    "section,row,expected",
    [
        ("signals", {"signal_type": "pattern", "ts": "2026-10-23T12:00:00Z"}, True),
        ("signals", {"signal_type": "pattern", "ts": "2026-10-22T12:00:00Z"}, False),
        ("events", {"importance": 3, "published_at": "2026-10-23T12:00:00Z"}, True),
        ("events", {"importance": 2, "published_at": "2026-10-23T12:00:00Z"}, False),
        ("actions", {"ex_date": "2026-10-26"}, True),
        ("actions", {"ex_date": "2026-11-26"}, False),
    ],
)
def test_each_material_change_and_quiet_case(section, row, expected):
    p = pack()
    p["items"].extend(
        [
            {"section": "previous_report", "row": {"created_at": "2026-10-23T00:00:00Z"}},
            {"section": section, "row": row},
        ]
    )
    assert decide(p, CONFIG["agents"])[0] is expected


def test_atr_threshold_and_scheduled_review():
    p = pack()
    p["items"].extend(
        [
            {"section": "previous_report", "row": {"created_at": "2026-10-23T00:00:00Z"}},
            {"section": "indicators", "row": {"series_key": "atr_14", "value": 10}},
            {"section": "prices", "row": {"close": 100}},
            {"section": "prices", "row": {"close": 114}},
        ]
    )
    assert not decide(p, CONFIG["agents"])[0]
    p["items"][-1]["row"]["close"] = 115
    assert decide(p, CONFIG["agents"])[0]
    p = pack()
    p["items"].append({"section": "previous_report", "row": {"created_at": "2026-10-15T00:00:00Z"}})
    assert decide(p, deepcopy(CONFIG["agents"]))[0]
