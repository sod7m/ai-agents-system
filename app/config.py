from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    llama_base_url: str
    llama_model: str
    default_workspace: Path
    max_agent_rounds: int
    max_telegram_message_length: int
    max_command_timeout_seconds: int
    approval_mode: str
    auto_progress_updates: bool
    router_mode: str
    write_mode: str
    logs_dir: Path
    db_path: Path


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def load_settings() -> Settings:
    load_dotenv(override=True, encoding="utf-8-sig")
    root_dir = Path(__file__).resolve().parent.parent

    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        llama_base_url=os.getenv("LLAMA_BASE_URL", "http://127.0.0.1:8081/v1").strip(),
        llama_model=os.getenv("LLAMA_MODEL", "local-model").strip(),
        default_workspace=Path(os.getenv("DEFAULT_WORKSPACE", str(root_dir))).expanduser(),
        max_agent_rounds=_int_env("MAX_AGENT_ROUNDS", 3),
        max_telegram_message_length=_int_env("MAX_TELEGRAM_MESSAGE_LENGTH", 3900),
        max_command_timeout_seconds=_int_env("MAX_COMMAND_TIMEOUT_SECONDS", 120),
        approval_mode=os.getenv("APPROVAL_MODE", "bypass").strip(),
        auto_progress_updates=_bool_env("AUTO_PROGRESS_UPDATES", True),
        router_mode=os.getenv("ROUTER_MODE", "hybrid").strip(),
        write_mode=os.getenv("WRITE_MODE", "read_only").strip(),
        logs_dir=root_dir / "logs",
        db_path=root_dir / "runtime.sqlite3",
    )
