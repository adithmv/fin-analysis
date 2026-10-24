"""Schedule and execute bounded jobs without importing another module."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from uuid import uuid4
import yaml
from shared.db import get_client
from job_queue import Queue
from runner import execute, command_for
from schedule import tick

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "runner"):
        sub.add_parser(command).add_argument("--once", action="store_true")
    sub.add_parser("status")
    for command in ("cancel", "retry"):
        sub.add_parser(command).add_argument("--id", type=int, required=True)
    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("--module", required=True)
    enqueue.add_argument("--kind", required=True)
    enqueue.add_argument("--key", required=True)
    args = parser.parse_args(argv)
    client, worker = get_client(), str(uuid4())
    queue = Queue(client)
    modules = yaml.safe_load((ROOT / "config/modules.yaml").read_text())
    config = yaml.safe_load((ROOT / "config/schedule.yaml").read_text())
    if args.command == "status":
        print(json.dumps(client.table("jobs").select("id,module,kind,status,attempts,scheduled_for,last_error").order("id", desc=True).limit(30).execute().data, indent=2))
        return 0
    if args.command in ("retry", "cancel"):
        print(json.dumps({"changed": queue.control(args.id, args.command)}))
        return 0
    if args.command == "enqueue":
        job = {"name": "manual", "module": args.module, "kind": args.kind}
        command_for(job, modules)
        print(json.dumps(queue.enqueue(args.key, datetime.now(timezone.utc), [job])))
        return 0
    while True:
        try:
            if args.command == "run":
                print(json.dumps(tick(client, queue, config)), flush=True)
            else:
                job = queue.claim(worker)
                if job:
                    execute(job, worker, queue, modules)
            if args.once:
                return 0
            time.sleep(60 if args.command == "run" else 5)
        except KeyboardInterrupt:
            return 0
        except Exception as exc:
            print(f"Scheduler cycle failed ({type(exc).__name__}); retrying in 30 seconds", file=sys.stderr, flush=True)
            if args.once:
                return 1
            time.sleep(30)


if __name__ == "__main__":
    raise SystemExit(main())
