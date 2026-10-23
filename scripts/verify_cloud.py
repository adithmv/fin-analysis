"""Non-destructive cloud checks: reads, an audit event, and rejected public writes."""

from pathlib import Path
from uuid import uuid4
import sys

from dotenv import dotenv_values
from supabase import create_client
from shared.db import get_client
from shared.logbook import log_event, sanitize


def main():
    env = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
    private = get_client()
    public = create_client(env["SUPABASE_URL"], env["NEXT_PUBLIC_SUPABASE_ANON_KEY"])
    for table in ("watchlist", "candles", "agent_events"):
        result = public.table(table).select("*").limit(1).execute()
        print(f"Public read {table}: OK ({len(result.data)} sample rows)")
    marker = "VERIFY_" + uuid4().hex[:12].upper()
    try:
        public.table("watchlist").insert({"symbol": marker, "exchange": "NSE"}).execute()
    except Exception:
        print("Public insert: correctly denied")
    else:
        raise RuntimeError("Public insert was unexpectedly allowed; review RLS immediately")
    run = uuid4()
    assert log_event(
        run,
        "setup",
        "cloud_verification",
        "success",
        output_summary="Public reads work; browser writes denied",
    )
    found = private.table("agent_events").select("id").eq("run_id", str(run)).execute().data
    assert len(found) == 1
    print("Python action log persisted: OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(sanitize(exc), file=sys.stderr)
        raise SystemExit(1)
