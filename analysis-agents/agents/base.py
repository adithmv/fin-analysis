from pathlib import Path
import json
from schemas import Output
from policy import delimit, violations

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


def safe_transcript(messages):
    output = []
    for m in messages:
        verification = m.get("_verification", {})
        accepted = {
            r["claim_id"] for r in verification.get("claims", []) if r["status"] in ("verified", "partial")
        }
        claims = [
            {k: v for k, v in c.items() if v is not None} for c in m.get("claims", []) if c["id"] in accepted
        ]
        output.append(
            {
                "role": m["author_role"],
                "round": m.get("round"),
                "status": m["verification_status"],
                "claims": claims,
                "verification": [
                    {k: v for k, v in r.items() if k != "evidence_ref"}
                    for r in verification.get("claims", [])
                ],
                "withheld_claims": [c["id"] for c in m.get("claims", []) if c["id"] not in accepted],
            }
        )
    return output


def generate(limited, role, round_number, pack, messages, config, question=None):
    snapshot = config.get("prompt_snapshot")
    system = (
        (snapshot["system"] + "\n" + snapshot[role])
        if snapshot
        else (PROMPTS / "system.md").read_text() + "\n" + (PROMPTS / f"{role}.md").read_text()
    )
    role_items = pack["items"]
    stats = sorted(
        [i for i in role_items if i["section"] == "track_records"],
        key=lambda i: (
            i["row"]["scope"] != "POOLED",
            bool(i["row"].get("abnormal")),
            i["row"]["sample"] not in ("in_sample", "out_of_sample"),
            i["row"]["signal_key"],
            i["row"]["direction"],
            i["row"]["sample"],
        ),
    )
    news_stats = [i for i in stats if i["row"]["signal_key"].startswith(("news:", "sentiment:"))]
    technical_stats = [i for i in stats if i not in news_stats]
    chosen_stats = (
        news_stats[:8]
        if role == "news_analyst"
        else technical_stats[:8]
        if role == "technical_analyst"
        else technical_stats[:4] + news_stats[:4]
    )
    core_indicators = {
        "rsi_14",
        "sma_50",
        "sma_200",
        "atr_14",
        "adx_14",
        "macd_line_12_26_9",
        "macd_hist_12_26_9",
        "bb_upper_20_2",
        "bb_lower_20_2",
        "volume_avg_20",
    }
    # Full evidence is frozen in the database; prompts contain a compact, auditable subset.
    counts = {}
    selected = []
    caps = {
        "prices": 5,
        "market": 3,
        "indicators": 10,
        "signals": 8,
        "track_records": 8,
        "news": 5,
        "events": 8,
        "macro": 3,
        "actions": 8,
        "quality": 10,
        "previous_report": 1,
    }
    for item in role_items:
        section = item["section"]
        if section == "track_records" and item not in chosen_stats:
            continue
        if section == "indicators" and item["row"]["series_key"] not in core_indicators:
            continue
        if role == "news_analyst" and section in ("prices", "indicators", "signals", "market"):
            continue
        if (
            role == "news_analyst"
            and section == "track_records"
            and not item["row"]["signal_key"].startswith(("news:", "sentiment:"))
        ):
            continue
        if role == "technical_analyst" and section in ("news", "events", "macro"):
            continue
        if (
            role == "technical_analyst"
            and section == "track_records"
            and item["row"]["signal_key"].startswith(("news:", "sentiment:"))
        ):
            continue
        counts[section] = counts.get(section, 0) + 1
        if section == "prices" and item not in [i for i in role_items if i["section"] == "prices"][-5:]:
            continue
        if section != "prices" and counts[section] > caps.get(section, 20):
            continue
        selected.append(item)
    snapshot = {**pack, "items": selected}
    prompt = (
        "<untrusted_data>"
        + delimit(
            {
                "evidence_pack": snapshot,
                "prior_verified_claims": safe_transcript(messages),
                "public_research_question": question,
                "round": round_number,
            }
        )
        + "</untrusted_data>"
    )
    if len(prompt) > config["agents"]["evidence_pack"]["max_prompt_characters"]:
        raise ValueError("Prompt size limit exceeded")
    model = config["llm"]["models"][
        "summariser" if role == "summariser" else "debater" if role in ("bull", "bear") else "analyst"
    ]
    last_error = ""
    rejection = "invalid schema or research policy"
    for attempt in range(2):
        reply = limited.generate(
            system,
            prompt + ("\nCorrection: " + last_error if attempt else ""),
            Output.model_json_schema(),
            role,
            model,
        )
        try:
            if reply.finish_reason != "STOP":
                rejection = "provider response incomplete"
                raise ValueError(rejection)
            output = Output.model_validate_json(reply.text)
            bad = violations(output.model_dump(), config["agents"]["policy"]["forbid_terms"])
            if bad:
                raise ValueError("Research-only policy violation; remove trading instructions")
            return output, reply, model
        except (ValueError, json.JSONDecodeError):
            # Do not echo model text (which could contain injected secrets or instructions) into repair messages.
            last_error = "Previous output was rejected. Return valid schema JSON and obey research-only policy. No trading instructions."
    raise ValueError(f"Model output withheld after one schema/policy repair attempt ({rejection})")
