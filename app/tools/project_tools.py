from __future__ import annotations

from pathlib import Path

from app.tools.file_tools import list_files, read_text_file


def project_summary(workspace: Path) -> str:
    files = list_files(workspace, max_files=120)
    interesting = []

    for candidate in ("package.json", "pyproject.toml", "requirements.txt", "README.md"):
        if candidate in files:
            try:
                content = read_text_file(candidate, workspace, max_bytes=40_000)
            except (OSError, ValueError):
                continue
            interesting.append(f"## {candidate}\n{content[:4000]}")

    files_text = "\n".join(f"- {item}" for item in files[:120]) or "- no files found"
    interesting_text = "\n\n".join(interesting) or "No known project metadata files found."

    return f"""Workspace:
{workspace}

Files:
{files_text}

Detected metadata:
{interesting_text}
"""
