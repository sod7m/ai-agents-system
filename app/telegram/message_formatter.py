from __future__ import annotations

from app.utils.text_splitter import split_text


def split_telegram_message(text: str, limit: int) -> list[str]:
    return split_text(text.strip() or "...", limit)

