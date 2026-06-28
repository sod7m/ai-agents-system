from __future__ import annotations

import logging
from pathlib import Path
from typing import Awaitable, Callable

from app.agents.factory import AgentPool
from app.orchestrator.task import Task
from app.orchestrator.task_state import TaskStatus
from app.router.conversation_router import ConversationRouter
from app.router.intents import IntentResult
from app.storage.task_repository import TaskRepository
from app.tools.action_executor import changed_paths, execute_actions, format_tool_results, parse_actions
from app.tools.file_tools import create_directory
from app.tools.git_tools import git_diff, git_status
from app.tools.project_tools import project_summary

SendMessage = Callable[[str], Awaitable[None]]

logger = logging.getLogger(__name__)


class MainOrchestrator:
    def __init__(
        self,
        router: ConversationRouter,
        agents: AgentPool,
        task_repository: TaskRepository,
    ) -> None:
        self.router = router
        self.agents = agents
        self.tasks = task_repository

    async def handle_message(
        self,
        chat_id: int,
        user_id: int | None,
        user_message: str,
        send: SendMessage,
    ) -> None:
        intent = await self.detect_intent(user_message, chat_id)
        await self.handle_intent(chat_id, user_id, user_message, intent, send)

    async def detect_intent(self, user_message: str, chat_id: int | None = None) -> IntentResult:
        return await self.router.detect(user_message, chat_id=chat_id)

    async def handle_intent(
        self,
        chat_id: int,
        user_id: int | None,
        user_message: str,
        intent: IntentResult,
        send: SendMessage,
    ) -> None:
        handlers = {
            "new_task": self._handle_new_task,
            "capability_request": self._handle_capability_request,
            "create_directory": self._handle_create_directory,
            "general_question": self._handle_general_question,
            "status_request": self._handle_status,
            "task_clarification": self._handle_clarification,
            "show_diff": self._handle_show_diff,
            "qa_history_request": self._handle_qa_history,
            "path_request": self._handle_path_request,
            "cancel_task": self._handle_cancel,
            "workspace_change": self._handle_workspace_change,
            "direct_agent_message": self._handle_direct_agent_message,
        }
        handler = handlers.get(intent.name, self._handle_general_chat)
        await handler(chat_id, user_id, user_message, intent, send)

    async def _handle_capability_request(
        self,
        chat_id: int,
        user_id: int | None,
        user_message: str,
        intent: IntentResult,
        send: SendMessage,
    ) -> None:
        if intent.extracted_task == "create_directory":
            if self._writes_enabled():
                await send("Так, можу створювати папки всередині активного workspace. Напиши, наприклад: `Створи папку TEST`.")
            else:
                await send("Поки ні: `WRITE_MODE` зараз не дозволяє запис. Увімкни `WRITE_MODE=bypass`, перезапусти bot, і тоді я зможу створювати папки всередині workspace.")
            return

        await send("Можу відповідати на задачі, статус, звернення до PM/Coder/QA і працювати з workspace.")

    async def _handle_create_directory(
        self,
        chat_id: int,
        user_id: int | None,
        user_message: str,
        intent: IntentResult,
        send: SendMessage,
    ) -> None:
        if not intent.target_path:
            await send("Напиши назву папки, наприклад: `Створи папку TEST`.")
            return

        if not self._writes_enabled():
            await send("Не створюю папку, бо запис зараз вимкнений. Постав `WRITE_MODE=bypass` у `.env` і перезапусти bot.")
            return

        workspace = self.tasks.get_workspace(chat_id)
        try:
            target = create_directory(intent.target_path, workspace)
        except ValueError:
            await send("Заблокував створення папки, бо шлях виходить за межі активного workspace.")
            return
        except OSError as exc:
            await send(f"Не зміг створити папку: {exc}")
            return

        await send(f"Готово, папку створено: `{target}`")

    async def _handle_general_question(
        self,
        chat_id: int,
        user_id: int | None,
        user_message: str,
        intent: IntentResult,
        send: SendMessage,
    ) -> None:
        task = self.tasks.get_active(chat_id)
        workspace = self.tasks.get_workspace(chat_id)
        task_context = task.context_for_final_pm() if task else "Активної задачі немає."
        response = await self.agents.pm.run(
            f"""Користувач поставив питання, це НЕ нова задача.
Не запускай workflow і не кажи, що береш у роботу.
Відповідай як PM/координатор системи: прямо, коротко, по-людськи.

Питання користувача:
{user_message}

Активний workspace:
{workspace}

Поточний режим запису:
{self.tasks.write_mode}

Поточний контекст задачі:
{task_context}
"""
        )
        await send(response)

    async def _handle_new_task(
        self,
        chat_id: int,
        user_id: int | None,
        user_message: str,
        intent: IntentResult,
        send: SendMessage,
    ) -> None:
        task_text = intent.extracted_task or user_message
        task = self.tasks.create(chat_id=chat_id, user_id=user_id, task_text=task_text)
        await send("Окей, беру в роботу. Спочатку PM складе план, потім Coder підготує рішення, а QA перевірить.")

        try:
            task.project_context = project_summary(task.workspace, task.raw_user_message)
            self.tasks.write_text(task, "project_context.md", task.project_context)
            self.tasks.save(task)
            await self._run_task(task, send)
        except Exception as exc:
            logger.exception("Task %s failed", task.id)
            task.set_status(TaskStatus.FAILED)
            self.tasks.save(task)
            self.tasks.write_text(task, "error.txt", str(exc))
            await send(f"Задача впала з помилкою: {exc}")

    async def _run_task(self, task: Task, send: SendMessage) -> None:
        task.set_status(TaskStatus.PM_PLANNING)
        self.tasks.save(task)
        self.tasks.add_event(task, "status", task.status.value)

        task.pm_plan = await self.agents.pm.run(task.context_for_pm())
        self.tasks.write_text(task, "pm_plan.md", task.pm_plan)
        self.tasks.add_event(task, "pm_plan", task.pm_plan)
        self.tasks.save(task)
        await send("PM склав план. Передаю Coder.")

        for round_number in range(1, task.max_rounds + 1):
            task.round = round_number
            task.set_status(TaskStatus.CODING)
            self.tasks.save(task)
            self.tasks.add_event(task, "status", f"{task.status.value}:{round_number}")

            coder_result = await self.agents.coder.run(task.context_for_coder())
            task.coder_results.append(coder_result)
            self.tasks.write_text(task, f"coder_round_{round_number}.md", coder_result)
            self.tasks.add_event(task, "coder_result", coder_result)
            self.tasks.save(task)

            actions = parse_actions(coder_result)
            if actions:
                tool_results = execute_actions(
                    actions,
                    task.workspace,
                    self._writes_enabled(),
                    command_timeout_seconds=self.tasks.max_command_timeout_seconds,
                )
                formatted_results = format_tool_results(tool_results)
                task.tool_results.append(formatted_results)
                current_changed_paths = changed_paths(tool_results)
                task.changed_files.extend(current_changed_paths)
                self.tasks.write_text(task, f"tool_results_round_{round_number}.md", formatted_results)
                self.tasks.add_event(task, "tool_results", formatted_results)
                self.tasks.save(task)

                if current_changed_paths:
                    await send("Coder підготував structured actions, Tool Layer застосував зміни. Передаю QA.")
                elif any(result.ok for result in tool_results):
                    await send("Coder підготував structured actions, Tool Layer виконав read/check actions без зміни файлів. Передаю QA.")
                else:
                    await send("Coder підготував actions, але Tool Layer їх заблокував. Передаю QA для оцінки.")
            else:
                task.tool_results.append("- no structured actions returned")
                self.tasks.write_text(task, f"tool_results_round_{round_number}.md", "- no structured actions returned")
                self.tasks.add_event(task, "tool_results", "- no structured actions returned")
                self.tasks.save(task)
                await send("Coder підготував відповідь без structured actions. Передаю QA.")

            task.set_status(TaskStatus.QA_CHECKING)
            self.tasks.save(task)
            self.tasks.add_event(task, "status", task.status.value)

            qa_result = await self.agents.qa.run(task.context_for_qa())
            task.qa_results.append(qa_result)
            self.tasks.write_text(task, f"qa_round_{round_number}.md", qa_result)
            self.tasks.add_event(task, "qa_result", qa_result)
            self.tasks.save(task)

            if self._qa_passed(qa_result):
                task.set_status(TaskStatus.QA_PASSED)
                self.tasks.save(task)
                self.tasks.add_event(task, "status", task.status.value)
                await send("QA дав PASS. Готую фінальний підсумок.")
                break

            task.set_status(TaskStatus.QA_FAILED)
            self.tasks.save(task)
            self.tasks.add_event(task, "status", task.status.value)
            await send("QA знайшов проблему. Повертаю Coder на ще один раунд.")
        else:
            await send("QA не дав PASS за максимальну кількість раундів. Підсумую поточний стан.")

        task.set_status(TaskStatus.FINAL_SUMMARY)
        self.tasks.save(task)

        final_pm_result = await self.agents.final_pm.run(task.context_for_final_pm())
        task.final_summary = self._guard_final_summary(task, final_pm_result)
        self.tasks.write_text(task, "final_summary.md", task.final_summary)
        task.set_status(TaskStatus.COMPLETED)
        self.tasks.save(task)
        self.tasks.add_event(task, "final_summary", task.final_summary)
        await send(task.final_summary)

    async def _handle_status(
        self,
        chat_id: int,
        user_id: int | None,
        user_message: str,
        intent: IntentResult,
        send: SendMessage,
    ) -> None:
        task = self.tasks.get_active(chat_id)
        if not task:
            await send("Активної задачі зараз немає.")
            return

        changed = "\n".join(f"- {path}" for path in task.changed_files[-20:]) or "- поки немає"
        await send(
            f"Поточний статус: {task.status.value}. Раунд: {task.round}/{task.max_rounds}.\n\n"
            f"Змінені файли/шляхи:\n{changed}"
        )

    async def _handle_clarification(
        self,
        chat_id: int,
        user_id: int | None,
        user_message: str,
        intent: IntentResult,
        send: SendMessage,
    ) -> None:
        task = self.tasks.get_active(chat_id)
        if not task:
            await send("Прийняв уточнення, але активної задачі зараз немає.")
            return

        task.constraints.extend(intent.constraints or (user_message,))
        self.tasks.save(task)
        await send("Прийняв уточнення і додав його до constraints активної задачі.")

    async def _handle_show_diff(
        self,
        chat_id: int,
        user_id: int | None,
        user_message: str,
        intent: IntentResult,
        send: SendMessage,
    ) -> None:
        workspace = self.tasks.get_workspace(chat_id)
        status = git_status(workspace)
        diff = git_diff(workspace)
        await send(f"Git status:\n```text\n{status}\n```\n\nGit diff:\n```diff\n{diff}\n```")

    async def _handle_qa_history(
        self,
        chat_id: int,
        user_id: int | None,
        user_message: str,
        intent: IntentResult,
        send: SendMessage,
    ) -> None:
        task = self.tasks.get_active(chat_id)
        if not task:
            await send("Не бачу останньої задачі для цього чату.")
            return

        if not task.qa_results:
            await send("У цій задачі QA ще не запускався.")
            return

        lines = [f"QA history для `{task.id}`:"]
        for index, result in enumerate(task.qa_results, start=1):
            lines.append(f"\nРаунд {index}:\n{result[:1200]}")
        await send("\n".join(lines))

    async def _handle_path_request(
        self,
        chat_id: int,
        user_id: int | None,
        user_message: str,
        intent: IntentResult,
        send: SendMessage,
    ) -> None:
        task = self.tasks.get_active(chat_id)
        workspace = self.tasks.get_workspace(chat_id)

        if self.tasks.write_mode == "read_only":
            log_line = f"\nЛоги останньої задачі: `logs/{task.id}`" if task else ""
            await send(
                "Папка або файли для цієї задачі не створювались. "
                "Поточний MVP працює в read-only/text-only режимі: агенти підготували план і перевірили його логічно, але Tool Layer ще не застосовує зміни.\n\n"
                f"Активний workspace: `{workspace}`"
                f"{log_line}"
            )
            return

        if task and task.changed_files:
            changed = "\n".join(f"- `{path}`" for path in task.changed_files[-20:])
            await send(f"Активний workspace: `{workspace}`\n\nОстанні змінені шляхи:\n{changed}")
            return

        await send(f"Активний workspace: `{workspace}`")

    async def _handle_cancel(
        self,
        chat_id: int,
        user_id: int | None,
        user_message: str,
        intent: IntentResult,
        send: SendMessage,
    ) -> None:
        task = self.tasks.cancel_active(chat_id)
        if not task:
            await send("Активної задачі для скасування немає.")
            return

        await send("Зупинив активну задачу. У цьому MVP зміни у файлах ще не застосовувались.")

    async def _handle_workspace_change(
        self,
        chat_id: int,
        user_id: int | None,
        user_message: str,
        intent: IntentResult,
        send: SendMessage,
    ) -> None:
        if not intent.workspace:
            await send("Не бачу шлях до workspace. Напиши, наприклад: Працюй з проєктом E:\\ai-agents-system")
            return

        workspace = Path(intent.workspace).expanduser()
        self.tasks.set_workspace(chat_id, workspace)
        await send(f"Окей, активний workspace: {workspace}")

    async def _handle_direct_agent_message(
        self,
        chat_id: int,
        user_id: int | None,
        user_message: str,
        intent: IntentResult,
        send: SendMessage,
    ) -> None:
        if not intent.target_agent:
            await send("Не зрозумів, до якого агента звернення.")
            return

        agent = self.agents.by_name(intent.target_agent)
        if not agent:
            await send(f"Агента `{intent.target_agent}` не знайдено.")
            return

        task = self.tasks.get_active(chat_id)
        task_context = task.context_for_final_pm() if task else "Активної задачі немає."
        message = intent.extracted_task or user_message
        response = await agent.run(
            f"""Direct user message to {agent.name}:
{message}

Current task context:
{task_context}
"""
        )
        await send(f"{agent.name}:\n{response}")

    async def _handle_general_chat(
        self,
        chat_id: int,
        user_id: int | None,
        user_message: str,
        intent: IntentResult,
        send: SendMessage,
    ) -> None:
        response = await self.agents.pm.run(
            f"""Користувач написав звичайне повідомлення, це не класифіковано як задача.
Відповідай як PM/координатор системи. Якщо це схоже на намір, попроси коротке уточнення.

Повідомлення:
{user_message}

Активний workspace:
{self.tasks.get_workspace(chat_id)}

Поточний режим запису:
{self.tasks.write_mode}
"""
        )
        await send(response)

    @staticmethod
    def _qa_passed(qa_result: str) -> bool:
        first_line = qa_result.strip().splitlines()[0].upper() if qa_result.strip() else ""
        return "PASS" in first_line and "FAIL" not in first_line

    @staticmethod
    def _guard_final_summary(task: Task, final_pm_result: str) -> str:
        if task.write_mode != "read_only":
            return final_pm_result

        return (
            "Важливо: у поточному MVP система працює в read-only/text-only режимі. "
            "Файли не створювались, папка TEST не створювалась, build/test не запускались. "
            "Команда підготувала тільки план і логічну QA-перевірку.\n\n"
            f"{final_pm_result}"
        )

    def _writes_enabled(self) -> bool:
        return self.tasks.write_mode.lower() in {"bypass", "write", "write_enabled"}
