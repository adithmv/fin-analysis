import os
import re
import httpx
from .base import Provider, ProviderError, Reply


class Gemini(Provider):
    def generate(self, system, prompt, schema, model, generation):
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise ProviderError("GEMINI_API_KEY is missing from root .env")
        if not re.fullmatch(r"gemini-[\w.-]+", model):
            raise ProviderError("Invalid configured model name")
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": generation["temperature"],
                "maxOutputTokens": generation["max_output_tokens"],
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
        }
        # No grounding, function tools, URL context, code execution, or browser capabilities.
        try:
            r = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": key},
                json=payload,
                timeout=90,
            )
        except httpx.TransportError as exc:
            raise ProviderError(type(exc).__name__) from None
        if not r.is_success:
            wait = r.headers.get("retry-after", "0")
            raise ProviderError(
                f"Gemini returned HTTP {r.status_code}; no automatic billing change",
                r.status_code,
                float(wait) if wait.isdigit() else 0,
            )
        data = r.json()
        usage = data.get("usageMetadata", {})
        text = "".join(
            p.get("text", "")
            for c in data.get("candidates", [])[:1]
            for p in c.get("content", {}).get("parts", [])
            if not p.get("thought")
        )
        return Reply(
            text,
            usage.get("promptTokenCount", 0),
            usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0),
        )
