"""Bounded independent checks; an unavailable check never resolves its old alert."""

from datetime import datetime, timedelta
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo


def stamp(value):
    return datetime.fromisoformat(value) if value else None


def result(rule, subject, status, message, value=None, severity="warning", detail=None):
    return dict(p_rule=rule,p_subject=subject,p_status=status,p_value=value,p_detail=detail or {},
                p_severity=severity,p_message=message)


def freshness(client, config, now):
    local = now.astimezone(ZoneInfo("Asia/Kolkata"))
    end = local.date() if local.hour >= 19 else local.date()-timedelta(days=1)
    days = client.table("trading_calendar").select("day,is_trading_day").eq("exchange", "NSE").gte("day", str(end-timedelta(days=14))).lte("day", str(end)).order("day",desc=True).execute().data
    if not days or days[0]["day"] != str(end):
        return [result("calendar_missing", "NSE", "fail", "Exchange calendar is missing. Refresh ingest calendar before running daily work.",severity="critical")]
    sessions = [r["day"] for r in days if r["is_trading_day"]]
    if not sessions:
        raise ValueError("No recent sessions")
    checks = [result("calendar_missing", "NSE", "ok", "Calendar is available")]
    watch = (
        client.table("watchlist")
        .select("symbol")
        .eq("active", True)
        .eq("exchange", "NSE")
        .eq("kind", "equity")
        .execute()
        .data
    )
    for row in watch:
        symbol = row["symbol"]
        candles = client.table("candles").select("ts,volume").eq("symbol",symbol).eq("exchange","NSE").eq("timeframe","1d").order("ts",desc=True).limit(15).execute().data
        latest = stamp(candles[0]["ts"]).astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat() if candles else ""
        stale = sum(day>latest for day in sessions)
        if config.get("price_ingestion_expected", True):
            status = "fail" if stale >= 2 else "warn" if stale else "ok"
            severity = "critical" if stale >= 2 else "warning"
            message = f"{symbol}: {stale} expected sessions missing at the end. Check ingest jobs, source status and calendar."
            detail = None
        else:
            status = "warn" if stale else "ok"
            severity = "warning"
            message = (f"{symbol}: {stale} expected sessions missing; market-price collection is paused. "
                       "Treat the stored close as stale until an approved source is commissioned.")
            detail = {"monitoring": "paused"} if stale else None
        checks.append(result("ingest_stale",symbol,status,message,stale,severity,detail))
        zero = 0
        for candle in candles:
            if candle["volume"] != 0:
                break
            zero += 1
        checks.append(result("zero_volume",symbol,"warn" if zero>=3 else "ok",f"{symbol}: {zero} consecutive zero-volume sessions. Inspect source and raw candles.",zero))
        signals = client.table("signals").select("ts").eq("symbol",symbol).eq("exchange","NSE").eq("signal_key","trend_state").order("ts",desc=True).limit(1).execute().data
        behind = bool(candles and (not signals or stamp(signals[0]["ts"])<stamp(candles[0]["ts"])))
        checks.append(result("signals_stale",symbol,"warn" if behind else "ok",f"{symbol}: check signal jobs after latest ingestion.",int(behind)))
    return checks


def sources(client, config, now):
    rows = client.table("news_sources").select("source_key,enabled,consecutive_failures,last_success_at,source_type").execute().data
    checks=[]
    for row in rows:
        if not row["enabled"]:
            checks.append(result("feed_dead",row["source_key"],"ok",
                "Source deliberately disabled; availability monitoring is paused.",detail={"monitoring":"disabled"}))
            continue
        stale = not row["last_success_at"] or now-stamp(row["last_success_at"])>timedelta(hours=24)
        bad = not row["enabled"] or row["consecutive_failures"]>=config["feed_failure_threshold"] or stale
        checks.append(result("feed_dead",row["source_key"],"warn" if bad else "ok",
            "Source is disabled, stale or repeatedly failing. Check source health, terms and recent fetch errors.",row["consecutive_failures"]))
    return checks


def infrastructure(client, config, now):
    rows=client.table("jobs").select("id,module").eq("status","dead").limit(100).execute().data
    checks=[result("pipeline_job_dead","queue","fail" if rows else "ok",
        f"{len(rows)} dead jobs. Inspect job errors, repair the cause, then retry.",len(rows),"critical",{"job_ids":[r["id"] for r in rows]})]
    heartbeat=client.table("health_checks").select("ts").eq("check_key","scheduler_heartbeat").order("ts",desc=True).limit(1).execute().data
    age=(now-stamp(heartbeat[0]["ts"])).total_seconds()/60 if heartbeat else 1e6
    expected=config.get("scheduler_expected",True)
    checks.append(result("scheduler_silent","local","fail" if expected and age>config["scheduler_silent_minutes"] else "ok",
        "Scheduler heartbeat missing or late. Check laptop power, scheduler process and database access." if expected else
        "All pipeline schedules are disabled; scheduler heartbeat monitoring is paused.",round(age),"critical",
        {"monitoring":"enabled" if expected else "disabled"}))
    size=client.rpc("database_size_bytes").execute().data
    fraction=size/config["database_limit_bytes"]
    checks.append(result("db_size","supabase","fail" if fraction>=config["database_critical_fraction"] else "warn" if fraction>=config["database_warning_fraction"] else "ok",
        "Database size check. Review table sizes, backup and retention dry-run before deleting anything.",size,"critical" if fraction>=config["database_critical_fraction"] else "warning"))
    free=shutil.disk_usage(Path(__file__).resolve().parents[1]).free
    checks.append(result("disk_space","local","fail" if free<config["minimum_disk_free_bytes"] else "ok",
        "Local free space check. Review backup and quarantine sizes; free space safely.",free,"critical"))
    backup=client.table("health_checks").select("ts").eq("check_key","backup_complete").eq("status","ok").order("ts",desc=True).limit(1).execute().data
    missing=not backup or now-stamp(backup[0]["ts"])>timedelta(days=config["backup_max_age_days"])
    checks.append(result("backup_missing","database","fail" if missing else "ok",
        "No recent verified backup. Check backup jobs, PostgreSQL credentials and both destinations.",int(missing),"critical"))
    return checks


def research(client, config, now, llm):
    day=now.astimezone(ZoneInfo(llm["limits"]["budget_timezone"])).date().isoformat()
    count=client.table("agent_call_reservations").select("id",count="exact",head=True).eq("budget_day",day).eq("provider",llm["provider"]).execute().count or 0
    maximum=llm["limits"]["max_calls_per_day"]
    checks=[result("llm_budget","daily","fail" if count>=maximum else "warn" if count>=maximum*0.8 else "ok",
        f"Model calls {count}/{maximum}. Defer optional agents and check usage; do not upgrade billing.",count,"critical" if count>=maximum else "warning")]
    threads=client.table("threads").select("status").order("created_at",desc=True).limit(3).execute().data
    failing=len(threads)==3 and all(r["status"] in ("failed","budget_exhausted") for r in threads)
    checks.append(result("thread_failures","agents","warn" if failing else "ok",
        "Recent discussion failures. Check provider status, quota and validation messages.",int(failing)))
    messages=client.table("messages").select("verification_notes").order("id",desc=True).limit(80).execute().data
    claims=[claim for row in messages for claim in row["verification_notes"] or [] if claim.get("claim_id") and claim.get("status") in ("verified","partial","unverified")]
    if claims:
        rate=sum(c["status"]=="verified" for c in claims)/len(claims)
        checks.append(result("verification_rate_low","agents","warn" if rate<config["verification_warning_fraction"] else "ok",
            "Verified-claim fraction is low. Inspect rejected claims, evidence coverage and prompts; this is not an accuracy score.",rate))
    return checks
