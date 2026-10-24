import json
import re


def violations(value, terms):
    text = json.dumps(value, ensure_ascii=True) if not isinstance(value, str) else value
    found = [term for term in terms if re.search(r"\b" + re.escape(term) + r"\b", text, re.I)]
    if re.search(
        r"\b(?:you should|recommend(?:ed)?|must|should i|i would|consider)\s+(?:consider\s+)?(?:buy(?:ing)?|sell(?:ing)?|purchas(?:e|ing)|short(?:ing)?)\b",
        text,
        re.I,
    ):
        found.append("trade instruction")
    if re.search(r"\b(?:take|open|enter)\s+(?:a\s+)?(?:long|short)\s+position\b", text, re.I):
        found.append("position instruction")
    if re.search(r"\b(?:invest|allocate)\s+(?:rs\.?|inr|₹|\d)", text, re.I):
        found.append("allocation instruction")
    return found


def public_question(text, terms):
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
        raise ValueError("Question must contain 1–2000 characters")
    if re.search(
        r"\b(?:my portfolio|my salary|my account|my holdings|i own|i hold|api.key|password|secret)\b|[\w.+-]+@[\w.-]+|\b(?:\d[ -]?){10,}\b",
        text,
        re.I,
    ):
        return (
            None,
            "Please remove personal holdings, account details and credentials. Only public market research questions can be sent to the model.",
        )
    if violations(text, terms) or re.search(r"\b(?:buy|sell|target|sizing)\b", text, re.I):
        parts = re.split(r"(?<=[?.!])\s+", text)
        research = [
            p
            for p in parts
            if not violations(p, terms)
            and not re.search(r"\b(?:buy|sell|target|sizing)\b", p, re.I)
            and re.search(r"\b(?:evidence|signals|news|reliability|research|data)\b", p, re.I)
        ]
        return (
            " ".join(research) or None,
            "I can discuss stored research evidence, but cannot provide trading instructions. Any separate research question will be answered from the evidence.",
        )
    return text.strip(), None


def delimit(value):
    # Quotes are JSON-escaped, and markup cannot close an untrusted-data wrapper.
    return (
        json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
