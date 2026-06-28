from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.router.rule_router import RuleRouter
from app.storage.task_repository import TaskRepository
from app.tools.action_executor import execute_actions, parse_actions


class RuleRouterTests(unittest.TestCase):
    def test_question_is_not_task(self) -> None:
        intent = RuleRouter().detect("Можеш зробити сторінку?")
        self.assertEqual(intent.name, "general_question")

    def test_create_directory_command(self) -> None:
        intent = RuleRouter().detect("Створи папку TEST")
        self.assertEqual(intent.name, "create_directory")
        self.assertEqual(intent.target_path, "TEST")

    def test_page_task_is_not_directory_command(self) -> None:
        intent = RuleRouter().detect("Зроби сторінку логіну в папці TEST")
        self.assertEqual(intent.name, "new_task")


class ActionExecutorTests(unittest.TestCase):
    def test_write_file_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            actions = parse_actions(
                '{"actions":[{"type":"write_file","path":"TEST/notes.txt","content":"hello"}]}'
            )
            results = execute_actions(actions, workspace, writes_enabled=True)

            self.assertTrue(results[0].ok)
            self.assertEqual((workspace / "TEST" / "notes.txt").read_text(encoding="utf-8"), "hello")

    def test_blocks_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            actions = [{"type": "write_file", "path": "../outside.txt", "content": "no"}]
            results = execute_actions(actions, workspace, writes_enabled=True)

            self.assertFalse(results[0].ok)


class TaskRepositoryTests(unittest.TestCase):
    def test_persists_workspace_and_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = TaskRepository(
                logs_dir=root / "logs",
                default_workspace=root,
                max_rounds=3,
                approval_mode="bypass",
                write_mode="bypass",
                db_path=root / "runtime.sqlite3",
            )
            repo.set_workspace(123, root / "project")
            task = repo.create(123, 456, "Зроби тест")
            task.final_summary = "done"
            repo.save(task)

            restored = TaskRepository(
                logs_dir=root / "logs",
                default_workspace=root,
                max_rounds=3,
                approval_mode="bypass",
                write_mode="bypass",
                db_path=root / "runtime.sqlite3",
            )

            self.assertEqual(restored.get_workspace(123), root / "project")
            latest = restored.get_active(123)
            self.assertIsNotNone(latest)
            self.assertEqual(latest.id, task.id)
            self.assertEqual(latest.final_summary, "done")


if __name__ == "__main__":
    unittest.main()

