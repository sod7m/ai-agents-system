from __future__ import annotations


def split_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    current = ""

    for paragraph in text.splitlines(keepends=True):
        if len(current) + len(paragraph) <= limit:
            current += paragraph
            continue

        if current:
            parts.append(current.rstrip())
            current = ""

        while len(paragraph) > limit:
            parts.append(paragraph[:limit].rstrip())
            paragraph = paragraph[limit:]

        current = paragraph

    if current:
        parts.append(current.rstrip())

    return parts

