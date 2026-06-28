from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IntentResult:
    name: str
    confidence: float
    raw_message: str
    extracted_task: str | None = None
    target_agent: str | None = None
    target_path: str | None = None
    workspace: str | None = None
    constraints: tuple[str, ...] = field(default_factory=tuple)
    references_active_task: bool = False
