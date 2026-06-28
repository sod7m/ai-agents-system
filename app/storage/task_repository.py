from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from app.orchestrator.task import Task
from app.orchestrator.task_state import TaskStatus


class TaskRepository:
    def __init__(
        self,
        logs_dir: Path,
        default_workspace: Path,
        max_rounds: int,
        approval_mode: str,
        write_mode: str = "read_only",
        max_command_timeout_seconds: int = 120,
    ) -> None:
        self.logs_dir = logs_dir
        self.default_workspace = default_workspace
        self.max_rounds = max_rounds
        self.approval_mode = approval_mode
        self.write_mode = write_mode
        self.max_command_timeout_seconds = max_command_timeout_seconds
        self._active_by_chat: dict[int, Task] = {}
        self._workspace_by_chat: dict[int, Path] = {}
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def get_workspace(self, chat_id: int) -> Path:
        return self._workspace_by_chat.get(chat_id, self.default_workspace)

    def set_workspace(self, chat_id: int, workspace: Path) -> None:
        self._workspace_by_chat[chat_id] = workspace

    def create(self, chat_id: int, user_id: int | None, task_text: str) -> Task:
        now = datetime.now()
        task_id = f"task_{now:%Y%m%d_%H%M%S}_{chat_id}"
        task = Task(
            id=task_id,
            chat_id=chat_id,
            user_id=user_id,
            workspace=self.get_workspace(chat_id),
            raw_user_message=task_text,
            normalized_task=task_text,
            max_rounds=self.max_rounds,
            approval_mode=self.approval_mode,
            write_mode=self.write_mode,
        )
        self._active_by_chat[chat_id] = task
        self.save(task, "task.json")
        self.write_text(task, "user_message.md", task_text)
        return task

    def get_active(self, chat_id: int) -> Task | None:
        return self._active_by_chat.get(chat_id)

    def cancel_active(self, chat_id: int) -> Task | None:
        task = self._active_by_chat.get(chat_id)
        if task:
            task.set_status(TaskStatus.CANCELLED)
            self.save(task, "task.json")
        return task

    def save(self, task: Task, filename: str = "task.json") -> None:
        task_dir = self._task_dir(task)
        task_dir.mkdir(parents=True, exist_ok=True)
        path = task_dir / filename
        path.write_text(json.dumps(task.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def write_text(self, task: Task, filename: str, content: str) -> None:
        task_dir = self._task_dir(task)
        task_dir.mkdir(parents=True, exist_ok=True)
        safe_name = self._safe_filename(filename)
        (task_dir / safe_name).write_text(content, encoding="utf-8")

    def _task_dir(self, task: Task) -> Path:
        return self.logs_dir / self._safe_filename(task.id)

    @staticmethod
    def _safe_filename(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]", "_", value)
