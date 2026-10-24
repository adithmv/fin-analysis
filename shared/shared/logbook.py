"""Best-effort, sanitized, code-written action events."""

import os
import re
import sys
import time
from contextlib import contextmanager
from types import SimpleNamespace
import httpx

from .db import get_client

SENSITIVE = re.compile(r"key|token|secret|password|authorization|cookie", re.I)


def sanitize(value):
    if isinstance(value, dict):
        return {
            str(k): "[REDACTED]"
            if SENSITIVE.search(str(k)) and k not in ("tokens_in", "tokens_out")
            else sanitize(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = str(value)
    for name, secret in os.environ.items():
        if SENSITIVE.search(name) and len(secret) >= 8:
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[REDACTED]", text)
    text = re.sub(r"sb_(?:secret|publishable)_[A-Za-z0-9_-]+", "[REDACTED]", text)
    text = re.sub(r"(?i)(bearer\s+)\S+", r"\1[REDACTED]", text)
    text = re.sub(
        r"(?i)((?:api[_-]?key|token|secret|password|authorization)[\s\"\x27]*[:=][\s\"\x27]*)[^\s,\"\x27&}]+",
        r"\1[REDACTED]",
        text,
    )
    return text


def log_event(
    run_id,
    module,
    action,
    status,
    tool=None,
    symbol=None,
    agent=None,
    input_summary=None,
    output_summary=None,
    source_urls=None,
    duration_ms=None,
    api_calls=None,
    error=None,
    meta=None,
    tokens_in=None,
    tokens_out=None,
    return_id=False,
):
    try:
        row = sanitize(
            dict(
                run_id=str(run_id),
                module=module,
                action=action,
                status=status,
                tool=tool,
                symbol=symbol,
                agent=agent,
                input_summary=input_summary,
                output_summary=output_summary,
                source_urls=source_urls,
                duration_ms=duration_ms,
                api_calls=api_calls,
                error=error,
                meta=meta or {},
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )
        )
        for key in ("input_summary", "output_summary"):
            if row[key] is not None:
                row[key] = " ".join(str(row[key]).split())[:300]
        if row["error"]:
            row["error"] = str(row["error"])[:2000]
        for attempt in range(3):
            try:
                response = get_client().table("agent_events").insert(row).execute()
                break
            except (httpx.ConnectError, httpx.ConnectTimeout):
                # Connection setup failed before sending the insert. Do not retry
                # read/write timeouts: the server may already have saved the event.
                if attempt == 2:
                    raise
                time.sleep(0.5 * 2**attempt)
        return response.data[0]["id"] if return_id and response.data else True
    except Exception:
        # Do not print database exceptions: they can contain authentication headers.
        try:
            print("Logbook write failed; action event could not be saved.", file=sys.stderr)
        except Exception:
            pass
        return False


@contextmanager
def action(run_id, module, action, **kwargs):
    ev = SimpleNamespace(**kwargs)
    start = time.monotonic()
    log_event(run_id, module, action, "started", **kwargs)
    try:
        yield ev
    except Exception as exc:
        fields = vars(ev).copy()
        fields.update(error=str(exc), duration_ms=int((time.monotonic() - start) * 1000))
        log_event(run_id, module, action, "failed", **fields)
        raise
    else:
        fields = vars(ev).copy()
        fields["duration_ms"] = int((time.monotonic() - start) * 1000)
        log_event(run_id, module, action, "success", **fields)
