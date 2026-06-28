from __future__ import annotations

from app.agents.base_agent import AgentCard, BaseAgent
from app.agents.prompts import CODER_PROMPT, FINAL_PM_PROMPT, PM_PROMPT, QA_PROMPT
from app.llm.base_provider import BaseLLMProvider


class AgentPool:
    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.pm = BaseAgent(
            AgentCard(
                name="PM Agent",
                role="pm",
                system_prompt=PM_PROMPT,
                allowed_tools=("project_summary", "list_files", "read_file"),
                temperature=0.25,
            ),
            llm_provider,
        )
        self.coder = BaseAgent(
            AgentCard(
                name="Coder Agent",
                role="coder",
                system_prompt=CODER_PROMPT,
                allowed_tools=("list_files", "read_file"),
                temperature=0.25,
            ),
            llm_provider,
        )
        self.qa = BaseAgent(
            AgentCard(
                name="QA Agent",
                role="qa",
                system_prompt=QA_PROMPT,
                allowed_tools=("git_diff", "run_command"),
                temperature=0.2,
            ),
            llm_provider,
        )
        self.final_pm = BaseAgent(
            AgentCard(
                name="Final PM Agent",
                role="final_pm",
                system_prompt=FINAL_PM_PROMPT,
                allowed_tools=(),
                temperature=0.3,
            ),
            llm_provider,
        )

    def by_name(self, name: str) -> BaseAgent | None:
        normalized = name.strip().lower()
        aliases = {
            "pm": self.pm,
            "project_manager": self.pm,
            "project manager": self.pm,
            "coder": self.coder,
            "кодер": self.coder,
            "qa": self.qa,
            "тестувальник": self.qa,
            "final_pm": self.final_pm,
        }
        return aliases.get(normalized)

