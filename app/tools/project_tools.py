from __future__ import annotations

import re
from pathlib import Path

from app.tools.file_tools import list_files, read_text_file

TEXT_EXTENSIONS = {
    ".css",
    ".html",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".py",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
}


def project_summary(workspace: Path, user_task: str | None = None) -> str:
    files = list_files(workspace, max_files=120)
    interesting = []

    for candidate in ("package.json", "pyproject.toml", "requirements.txt", "README.md"):
        if candidate in files:
            try:
                content = read_text_file(candidate, workspace, max_bytes=40_000)
            except (OSError, ValueError):
                continue
            interesting.append(f"## {candidate}\n{content[:4000]}")

    relevant_files = _select_relevant_files(files, user_task or "")
    relevant_contents = []
    for file_path in relevant_files:
        try:
            content = read_text_file(file_path, workspace, max_bytes=80_000)
        except (OSError, ValueError):
            continue
        relevant_contents.append(f"## {file_path}\n```text\n{content[:8000]}\n```")

    files_text = "\n".join(f"- {item}" for item in files[:120]) or "- no files found"
    interesting_text = "\n\n".join(interesting) or "No known project metadata files found."
    relevant_text = "\n\n".join(relevant_contents) or "No relevant file contents selected."

    return f"""Workspace:
{workspace}

Files:
{files_text}

Detected metadata:
{interesting_text}

Relevant file contents:
{relevant_text}
"""


def _select_relevant_files(files: list[str], user_task: str, limit: int = 6) -> list[str]:
    task_tokens = {token.lower() for token in re.findall(r"[A-Za-zА-Яа-яІіЇїЄєҐґ0-9_-]+", user_task) if len(token) >= 3}
    explicit_paths = set(re.findall(r"[A-Za-z0-9_.\-/\\]+\\.[A-Za-z0-9]+", user_task))
    scored: list[tuple[int, str]] = []

    for file_path in files:
        path = Path(file_path)
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue

        normalized = file_path.replace("\\", "/").lower()
        score = 0

        if file_path in explicit_paths or normalized in {item.replace("\\", "/").lower() for item in explicit_paths}:
            score += 100

        path_tokens = {token.lower() for token in re.findall(r"[A-Za-zА-Яа-яІіЇїЄєҐґ0-9_-]+", normalized)}
        score += 10 * len(task_tokens.intersection(path_tokens))

        if path.name.lower() in {"package.json", "readme.md", "app.tsx", "app.jsx", "main.tsx", "main.jsx", "index.html"}:
            score += 5

        if score > 0:
            scored.append((score, file_path))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [file_path for _, file_path in scored[:limit]]
