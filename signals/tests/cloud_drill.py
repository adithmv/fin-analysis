"""Explicit live repair drill; latest stored TCS signals are restored on failure."""

from pathlib import Path
import sys
from uuid import uuid4
import yaml
from shared.db import get_client

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from signals.main import run_symbol  # noqa: E402


def main():
    client = get_client()
    config = yaml.safe_load(Path("config/signals.yaml").read_text())
    latest = (
        client.table("candles")
        .select("ts")
        .eq("symbol", "TCS")
        .eq("exchange", "NSE")
        .eq("timeframe", "1d")
        .order("ts", desc=True)
        .limit(1)
        .execute()
        .data[0]["ts"]
    )

    def query():
        return (
            client.table("signals")
            .select("*")
            .eq("symbol", "TCS")
            .eq("exchange", "NSE")
            .eq("timeframe", "1d")
            .eq("ts", latest)
            .order("signal_key")
            .execute()
            .data
        )

    before = query()
    assert before
    try:
        client.table("signals").delete().eq("symbol", "TCS").eq("exchange", "NSE").eq("timeframe", "1d").eq(
            "ts", latest
        ).execute()
        result = run_symbol(client, "TCS", config, str(uuid4()), False, None)
        assert result == {"status": "success", "days": 1}

        def stable(rows):
            return [{k: v for k, v in row.items() if k != "computed_at"} for row in rows]

        assert stable(query()) == stable(before)
        repeat = run_symbol(client, "TCS", config, str(uuid4()), False, None)
        assert repeat == {"status": "skipped", "days": 0}
        print("Latest-day deletion repaired exactly; repeat skipped with zero writes.")
    except Exception:
        client.table("signals").upsert(
            before, on_conflict="symbol,exchange,ts,timeframe,signal_key"
        ).execute()
        raise


if __name__ == "__main__":
    main()
