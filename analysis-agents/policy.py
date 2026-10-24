import json
import re


def violations(value, terms):
    text = json.dumps(value, ensure_ascii=True) if not isinstance(value, str) else value
    found = [term for term in terms if re.search(r"\b" + re.escape(term) + r"\b", text, re.I)]
    if re.search(
        r"\b(?:you should|recommend(?:ed)?|must|should i|i would)\s+(?:buy|sell|purchase|short)\b", text, re.I
    ):
        found.append("trade instruction")
    if re.search(r"\b(?:invest|allocate)\s+(?:rs\.?|inr|₹|\d)", text, re.I):
        found.append("allocation instruction")
    return found


def public_question(text, terms):
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
        raise ValueError("Question must contain 1–2000 characters")
    if violations(text, terms) or re.search(r"\b(?:buy|sell|target|sizing)\b", text, re.I):
        return (
            None,
            "I can discuss stored research evidence, but cannot provide trading instructions. Please ask about signals, news, or their measured reliability.",
        )
    if re.search(
        r"\b(?:my portfolio|my salary|my account|my holdings|i own|i hold|api.key|password|secret)\b|[\w.+-]+@[\w.-]+|\b(?:\d[ -]?){10,}\b",
        text,
        re.I,
    ):
        return (
            None,
            "Please remove personal holdings, account details and credentials. Only public market research questions can be sent to the model.",
        )
    return text.strip(), None


def delimit(value):
    # Quotes are JSON-escaped, and markup cannot close an untrusted-data wrapper.
    return (
        json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
