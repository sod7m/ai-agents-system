from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from app.orchestrator.task import Task, utc_now_iso
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
        db_path: Path | None = None,
    ) -> None:
        self.logs_dir = logs_dir
        self.default_workspace = default_workspace
        self.max_rounds = max_rounds
        self.approval_mode = approval_mode
        self.write_mode = write_mode
        self.max_command_timeout_seconds = max_command_timeout_seconds
        self.db_path = db_path or logs_dir.parent / "runtime.sqlite3"
        self._active_by_chat: dict[int, Task] = {}
        self._workspace_by_chat: dict[int, Path] = {}
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._load_workspaces()

    def get_workspace(self, chat_id: int) -> Path:
        return self._workspace_by_chat.get(chat_id, self.default_workspace)

    def set_workspace(self, chat_id: int, workspace: Path) -> None:
        self._workspace_by_chat[chat_id] = workspace
        with self._connect() as conn:
            conn.execute(
                """
                insert into workspaces(chat_id, workspace, updated_at)
                values (?, ?, ?)
                on conflict(chat_id) do update set workspace=excluded.workspace, updated_at=excluded.updated_at
                """,
                (chat_id, str(workspace), utc_now_iso()),
            )

    def create(self, chat_id: int, user_id: int | None, task_text: str) -> Task:
        now = datetime.now()
        task_id = f"task_{now:%Y%m%d_%H%M%S}_{chat_id}"
        previous_task = self.get_latest(chat_id)
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
            previous_task_context=self._format_previous_task(previous_task),
        )
        self._active_by_chat[chat_id] = task
        self.save(task, "task.json")
        self.write_text(task, "user_message.md", task_text)
        self.add_event(task, "user_message", task_text)
        return task

    def get_active(self, chat_id: int) -> Task | None:
        if chat_id in self._active_by_chat:
            return self._active_by_chat[chat_id]

        task = self.get_latest(chat_id)
        if task:
            self._active_by_chat[chat_id] = task
        return task

    def get_latest(self, chat_id: int) -> Task | None:
        with self._connect() as conn:
            row = conn.execute(
                "select data from tasks where chat_id = ? order by updated_at desc limit 1",
                (chat_id,),
            ).fetchone()
        if not row:
            return None
        return Task.from_dict(json.loads(row["data"]))

    def list_recent(self, chat_id: int, limit: int = 5) -> list[Task]:
        with self._connect() as conn:
            rows = conn.execute(
                "select data from tasks where chat_id = ? order by updated_at desc limit ?",
                (chat_id, limit),
            ).fetchall()
        return [Task.from_dict(json.loads(row["data"])) for row in rows]

    def list_events(self, task_id: str, limit: int = 20) -> list[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select kind, content, created_at
                from task_events
                where task_id = ?
                order by created_at desc
                limit ?
                """,
                (task_id, limit),
            ).fetchall()
        return list(reversed(rows))

    def cancel_active(self, chat_id: int) -> Task | None:
        task = self.get_active(chat_id)
        if task:
            task.set_status(TaskStatus.CANCELLED)
            self.save(task, "task.json")
            self.add_event(task, "cancelled", "Task cancelled by user")
        return task

    def save(self, task: Task, filename: str = "task.json") -> None:
        task_dir = self._task_dir(task)
        task_dir.mkdir(parents=True, exist_ok=True)
        path = task_dir / filename
        data = task.to_dict()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        with self._connect() as conn:
            conn.execute(
                """
                insert into tasks(id, chat_id, user_id, status, data, updated_at)
                values (?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                    chat_id=excluded.chat_id,
                    user_id=excluded.user_id,
                    status=excluded.status,
                    data=excluded.data,
                    updated_at=excluded.updated_at
                """,
                (
                    task.id,
                    task.chat_id,
                    task.user_id,
                    task.status.value,
                    json.dumps(data, ensure_ascii=False),
                    task.updated_at,
                ),
            )
        self._active_by_chat[task.chat_id] = task

    def write_text(self, task: Task, filename: str, content: str) -> None:
        task_dir = self._task_dir(task)
        task_dir.mkdir(parents=True, exist_ok=True)
        safe_name = self._safe_filename(filename)
        (task_dir / safe_name).write_text(content, encoding="utf-8")

    def add_event(self, task: Task, kind: str, content: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "insert into task_events(task_id, chat_id, kind, content, created_at) values (?, ?, ?, ?, ?)",
                (task.id, task.chat_id, kind, content, utc_now_iso()),
            )

    def _task_dir(self, task: Task) -> Path:
        return self.logs_dir / self._safe_filename(task.id)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("pragma journal_mode=WAL")
            conn.execute(
                """
                create table if not exists workspaces(
                    chat_id integer primary key,
                    workspace text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists tasks(
                    id text primary key,
                    chat_id integer not null,
                    user_id integer,
                    status text not null,
                    data text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists task_events(
                    id integer primary key autoincrement,
                    task_id text not null,
                    chat_id integer not null,
                    kind text not null,
                    content text not null,
                    created_at text not null
                )
                """
            )
            conn.execute("create index if not exists idx_tasks_chat_updated on tasks(chat_id, updated_at)")
            conn.execute("create index if not exists idx_events_task on task_events(task_id, created_at)")

    def _load_workspaces(self) -> None:
        with self._connect() as conn:
            rows = conn.execute("select chat_id, workspace from workspaces").fetchall()
        self._workspace_by_chat = {int(row["chat_id"]): Path(row["workspace"]) for row in rows}

    @staticmethod
    def _safe_filename(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]", "_", value)

    @staticmethod
    def _format_previous_task(task: Task | None) -> str:
        if not task:
            return ""

        changed = "\n".join(f"- {path}" for path in task.changed_files[-10:]) or "- none"
        summary = task.final_summary[:2000] if task.final_summary else "No final summary."
        return f"""Previous task id: {task.id}
Previous user request: {task.raw_user_message}
Previous status: {task.status.value}
Previous changed files:
{changed}
Previous final summary:
{summary}
"""
