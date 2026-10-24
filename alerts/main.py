"""Run health checks, save actionable incidents and send bounded Telegram batches."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from uuid import uuid4
from zoneinfo import ZoneInfo
import yaml
from shared.db import get_client
from shared.logbook import log_event

if __package__:
    from . import checks
    from .notifiers.telegram import send
else:
    import checks
    from notifiers.telegram import send

ROOT=Path(__file__).resolve().parents[1]


def quiet(now, hours):
    hour=now.astimezone(ZoneInfo("Asia/Kolkata")).hour
    start,end=hours
    return hour>=start or hour<end if start>end else start<=hour<end


def notify(client, config, run_id, now):
    if not config["notifications_enabled"]:
        return {"sent": 0, "reason": "Telegram not enabled; incidents remain visible in dashboard"}
    pending=client.table("alerts").select("*").is_("notified_at","null").eq("status","open").order("id").limit(100).execute().data
    pending=[r for r in pending if r["severity"]=="critical" or (r["severity"]=="warning" and not quiet(now,config["quiet_hours_ist"]))]
    resolved=client.table("alerts").select("*").eq("status","resolved").contains("meta",{"resolution_pending":True}).limit(20).execute().data
    chosen=(pending+resolved)[:8]
    if not chosen or not client.rpc("reserve_notification",{"p_key":"alerts","p_min_seconds":config["minimum_notification_seconds"]}).execute().data:
        return {"sent":0}
    message="Market research alerts\n\n"+"\n\n".join(
        f"{'RESOLVED' if r['status']=='resolved' else r['severity'].upper()} · {r['rule_key']} / {r['subject']}\n{r['message']}" for r in chosen)
    try:
        send(message)
        for row in chosen:
            client.table("alerts").update({"notified_at":now.isoformat(),"meta":dict(row["meta"],resolution_pending=False)}).eq("id",row["id"]).execute()
        log_event(run_id,"alerts","send_notification","success",output_summary=f"Sent one batch of {len(chosen)} incidents")
        return {"sent":len(chosen)}
    except Exception:
        log_event(run_id,"alerts","send_notification","failed",error="Telegram delivery failed; dashboard retains incidents")
        return {"sent":0,"failed":True}


def check(client, config, llm, now=None):
    now=now or datetime.now(timezone.utc)
    run_id=str(uuid4())
    results=[]
    failures=[]
    for group in (checks.freshness,checks.sources,checks.infrastructure,checks.research):
        try:
            rows=group(client,config,now,llm) if group is checks.research else group(client,config,now)
            for row in rows:
                client.rpc("record_health",row).execute()
            results.extend(rows)
        except Exception as exc:
            failures.append(group.__name__)
            log_event(run_id,"alerts","run_check","failed",error=type(exc).__name__,output_summary=group.__name__)
    delivery=notify(client,config,run_id,now)
    summary={"checks":len(results),"violations":sum(r["p_status"]!="ok" for r in results),"failed_groups":failures,**delivery}
    log_event(run_id,"alerts","run_check","warning" if failures else "success",meta=summary)
    return summary


def digest(client,config,llm):
    now=datetime.now(timezone.utc)
    day=now.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()
    jobs=client.table("jobs").select("module,status").gte("created_at",day+"T00:00:00+05:30").limit(1000).execute().data
    threads=client.table("threads").select("symbol,status").eq("thread_date",day).limit(100).execute().data
    reports=client.table("analysis_reports").select("symbol,stance,evidence_strength").eq("as_of_date",day).limit(100).execute().data
    incidents=client.table("alerts").select("severity,rule_key,subject").neq("status","resolved").limit(100).execute().data
    budget=checks.research(client,config,now,llm)[0]
    tally={state:sum(r["status"]==state for r in jobs) for state in ("succeeded","skipped","dead","queued","running")}
    text=f"Market research · {day}\nJobs: "+", ".join(f"{n} {state}" for state,n in tally.items())
    text+=f"\nDiscussions: {len(threads)} · Open alerts: {len(incidents)}\n"+budget["p_message"].split(". ")[0]
    text+="\n"+"\n".join(f"{r['symbol']}: {r['stance']} ({r['evidence_strength']} evidence)" for r in reports[:6])
    text+="\n"+"\n".join(f"{r['severity']}: {r['rule_key']} / {r['subject']}" for r in incidents[:5])
    if config["notifications_enabled"]:
        already=client.table("health_checks").select("id").eq("check_key","digest_sent").eq("subject",day).limit(1).execute().data
        if already:
            return {"status":"skipped","reason":"Daily digest already sent"}
        if not client.rpc("reserve_notification",{"p_key":"digest:"+day,"p_min_seconds":config["minimum_notification_seconds"]}).execute().data:
            raise RuntimeError("Notification interval reserved; retry digest later")
        send(text)
        client.table("health_checks").insert({"check_key":"digest_sent","subject":day,"status":"ok"}).execute()
    log_event(str(uuid4()),"alerts","send_digest","success" if config["notifications_enabled"] else "skipped",output_summary=text[:300])
    return {"status":"sent" if config["notifications_enabled"] else "preview","text":text}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["check","digest","test-notify"])
    args=parser.parse_args(argv)
    client=get_client() # Loads the ignored root .env before notifier access.
    config=yaml.safe_load((ROOT/"config/alerts.yaml").read_text())
    llm=yaml.safe_load((ROOT/"config/llm.yaml").read_text())
    try:
        if args.command=="test-notify":
            send("Market research: Telegram alert connection test.")
            result={"status":"sent"}
        else:
            result=check(client,config,llm) if args.command=="check" else digest(client,config,llm)
        print(json.dumps(result))
        return int(bool(result.get("failed_groups") or result.get("failed")))
    except Exception as exc:
        print(f"Alert operation failed ({type(exc).__name__}); inspect local settings and connectivity",file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
