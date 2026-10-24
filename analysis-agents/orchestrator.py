from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from uuid import uuid4
from shared.logbook import log_event
from data.asof_db import AsOfDB, instant
from evidence.pack import build
from gating import decide
from agents.base import generate
from verifier import verify
from report import build_report
from llm.limiter import LimitedProvider
from llm.base import BudgetExhausted
from policy import public_question


def now():
    return datetime.now(timezone.utc).isoformat()


def write_message(client, thread_id, messages, role, content, **fields):
    row = dict(
        thread_id=thread_id,
        seq=len(messages) + 1,
        author_role=role,
        author_type="system" if role == "system" else "agent",
        content_md=content,
        verification_status="not_applicable",
    )
    row.update(fields)
    hidden = row.pop("_verification", None)
    client.table("messages").insert(row).execute()
    if hidden:
        row["_verification"] = hidden
    messages.append(row)
    return row


def run(client, provider, config, symbol, force=False, as_of=None, on_demand=False):
    cutoff = instant(as_of) if as_of else datetime.now(timezone.utc)
    if cutoff > datetime.now(timezone.utc):
        raise ValueError("Research cutoff cannot be in the future")
    day = cutoff.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()
    kind = "on_demand" if on_demand else "daily"
    existing = (
        client.table("threads")
        .select("id,status")
        .eq("symbol", symbol)
        .eq("thread_date", day)
        .eq("kind", "daily")
        .execute()
        .data
        if not on_demand
        else []
    )
    if existing:
        return {"thread_id": existing[0]["id"], "status": existing[0]["status"], "duplicate_skipped": True}
    thread_id = str(uuid4())
    run_id = str(uuid4())
    messages = []
    client.table("threads").insert(
        dict(
            id=thread_id,
            symbol=symbol,
            thread_date=day,
            kind=kind,
            status="running",
            data_cutoff_ts=cutoff.isoformat(),
            run_id=run_id,
            llm_provider=config["llm"]["provider"],
            llm_model=config["llm"]["models"]["analyst"],
            prompt_version=config["agents"]["prompt_version"],
            config={**config, "replay": bool(as_of)},
            started_at=now(),
        )
    ).execute()
    log_event(run_id, "analysis-agents", "run_start", "started", symbol=symbol, meta={"thread_id": thread_id})
    status = "failed"
    reason = None
    try:
        pack, pack_hash = build(AsOfDB(client, cutoff.isoformat()), symbol, config)
        client.table("evidence_packs").insert(
            dict(thread_id=thread_id, pack=pack, pack_hash=pack_hash)
        ).execute()
        log_event(
            run_id,
            "analysis-agents",
            "build_evidence",
            "success",
            symbol=symbol,
            output_summary=f"{len(pack['items'])} frozen references",
            meta={"pack_hash": pack_hash},
        )
        allowed, reasons = decide(pack, config["agents"], force)
        if not allowed:
            write_message(client, thread_id, messages, "system", "; ".join(reasons))
            status = "skipped"
        else:
            limited = LimitedProvider(client, provider, config["llm"], run_id, thread_id)
            roles = [("technical_analyst", 1), ("news_analyst", 1), ("bull", 1), ("bear", 1)]
            if config["agents"]["debate_rounds"] == 2:
                roles.extend([("bull", 2), ("bear", 2)])
            roles.extend([("risk_manager", 1), ("summariser", 1)])
            for role, round_number in roles:
                before = len(limited.event_ids)
                output, reply, model = generate(limited, role, round_number, pack, messages, config)
                checked = verify(output, pack, config["verification"])
                log_event(
                    run_id,
                    "analysis-agents",
                    "verify_claims",
                    "failed"
                    if checked["severe"]
                    else "warning"
                    if checked["status"] != "verified"
                    else "success",
                    agent=role,
                    symbol=symbol,
                    output_summary=checked["status"],
                    meta={
                        "thread_id": thread_id,
                        "severe": checked["severe"],
                        "claim_results": checked["claims"],
                    },
                )
                write_message(
                    client,
                    thread_id,
                    messages,
                    role,
                    output.content_md,
                    round=round_number,
                    stance=output.stance,
                    confidence=output.confidence,
                    claims=[c.model_dump() for c in output.claims],
                    evidence=[
                        dict(
                            evidence_id=c.evidence_id,
                            **next(i["ref"] for i in pack["items"] if i["evidence_id"] == c.evidence_id),
                        )
                        for c in output.claims
                        if c.evidence_id and any(i["evidence_id"] == c.evidence_id for i in pack["items"])
                    ],
                    verification_status=checked["status"],
                    verification_notes=[*checked["claims"], *checked["notes"]],
                    event_ids=limited.event_ids[before:],
                    llm_model=model,
                    tokens_in=reply.tokens_in,
                    tokens_out=reply.tokens_out,
                    _verification=checked,
                )
                if role == "summariser":
                    report = build_report(output, checked, pack, config, messages)
                    report["as_of_date"] = day
                    client.table("analysis_reports").insert(dict(thread_id=thread_id, **report)).execute()
            status = "completed"
    except BudgetExhausted as exc:
        status = "budget_exhausted"
        reason = str(exc)
        write_message(client, thread_id, messages, "system", reason + " No completed report was produced.")
    except Exception as exc:
        reason = str(exc)
        log_event(run_id, "analysis-agents", "thread_failed", "failed", symbol=symbol, error=reason)
        write_message(
            client,
            thread_id,
            messages,
            "system",
            "Analysis stopped before completion. See the run log for the failure; no full report is claimed.",
        )
    client.table("threads").update(dict(status=status, finished_at=now(), failure_reason=reason)).eq(
        "id", thread_id
    ).execute()
    log_event(
        run_id,
        "analysis-agents",
        "run_end",
        "success" if status == "completed" else "skipped" if status == "skipped" else "failed",
        symbol=symbol,
        output_summary=status,
        meta={"thread_id": thread_id},
    )
    return {"thread_id": thread_id, "status": status}


def answer(client, provider, config, request):
    thread = client.table("threads").select("*").eq("id", request["thread_id"]).single().execute().data
    pack = (
        client.table("evidence_packs")
        .select("pack")
        .eq("thread_id", thread["id"])
        .single()
        .execute()
        .data["pack"]
    )
    messages = client.table("messages").select("*").eq("thread_id", thread["id"]).order("seq").execute().data
    for m in messages:
        m["_verification"] = {"claims": [r for r in m["verification_notes"] if "claim_id" in r]}
    text, refusal = public_question(request["question_text"], config["agents"]["policy"]["forbid_terms"])
    # Private question content is stored only in owner-protected tables, never public logs.
    write_message(client, thread["id"], messages, "user", request["question_text"], author_type="user")
    if refusal:
        write_message(client, thread["id"], messages, "system", refusal)
        return "rejected"
    run_id = str(uuid4())
    limited = LimitedProvider(client, provider, config["llm"], run_id, thread["id"], question=True)
    output, reply, model = generate(limited, "research_assistant", 1, pack, messages, config, text)
    checked = verify(output, pack, config["verification"])
    write_message(
        client,
        thread["id"],
        messages,
        "research_assistant",
        output.content_md,
        claims=[c.model_dump() for c in output.claims],
        stance=output.stance,
        confidence=output.confidence,
        evidence=[
            dict(
                evidence_id=c.evidence_id,
                **next(i["ref"] for i in pack["items"] if i["evidence_id"] == c.evidence_id),
            )
            for c in output.claims
            if c.evidence_id and any(i["evidence_id"] == c.evidence_id for i in pack["items"])
        ],
        verification_status=checked["status"],
        verification_notes=[*checked["claims"], *checked["notes"]],
        llm_model=model,
        event_ids=limited.event_ids,
        tokens_in=reply.tokens_in,
        tokens_out=reply.tokens_out,
    )
    return "done"
