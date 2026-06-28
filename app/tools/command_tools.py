from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.tools.file_tools import is_inside_workspace, resolve_workspace_path


@dataclass(frozen=True)
class CommandAction:
    command: str
    args: tuple[str, ...]
    cwd: str | None = None


ALLOWED_COMMANDS: tuple[CommandAction, ...] = (
    CommandAction("npm", ("run", "build")),
    CommandAction("npm", ("test",)),
    CommandAction("npm", ("run", "test")),
    CommandAction("npm", ("run", "lint")),
    CommandAction("pnpm", ("build",)),
    CommandAction("pnpm", ("test",)),
    CommandAction("pnpm", ("lint",)),
    CommandAction("yarn", ("build",)),
    CommandAction("yarn", ("test",)),
    CommandAction("yarn", ("lint",)),
    CommandAction("go", ("test", "./...")),
    CommandAction("python", ("-m", "compileall", "app", "main.py")),
    CommandAction("python", ("-m", "pytest")),
    CommandAction("pytest", ()),
)


def is_allowed_command(action: CommandAction) -> bool:
    return any(action.command == item.command and action.args == item.args for item in ALLOWED_COMMANDS)


def run_allowed_command(action: CommandAction, workspace: Path, timeout_seconds: int = 120) -> tuple[int, str]:
    if not is_allowed_command(action):
        raise ValueError(f"Command is not allowed: {action.command} {list(action.args)}")

    cwd = workspace
    if action.cwd:
        cwd = resolve_workspace_path(action.cwd, workspace)
        if not is_inside_workspace(cwd, workspace):
            raise ValueError(f"Command cwd is outside workspace: {cwd}")

    completed = subprocess.run(
        [action.command, *action.args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        shell=False,
    )
    output = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
    return completed.returncode, output
