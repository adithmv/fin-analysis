"""Opt-in live queue drill. Refuses an active queue; removes only its own fixtures."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4
from shared.db import get_client


def main():
    client = get_client()
    if client.table("jobs").select("id").in_("status", ["queued", "running"]).limit(1).execute().data:
        raise RuntimeError("Stop scheduling and drain the queue before this isolated drill")
    key = "concurrency-drill:" + str(uuid4())
    stages = [{"name": f"stage-{n}", "module": f"fixture-{n}", "kind": "test"} for n in range(12)]
    try:
        def enqueue(_):
            return client.rpc("enqueue_pipeline", {"p_key": key, "p_at": datetime.now(timezone.utc).isoformat(),
                "p_stages": stages}).execute().data
        with ThreadPoolExecutor(max_workers=2) as pool:
            copies = list(pool.map(enqueue, range(2)))
        assert {r["id"] for r in copies[0]} == {r["id"] for r in copies[1]}
        assert len(copies[0]) == 12

        def claim(n):
            return client.rpc("claim_job", {"p_worker": f"drill-{n}"}).execute().data
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = [r for rows in pool.map(claim, range(24)) for r in rows]
        assert len(claims) == 12 and len({r["id"] for r in claims}) == 12
        assert all(r["pipeline_run"] == key and r["attempts"] == 1 for r in claims)
        print("Passed: two schedulers inserted one pipeline; two workers claimed 12 jobs exactly once.")
    finally:
        client.table("jobs").delete().eq("pipeline_run", key).execute()


if __name__ == "__main__":
    main()
