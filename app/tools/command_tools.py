from __future__ import annotations

from dataclasses import dataclass


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
    CommandAction("python", ("-m", "pytest")),
    CommandAction("pytest", ()),
)


def is_allowed_command(action: CommandAction) -> bool:
    return any(action.command == item.command and action.args == item.args for item in ALLOWED_COMMANDS)

