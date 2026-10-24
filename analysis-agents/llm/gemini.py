import os
import re
import httpx
from .base import Provider, ProviderError, Reply


def provider_schema(schema):
    """Expand Pydantic definitions into Gemini's supported OpenAPI schema subset."""
    definitions = schema.get("$defs", {})

    def convert(node):
        if "$ref" in node:
            return convert(definitions[node["$ref"].split("/")[-1]])
        if "anyOf" in node:
            choices = [c for c in node["anyOf"] if c.get("type") != "null"]
            if len(choices) != 1:
                raise ValueError("Unsupported schema union")
            return {**convert(choices[0]), "nullable": True}
        result = {}
        for k, v in node.items():
            if k == "type":
                result[k] = v.upper()
            elif k == "properties":
                result[k] = {name: convert(child) for name, child in v.items()}
            elif k == "items":
                result[k] = convert(v)
            elif k in ("required", "enum", "description", "nullable"):
                result[k] = v
        return result

    return convert(schema)


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
                "responseSchema": provider_schema(schema),
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
            data.get("candidates", [{}])[0].get("finishReason", "UNKNOWN"),
        )
