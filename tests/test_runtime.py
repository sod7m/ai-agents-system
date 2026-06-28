from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.router.rule_router import RuleRouter
from app.storage.task_repository import TaskRepository
from app.tools.action_executor import execute_actions, parse_actions
from app.tools.project_tools import project_summary


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

    def test_qa_history_question(self) -> None:
        intent = RuleRouter().detect("Що відхилив QA?")
        self.assertEqual(intent.name, "qa_history_request")

    def test_change_file_instruction_is_task(self) -> None:
        intent = RuleRouter().detect("Зміни TEST/profile.html: заміни ім'я на Дмитро")
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

    def test_patch_file_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            target = workspace / "profile.html"
            target.write_text("<h1>Old</h1>", encoding="utf-8")
            actions = [
                {
                    "type": "patch_file",
                    "path": "profile.html",
                    "old_text": "Old",
                    "new_text": "New",
                }
            ]
            results = execute_actions(actions, workspace, writes_enabled=True)

            self.assertTrue(results[0].ok)
            self.assertEqual(target.read_text(encoding="utf-8"), "<h1>New</h1>")

    def test_read_file_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "profile.html").write_text("<h1>Dmytro</h1>", encoding="utf-8")
            actions = [{"type": "read_file", "path": "profile.html"}]
            results = execute_actions(actions, workspace, writes_enabled=True)

            self.assertTrue(results[0].ok)
            self.assertIn("<h1>Dmytro</h1>", results[0].message)

    def test_rejects_invalid_action_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            results = execute_actions([{"type": "write_file", "path": "x.txt"}], workspace, writes_enabled=True)

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
            repo.add_event(task, "qa_result", "Статус: FAIL")

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
            events = restored.list_events(task.id)
            self.assertTrue(any(event["kind"] == "qa_result" for event in events))


class ProjectSummaryTests(unittest.TestCase):
    def test_includes_relevant_file_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "TEST").mkdir()
            (workspace / "TEST" / "profile.html").write_text("<h1>Profile</h1>", encoding="utf-8")

            summary = project_summary(workspace, "Зміни TEST/profile.html")

            self.assertIn("TEST/profile.html", summary)
            self.assertIn("<h1>Profile</h1>", summary)


if __name__ == "__main__":
    unittest.main()
