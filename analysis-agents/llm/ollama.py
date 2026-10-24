"""Optional local provider; never invokes Ollama cloud endpoints."""

import httpx
from .base import Provider, ProviderError, Reply


class Ollama(Provider):
    def generate(self, system, prompt, schema, model, generation):
        if ":cloud" in model:
            raise ProviderError("Cloud Ollama models are disabled")
        try:
            r = httpx.post(
                "http://127.0.0.1:11434/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "format": schema,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                    "options": {
                        "temperature": generation["temperature"],
                        "num_predict": generation["max_output_tokens"],
                    },
                },
                timeout=300,
            )
            r.raise_for_status()
        except httpx.HTTPError:
            raise ProviderError("Local Ollama request failed") from None
        d = r.json()
        return Reply(d["message"]["content"], d.get("prompt_eval_count", 0), d.get("eval_count", 0))
