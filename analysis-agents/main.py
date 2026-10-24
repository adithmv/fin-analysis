"""Manual evidence-only research agents. No agent tools can execute or fetch external data."""

import argparse
from datetime import datetime, time, timezone
import json
import sys
import time as clock
from uuid import uuid4
from zoneinfo import ZoneInfo
from filelock import FileLock, Timeout
from shared.db import get_client
from shared.logbook import log_event, sanitize
from settings import settings, ROOT
from orchestrator import run, answer


def provider(config):
    if config["llm"]["provider"] == "gemini":
        from llm.gemini import Gemini

        return Gemini()
    if config["llm"]["provider"] == "ollama":
        from llm.ollama import Ollama

        return Ollama()
    raise ValueError("Unsupported provider")


def recover(client, node):
    journal = ROOT / ".cache" / "active-analysis-request"
    if journal.exists():
        client.table("analysis_requests").update(
            {
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error": "Local worker interrupted; partial messages retained. Submit a new request to retry.",
            }
        ).eq("id", int(journal.read_text())).eq("status", "running").execute()
        journal.unlink()
    for r in (
        client.table("threads")
        .select("id,run_id")
        .eq("status", "running")
        .contains("config", {"worker_id": node})
        .execute()
        .data
    ):
        client.table("threads").update(
            {
                "status": "failed",
                "failure_reason": "Local process interrupted; partial transcript retained",
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", r["id"]).execute()
        log_event(
            r["run_id"],
            "analysis-agents",
            "recover_interrupted",
            "failed",
            output_summary="Previous local process stopped; no messages replayed",
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    cmd = subs.add_parser("run")
    group = cmd.add_mutually_exclusive_group(required=True)
    group.add_argument("--symbol")
    group.add_argument("--all", action="store_true")
    cmd.add_argument("--force", action="store_true")
    cmd.add_argument("--as-of", type=lambda s: datetime.fromisoformat(s).date())
    cmd.add_argument("--on-demand", action="store_true")
    subs.add_parser("usage")
    cmd = subs.add_parser("serve")
    cmd.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    cfg = settings()
    client = get_client()
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    nodefile = cache / "agent-worker-id"
    if not nodefile.exists():
        nodefile.write_text(str(uuid4()))
    cfg["worker_id"] = nodefile.read_text().strip()
    try:
        if args.command == "usage":
            day = datetime.now(ZoneInfo(cfg["llm"]["limits"]["budget_timezone"])).date().isoformat()
            rows = (
                client.table("agent_call_reservations")
                .select("role,status,tokens_in,tokens_out,thread_id")
                .eq("budget_day", day)
                .execute()
                .data
            )
            print(
                json.dumps(
                    {
                        "budget_day": day,
                        "timezone": cfg["llm"]["limits"]["budget_timezone"],
                        "calls": len(rows),
                        "limit": cfg["llm"]["limits"]["max_calls_per_day"],
                        "tokens_in": sum(r["tokens_in"] or 0 for r in rows),
                        "tokens_out": sum(r["tokens_out"] or 0 for r in rows),
                    }
                )
            )
            return 0
        with FileLock(str(cache / "agent-worker.lock"), timeout=0):
            recover(client, cfg["worker_id"])
            model = provider(cfg)
            if args.command == "run":
                symbols = (
                    [args.symbol.upper()]
                    if args.symbol
                    else [
                        r["symbol"]
                        for r in client.table("watchlist")
                        .select("symbol")
                        .eq("active", True)
                        .eq("kind", "equity")
                        .execute()
                        .data
                    ]
                )
                available = {
                    r["symbol"]
                    for r in client.table("watchlist")
                    .select("symbol")
                    .eq("active", True)
                    .eq("kind", "equity")
                    .execute()
                    .data
                }
                if any(s not in available for s in symbols):
                    raise ValueError("Select an active watchlist equity")
                cutoff = (
                    datetime.combine(args.as_of, time(23, 59, 59), ZoneInfo("Asia/Kolkata")).isoformat()
                    if args.as_of
                    else None
                )
                results = [run(client, model, cfg, s, args.force, cutoff, args.on_demand) for s in symbols]
                print(json.dumps(results))
                return int(any(r["status"] in ("failed", "budget_exhausted") for r in results))
            while True:
                requests = client.rpc("claim_analysis_request").execute().data
                for request in requests:
                    journal = cache / "active-analysis-request"
                    journal.write_text(str(request["id"]))
                    try:
                        if request["kind"] == "question":
                            status = answer(client, model, cfg, request)
                        else:
                            result = run(client, model, cfg, request["symbol"], force=True, on_demand=True)
                            status = "done" if result["status"] == "completed" else "failed"
                        error = None
                    except Exception as exc:
                        status = "failed"
                        error = str(sanitize(exc))[:500]
                    client.table("analysis_requests").update(
                        {
                            "status": status,
                            "finished_at": datetime.now(timezone.utc).isoformat(),
                            "error": error,
                        }
                    ).eq("id", request["id"]).execute()
                    journal.unlink(missing_ok=True)
                if args.once:
                    return 0
                clock.sleep(5)
    except Timeout:
        print(
            "Another local agent worker is active; use dashboard requests or stop that worker first.",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(str(sanitize(exc)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
