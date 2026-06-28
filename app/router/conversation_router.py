from __future__ import annotations

from app.router.intents import IntentResult
from app.router.rule_router import RuleRouter


class ConversationRouter:
    def __init__(self) -> None:
        self.rule_router = RuleRouter()

    async def detect(self, message: str, chat_id: int | None = None) -> IntentResult:
        # MVP uses a deterministic router first. LLM fallback can be added behind this API.
        return self.rule_router.detect(message)

