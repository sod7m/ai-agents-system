from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.orchestrator.task_state import TaskStatus


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class Task:
    id: str
    chat_id: int
    user_id: int | None
    workspace: Path
    raw_user_message: str
    normalized_task: str
    status: TaskStatus = TaskStatus.TASK_CREATED
    round: int = 0
    max_rounds: int = 3
    approval_mode: str = "bypass"
    write_mode: str = "read_only"
    constraints: list[str] = field(default_factory=list)
    pm_plan: str = ""
    coder_results: list[str] = field(default_factory=list)
    qa_results: list[str] = field(default_factory=list)
    final_summary: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def set_status(self, status: TaskStatus) -> None:
        self.status = status
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict:
        data = asdict(self)
        data["workspace"] = str(self.workspace)
        data["status"] = self.status.value
        return data

    def context_for_pm(self) -> str:
        return f"""User task:
{self.raw_user_message}

Workspace:
{self.workspace}

Runtime mode:
{self.write_mode}

Constraints:
{self._format_list(self.constraints)}
"""

    def context_for_coder(self) -> str:
        return f"""Original user task:
{self.raw_user_message}

PM plan:
{self.pm_plan}

Workspace:
{self.workspace}

Constraints:
{self._format_list(self.constraints)}

Mode:
{self.write_mode}. If this is read_only, do not claim files were created, edited, or tested.
"""

    def context_for_qa(self) -> str:
        latest_coder = self.coder_results[-1] if self.coder_results else ""
        return f"""Original user task:
{self.raw_user_message}

PM plan:
{self.pm_plan}

Coder result:
{latest_coder}

Constraints:
{self._format_list(self.constraints)}

Runtime mode:
{self.write_mode}

Check whether the coder result is good enough for this MVP stage.
If runtime mode is read_only, FAIL any claim that files were actually created or changed.
"""

    def context_for_final_pm(self) -> str:
        return f"""Original user task:
{self.raw_user_message}

PM plan:
{self.pm_plan}

Coder results:
{self._format_list(self.coder_results)}

QA results:
{self._format_list(self.qa_results)}

Final status:
{self.status.value}

Runtime mode:
{self.write_mode}

Hard fact:
If runtime mode is read_only, no project files were created, edited, tested, or built by the system.
"""

    @staticmethod
    def _format_list(items: list[str]) -> str:
        if not items:
            return "- none"
        return "\n".join(f"- {item}" for item in items)
