from __future__ import annotations

import aiohttp


class LlamaCppProvider:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def chat(self, messages: list[dict], temperature: float = 0.3) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096,
        }

        timeout = aiohttp.ClientTimeout(total=180)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{self.base_url}/chat/completions", json=payload) as response:
                text = await response.text()
                if response.status >= 400:
                    raise RuntimeError(f"llama.cpp returned HTTP {response.status}: {text[:1000]}")

                data = await response.json()

        try:
            message = data["choices"][0]["message"]
            content = (message.get("content") or "").strip()
            if content:
                return content

            # Some local reasoning models expose useful text here while leaving
            # the OpenAI-compatible content field empty.
            reasoning_content = (message.get("reasoning_content") or "").strip()
            if reasoning_content:
                return reasoning_content

            return ""
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected llama.cpp response shape: {data}") from exc
