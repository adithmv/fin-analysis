from datetime import datetime
from zoneinfo import ZoneInfo
import math
import time
from shared.logbook import log_event
from .base import BudgetExhausted, ProviderError


class LimitedProvider:
    def __init__(self, client, provider, config, run_id, thread_id=None, question=False, sleep=time.sleep):
        self.client = client
        self.provider = provider
        self.config = config
        self.run = run_id
        self.thread = thread_id
        self.question = question
        self.sleep = sleep
        self.event_ids = []

    def reserve(self, role, model, size):
        cfg = self.config
        limits = cfg["limits"]
        day = datetime.now(ZoneInfo(limits["budget_timezone"])).date().isoformat()
        args = {
            "p_run": self.run,
            "p_thread": self.thread,
            "p_role": role,
            "p_provider": cfg["provider"],
            "p_model": model,
            "p_day": day,
            "p_daily_limit": limits["max_calls_per_day"],
            "p_thread_limit": limits["max_calls_per_question" if self.question else "max_calls_per_thread"],
            "p_rpm": limits["requests_per_minute"],
            "p_input_tokens": size,
            "p_tpm": limits["input_tokens_per_minute"],
        }
        for attempt in range(3):
            try:
                return self.client.rpc("reserve_agent_call", args).execute().data
            except Exception as exc:
                message = str(exc)
                if "RATE_LIMIT" in message and attempt < 2:
                    log_event(
                        self.run,
                        "analysis-agents",
                        "rate_wait",
                        "warning",
                        agent=role,
                        output_summary="Waiting for local minute budget",
                    )
                    self.sleep(60)
                    continue
                if any(k in message for k in ("BUDGET", "RATE_LIMIT", "PROMPT_TOO_LARGE")):
                    raise BudgetExhausted("Configured call/token budget reached") from None
                raise

    def generate(self, system, prompt, schema, role, model):
        cfg = self.config
        for attempt in range(cfg["retries"]["max_attempts"]):
            reservation = self.reserve(role, model, math.ceil((len(prompt) + len(system)) / 3))
            start = time.monotonic()
            reply = None
            failure = None
            try:
                reply = self.provider.generate(system, prompt, schema, model, cfg["generation"])
            except ProviderError as exc:
                failure = exc
            event = log_event(
                self.run,
                "analysis-agents",
                "llm_call",
                "failed" if failure else "success",
                agent=role,
                tool=model,
                input_summary="Public evidence pack and verified transcript",
                output_summary="Provider failed" if failure else "Structured response received",
                error=str(failure) if failure else None,
                duration_ms=int((time.monotonic() - start) * 1000),
                api_calls=1,
                tokens_in=reply.tokens_in if reply else 0,
                tokens_out=reply.tokens_out if reply else 0,
                meta={"thread_id": self.thread, "reservation_id": reservation, "attempt": attempt + 1},
                return_id=True,
            )
            event_id = event if isinstance(event, int) and not isinstance(event, bool) else None
            if event_id:
                self.event_ids.append(event_id)
            self.client.table("agent_call_reservations").update(
                {
                    "status": "failed" if failure else "success",
                    "tokens_in": reply.tokens_in if reply else 0,
                    "tokens_out": reply.tokens_out if reply else 0,
                    "event_id": event_id,
                }
            ).eq("id", reservation).execute()
            if reply:
                return reply
            if failure.status not in (0, 429, 500, 502, 503, 504):
                raise failure
            if attempt + 1 == cfg["retries"]["max_attempts"]:
                if failure.status == 429:
                    raise BudgetExhausted("Provider quota exhausted; partial transcript preserved")
                raise failure
            wait = max(cfg["retries"]["backoff_seconds"][attempt], failure.retry_after)
            if wait > 60:
                raise BudgetExhausted("Provider requested a longer pause; retry in a later run")
            log_event(
                self.run,
                "analysis-agents",
                "retry_llm",
                "retried",
                agent=role,
                output_summary=f"Backoff {wait} seconds",
            )
            self.sleep(wait)
