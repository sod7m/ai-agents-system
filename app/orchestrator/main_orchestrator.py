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
        intent = await self.router.detect(user_message, chat_id=chat_id)

        handlers = {
            "new_task": self._handle_new_task,
            "status_request": self._handle_status,
            "task_clarification": self._handle_clarification,
            "show_diff": self._handle_show_diff,
            "cancel_task": self._handle_cancel,
            "workspace_change": self._handle_workspace_change,
            "direct_agent_message": self._handle_direct_agent_message,
        }
        handler = handlers.get(intent.name, self._handle_general_chat)
        await handler(chat_id, user_id, user_message, intent, send)

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

        task.pm_plan = await self.agents.pm.run(task.context_for_pm())
        self.tasks.write_text(task, "pm_plan.md", task.pm_plan)
        self.tasks.save(task)
        await send("PM склав план. Передаю Coder.")

        for round_number in range(1, task.max_rounds + 1):
            task.round = round_number
            task.set_status(TaskStatus.CODING)
            self.tasks.save(task)

            coder_result = await self.agents.coder.run(task.context_for_coder())
            task.coder_results.append(coder_result)
            self.tasks.write_text(task, f"coder_round_{round_number}.md", coder_result)
            self.tasks.save(task)
            await send("Coder підготував рішення. Передаю QA.")

            task.set_status(TaskStatus.QA_CHECKING)
            self.tasks.save(task)

            qa_result = await self.agents.qa.run(task.context_for_qa())
            task.qa_results.append(qa_result)
            self.tasks.write_text(task, f"qa_round_{round_number}.md", qa_result)
            self.tasks.save(task)

            if self._qa_passed(qa_result):
                task.set_status(TaskStatus.QA_PASSED)
                await send("QA дав PASS. Готую фінальний підсумок.")
                break

            task.set_status(TaskStatus.QA_FAILED)
            await send("QA знайшов проблему. Повертаю Coder на ще один раунд.")
        else:
            await send("QA не дав PASS за максимальну кількість раундів. Підсумую поточний стан.")

        task.set_status(TaskStatus.FINAL_SUMMARY)
        self.tasks.save(task)

        task.final_summary = await self.agents.final_pm.run(task.context_for_final_pm())
        self.tasks.write_text(task, "final_summary.md", task.final_summary)
        task.set_status(TaskStatus.COMPLETED)
        self.tasks.save(task)
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

        await send(f"Поточний статус: {task.status.value}. Раунд: {task.round}/{task.max_rounds}.")

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
        await send("У поточному MVP файлова зміна ще вимкнена, тому diff поки немає. Наступний етап - read-only workspace, потім patch/write tools.")

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
        await send("Я готовий. Напиши задачу природною мовою, наприклад: `Зроби сторінку логіну на React і Tailwind`.")

    @staticmethod
    def _qa_passed(qa_result: str) -> bool:
        first_line = qa_result.strip().splitlines()[0].upper() if qa_result.strip() else ""
        return "PASS" in first_line and "FAIL" not in first_line

