from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app.agents.factory import AgentPool
from app.config import load_settings
from app.llm.llama_cpp_provider import LlamaCppProvider
from app.orchestrator.main_orchestrator import MainOrchestrator
from app.router.conversation_router import ConversationRouter
from app.storage.task_repository import TaskRepository
from app.telegram.message_formatter import split_telegram_message
from app.utils.logger import configure_logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueuedMessage:
    chat_id: int
    user_id: int | None
    text: str


class BackgroundTaskQueue:
    def __init__(self, orchestrator: MainOrchestrator, bot: Bot, message_limit: int) -> None:
        self.orchestrator = orchestrator
        self.bot = bot
        self.message_limit = message_limit
        self.queue: asyncio.Queue[QueuedMessage] = asyncio.Queue()
        self.pending_by_chat: dict[int, int] = defaultdict(int)
        self.running_by_chat: set[int] = set()

    def start(self) -> asyncio.Task:
        return asyncio.create_task(self._worker(), name="ai-team-runtime-worker")

    async def enqueue(self, item: QueuedMessage) -> int:
        self.pending_by_chat[item.chat_id] += 1
        await self.queue.put(item)
        return self.pending_by_chat[item.chat_id]

    def status_for_chat(self, chat_id: int) -> str | None:
        pending = self.pending_by_chat.get(chat_id, 0)
        running = chat_id in self.running_by_chat
        if not pending and not running:
            return None

        parts = []
        if running:
            parts.append("є задача в роботі")
        if pending:
            parts.append(f"у черзі: {pending}")
        return ", ".join(parts)

    async def _worker(self) -> None:
        while True:
            item = await self.queue.get()
            self.pending_by_chat[item.chat_id] = max(0, self.pending_by_chat[item.chat_id] - 1)
            self.running_by_chat.add(item.chat_id)

            async def send(text: str) -> None:
                await _send_chat_chunks(self.bot, item.chat_id, text, self.message_limit)

            try:
                await self.orchestrator.handle_message(
                    chat_id=item.chat_id,
                    user_id=item.user_id,
                    user_message=item.text,
                    send=send,
                )
            except Exception:
                logger.exception("Background task failed")
                await send("Задача впала з неочікуваною помилкою. Деталі є в логах.")
            finally:
                self.running_by_chat.discard(item.chat_id)
                self.queue.task_done()


def build_orchestrator() -> tuple[MainOrchestrator, int]:
    settings = load_settings()
    llm = LlamaCppProvider(settings.llama_base_url, settings.llama_model)
    agents = AgentPool(llm)
    router = ConversationRouter()
    tasks = TaskRepository(
        logs_dir=settings.logs_dir,
        default_workspace=settings.default_workspace,
        max_rounds=settings.max_agent_rounds,
        approval_mode=settings.approval_mode,
        write_mode=settings.write_mode,
        max_command_timeout_seconds=settings.max_command_timeout_seconds,
        db_path=settings.db_path,
    )
    orchestrator = MainOrchestrator(router=router, agents=agents, task_repository=tasks)
    return orchestrator, settings.max_telegram_message_length


async def _send_chunks(message: Message, text: str, limit: int) -> None:
    for part in split_telegram_message(text, limit):
        await message.answer(part)


async def _send_chat_chunks(bot: Bot, chat_id: int, text: str, limit: int) -> None:
    for part in split_telegram_message(text, limit):
        await bot.send_message(chat_id=chat_id, text=part)


async def main() -> None:
    configure_logging()
    settings = load_settings()

    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty. Create .env from .env.example.")

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    orchestrator, message_limit = build_orchestrator()
    task_queue = BackgroundTaskQueue(orchestrator, bot, message_limit)
    worker_task = task_queue.start()

    @dp.message(Command("start"))
    async def start(message: Message) -> None:
        await message.answer(
            "Привіт. Я AI Team Runtime: один Telegram bot, всередині PM/Coder/QA agents. "
            "Напиши задачу природною мовою або звернись напряму: `QA, перевір план`."
        )

    @dp.message(Command("help"))
    async def help_command(message: Message) -> None:
        await message.answer(
            "Приклади:\n"
            "- Працюй з проєктом E:\\ai-agents-system\n"
            "- Зроби сторінку логіну на React і Tailwind\n"
            "- Як там?\n"
            "- QA, перевір чи нормальний план\n"
            "- Стоп\n"
            "- Покажи зміни\n"
            "- /tasks"
        )

    @dp.message(Command("status"))
    async def status(message: Message) -> None:
        queue_status = task_queue.status_for_chat(message.chat.id)
        if queue_status:
            await message.answer(f"Черга: {queue_status}")
        await orchestrator.handle_message(
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else None,
            user_message="статус",
            send=lambda text: _send_chunks(message, text, message_limit),
        )

    @dp.message(Command("diff"))
    async def diff(message: Message) -> None:
        await orchestrator.handle_message(
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else None,
            user_message="покажи зміни",
            send=lambda text: _send_chunks(message, text, message_limit),
        )

    @dp.message(Command("tasks"))
    async def tasks(message: Message) -> None:
        recent = orchestrator.tasks.list_recent(message.chat.id, limit=5)
        if not recent:
            await message.answer("Задач ще немає.")
            return

        lines = ["Останні задачі:"]
        for task in recent:
            lines.append(f"- `{task.id}`: {task.status.value}, раунд {task.round}/{task.max_rounds}")
        await message.answer("\n".join(lines))

    @dp.message(Command("workspace"))
    async def workspace(message: Message, command: CommandObject) -> None:
        if not command.args:
            await message.answer("Напиши так: /workspace E:\\ai-agents-system")
            return

        await orchestrator.handle_message(
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else None,
            user_message=f"працюй з проєктом {command.args}",
            send=lambda text: _send_chunks(message, text, message_limit),
        )

    @dp.message(F.text)
    async def text_message(message: Message) -> None:
        assert message.text is not None
        intent = await orchestrator.detect_intent(message.text, message.chat.id)
        if intent.name == "new_task":
            pending = await task_queue.enqueue(
                QueuedMessage(
                    chat_id=message.chat.id,
                    user_id=message.from_user.id if message.from_user else None,
                    text=message.text,
                )
            )
            await message.answer(f"Поставив задачу в чергу. Позиція в черзі: {pending}.")
            return

        await orchestrator.handle_intent(
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else None,
            user_message=message.text,
            intent=intent,
            send=lambda text: _send_chunks(message, text, message_limit),
        )

    logger.info("Starting Telegram polling")
    try:
        await dp.start_polling(bot)
    finally:
        worker_task.cancel()


def run_bot() -> None:
    asyncio.run(main())
