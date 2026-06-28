from __future__ import annotations

import asyncio
import logging

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
    )
    orchestrator = MainOrchestrator(router=router, agents=agents, task_repository=tasks)
    return orchestrator, settings.max_telegram_message_length


async def _send_chunks(message: Message, text: str, limit: int) -> None:
    for part in split_telegram_message(text, limit):
        await message.answer(part)


async def main() -> None:
    configure_logging()
    settings = load_settings()

    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty. Create .env from .env.example.")

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    orchestrator, message_limit = build_orchestrator()

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
            "- Стоп"
        )

    @dp.message(Command("status"))
    async def status(message: Message) -> None:
        await orchestrator.handle_message(
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else None,
            user_message="статус",
            send=lambda text: _send_chunks(message, text, message_limit),
        )

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
        await orchestrator.handle_message(
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else None,
            user_message=message.text,
            send=lambda text: _send_chunks(message, text, message_limit),
        )

    logger.info("Starting Telegram polling")
    await dp.start_polling(bot)


def run_bot() -> None:
    asyncio.run(main())

