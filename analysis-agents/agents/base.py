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
        claims = [c for c in m.get("claims", []) if c["id"] in accepted]
        output.append(
            {
                "role": m["author_role"],
                "round": m.get("round"),
                "status": m["verification_status"],
                "claims": claims,
                "verification": verification,
                "withheld_claims": [c["id"] for c in m.get("claims", []) if c["id"] not in accepted],
            }
        )
    return output


def generate(limited, role, round_number, pack, messages, config, question=None):
    system = (PROMPTS / "system.md").read_text() + "\n" + (PROMPTS / f"{role}.md").read_text()
    role_items = pack["items"]
    # Full evidence is frozen in the database; prompts contain a compact, auditable subset.
    counts = {}
    selected = []
    caps = {
        "prices": 5,
        "market": 3,
        "indicators": 24,
        "signals": 18,
        "track_records": 24,
        "news": 8,
        "events": 16,
        "macro": 5,
        "actions": 8,
        "quality": 10,
        "previous_report": 1,
    }
    for item in role_items:
        section = item["section"]
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
    for attempt in range(2):
        reply = limited.generate(
            system,
            prompt + ("\nCorrection: " + last_error if attempt else ""),
            Output.model_json_schema(),
            role,
            model,
        )
        try:
            output = Output.model_validate_json(reply.text)
            bad = violations(output.model_dump(), config["agents"]["policy"]["forbid_terms"])
            if bad:
                raise ValueError("Research-only policy violation; remove trading instructions")
            return output, reply, model
        except (ValueError, json.JSONDecodeError):
            # Do not echo model text (which could contain injected secrets or instructions) into repair messages.
            last_error = "Previous output was rejected. Return valid schema JSON and obey research-only policy. No trading instructions."
    raise ValueError("Model output withheld after one schema/policy repair attempt")
