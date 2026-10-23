"""Read-only logbook CLI. Run from any directory after installing shared."""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import UUID

from shared.db import get_client
from shared.logbook import sanitize


def parse_since(value):
    match = re.fullmatch(r"(\d+)([hd])", value)
    if not match:
        raise argparse.ArgumentTypeError("Use a duration such as 24h or 7d")
    amount, unit = match.groups()
    return (
        datetime.now(timezone.utc) - timedelta(hours=int(amount) * (24 if unit == "d" else 1))
    ).isoformat()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read the research action logbook")
    commands = parser.add_subparsers(dest="command", required=True)
    tail = commands.add_parser("tail")
    tail.add_argument("--limit", type=int, default=50)
    tail.add_argument("--status", choices=["started", "success", "failed", "retried", "skipped", "warning"])
    tail.add_argument("--module")
    tail.add_argument("--symbol")
    run = commands.add_parser("run")
    run.add_argument("run_id", type=UUID)
    summary = commands.add_parser("summary")
    summary.add_argument("--since", type=parse_since, default="24h")
    args = parser.parse_args(argv)
    try:
        client = get_client()
        if args.command == "tail":
            if not 1 <= args.limit <= 1000:
                parser.error("--limit must be between 1 and 1000")
            query = client.table("agent_events").select("*")
            for field in ("status", "module", "symbol"):
                if value := getattr(args, field):
                    query = query.eq(field, value.upper() if field == "symbol" else value)
            rows = query.order("ts", desc=True).order("id", desc=True).limit(args.limit).execute().data
        else:
            rows = []
            offset = 0
            while True:
                query = client.table("agent_events").select("*")
                query = (
                    query.eq("run_id", str(args.run_id))
                    if args.command == "run"
                    else query.gte("ts", args.since)
                )
                page = query.order("ts").order("id").range(offset, offset + 499).execute().data
                rows.extend(page)
                if len(page) < 500:
                    break
                offset += 500
        if args.command == "summary":
            for (module, status), count in sorted(Counter((r["module"], r["status"]) for r in rows).items()):
                print(f"{module:18} {status:10} {count:6}")
        else:
            for row in rows:
                print(json.dumps(row, ensure_ascii=True))
        if not rows:
            print("No events found.")
        return 0
    except Exception as exc:
        print(f"Unable to read logbook: {sanitize(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
