"""Explicit, repeatable live source and database drills; no market orders."""

import sys
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingest.main import Pipeline, completed_date
from ingest.sources.base import SourceError
from ingest.sources.runner import fetch_bounded
from shared.db import get_client


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "config/ingest.yaml").read_text())
    config["crosscheck"]["enabled"] = False
    config["source_priority"] = ["jugaad", "yfinance"]
    config["default_lookback_days"] = 14

    def fail_primary(name, *args):
        if name == "jugaad":
            raise SourceError("Intentional primary-source failure drill")
        return fetch_bounded(name, *args)

    pipeline = Pipeline(get_client(), config, fetcher=fail_primary)
    totals = pipeline.run(["SBIN"], completed_date(), days=14)
    print("Live fallback drill:", pipeline.run_id, totals)
    assert totals["success"] == 1

    # Simulate a network outage after the first real source fetch. This avoids
    # disabling networking for the user's other applications.
    outage_config = dict(config, retries=2, retry_backoff_seconds=0)
    outage_config["source_priority"] = ["jugaad", "yfinance"]
    state = {"fetched": False}

    def disconnect_after_fetch(name, *args):
        if state["fetched"]:
            raise SourceError("Simulated network disconnection mid-run", transient=True)
        result = fetch_bounded(name, *args)
        state["fetched"] = True
        return result

    outage = Pipeline(get_client(), outage_config, fetcher=disconnect_after_fetch)
    totals = outage.run(["TCS", "INFY"], completed_date(), days=7)
    print("Mid-run network drill:", outage.run_id, totals)
    assert totals["success"] == 1 and totals["failed"] == 1
