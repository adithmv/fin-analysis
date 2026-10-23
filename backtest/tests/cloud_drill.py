"""Explicit cloud reproducibility check; produces two reviewable saved runs."""

from argparse import Namespace
from pathlib import Path
import sys
from shared.db import get_client

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backtest.main import execute  # noqa: E402


def main():
    args = Namespace(
        config=Path("config/backtest.yaml"), symbols="TCS", mode="strategy", strategy="sma_cross"
    )
    first, second = execute(args), execute(args)
    client = get_client()
    configs = [
        client.table("backtest_runs").select("config,code_version").eq("id", run).single().execute().data
        for run in (first, second)
    ]
    assert configs[0] == configs[1]
    results = [
        client.table("backtest_results").select("*").eq("run_id", run).order("sample").execute().data
        for run in (first, second)
    ]

    def stable(rows):
        return [{k: v for k, v in row.items() if k not in ("run_id", "id")} for row in rows]

    assert stable(results[0]) == stable(results[1])
    trades = [
        client.table("backtest_trades")
        .select("*")
        .eq("run_id", run)
        .order("sample")
        .order("entry_ts")
        .execute()
        .data
        for run in (first, second)
    ]
    assert stable(trades[0]) == stable(trades[1])
    print("Identical configs, code versions, metrics, equity curves and trades across repeated cloud runs.")


if __name__ == "__main__":
    main()
