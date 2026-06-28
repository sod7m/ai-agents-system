from __future__ import annotations

from dataclasses import dataclass

from app.llm.base_provider import BaseLLMProvider


@dataclass(frozen=True)
class AgentCard:
    name: str
    role: str
    system_prompt: str
    allowed_tools: tuple[str, ...]
    temperature: float = 0.3


class BaseAgent:
    def __init__(self, card: AgentCard, llm_provider: BaseLLMProvider) -> None:
        self.card = card
        self.llm = llm_provider

    @property
    def name(self) -> str:
        return self.card.name

    @property
    def role(self) -> str:
        return self.card.role

    async def run(self, context: str) -> str:
        messages = [
            {"role": "system", "content": self.card.system_prompt},
            {"role": "user", "content": context},
        ]
        return await self.llm.chat(messages=messages, temperature=self.card.temperature)

