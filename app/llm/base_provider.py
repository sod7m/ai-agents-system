from __future__ import annotations

from typing import Protocol


class BaseLLMProvider(Protocol):
    async def chat(self, messages: list[dict], temperature: float = 0.3) -> str:
        """Return assistant text for a chat completion request."""

