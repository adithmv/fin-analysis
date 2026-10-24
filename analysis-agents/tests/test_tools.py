from types import SimpleNamespace
import pytest
from tools import ResearchTools
from data.asof_db import FutureData
from test_verification import pack


def test_frozen_tools_bounds_cutoff_copy_and_trace(monkeypatch):
    monkeypatch.setattr("tools.log_event", lambda *a, **k: 123)
    p = pack()
    tools = ResearchTools(p, "run", max_calls=2)
    rows = tools.get_indicators("TCS", ["rsi_14"])
    rows[0]["row"]["value"] = -999
    assert p["items"][0]["row"]["value"] == 71.3 and tools.event_ids == [123]
    p["items"][0]["row"]["computed_at"] = "2027-01-01T00:00:00Z"
    with pytest.raises(FutureData):
        tools.get_indicators("TCS")
    with pytest.raises(ValueError, match="call limit"):
        tools.get_data_quality("TCS")


def test_semantic_results_cannot_add_rows_outside_frozen_pack(monkeypatch):
    monkeypatch.setattr("tools.log_event", lambda *a, **k: 123)
    fake = SimpleNamespace(
        get=lambda *a, **k: SimpleNamespace(
            raise_for_status=lambda: None, json=lambda: [{"article_id": "future"}]
        )
    )
    result = ResearchTools(pack(), "run", search_client=fake).search_similar_news("results", "TCS")
    assert not result["items"] and "Anecdotal" in result["label"]


def test_tool_scope_cannot_read_other_stocks(monkeypatch):
    monkeypatch.setattr("tools.log_event", lambda *a, **k: 123)
    with pytest.raises(ValueError, match="scope"):
        ResearchTools(pack(), "run").get_candles("OTHER")
