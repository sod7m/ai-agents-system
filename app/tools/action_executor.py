from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.tools.action_schema import (
    ACTION_ADAPTER,
    BaseAction,
    CreateDirectoryAction,
    PatchFileAction,
    ReadFileAction,
    RunCommandAction,
    WriteFileAction,
)
from app.tools.command_tools import CommandAction, run_allowed_command
from app.tools.file_tools import create_directory, patch_file, read_text_file, write_file


@dataclass
class ToolExecutionResult:
    ok: bool
    action_type: str
    path: str | None = None
    message: str = ""


def parse_actions(text: str) -> list[dict[str, Any]]:
    payload = _extract_json_payload(text)
    if not payload:
        return []

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []

    if isinstance(data, dict):
        actions = data.get("actions", [])
    elif isinstance(data, list):
        actions = data
    else:
        return []

    return [action for action in actions if isinstance(action, dict)]


def validate_actions(actions: list[dict[str, Any]]) -> tuple[list[BaseAction], list[ToolExecutionResult]]:
    valid_actions: list[BaseAction] = []
    errors: list[ToolExecutionResult] = []

    for action in actions:
        action_type = str(action.get("type", "unknown"))
        try:
            valid_actions.append(ACTION_ADAPTER.validate_python(action))
        except ValidationError as exc:
            errors.append(ToolExecutionResult(False, action_type, None, exc.errors()[0]["msg"]))

    return valid_actions, errors


def execute_actions(
    actions: list[dict[str, Any]],
    workspace: Path,
    writes_enabled: bool,
    command_timeout_seconds: int = 120,
) -> list[ToolExecutionResult]:
    valid_actions, results = validate_actions(actions)

    for action in valid_actions:
        if isinstance(action, CreateDirectoryAction):
            result = _execute_create_directory(action.path, workspace, writes_enabled)
        elif isinstance(action, WriteFileAction):
            result = _execute_write_file(action.path, action.content, workspace, writes_enabled)
        elif isinstance(action, PatchFileAction):
            result = _execute_patch_file(action.path, action.old_text, action.new_text, workspace, writes_enabled)
        elif isinstance(action, ReadFileAction):
            result = _execute_read_file(action.path, workspace)
        elif isinstance(action, RunCommandAction):
            result = _execute_run_command(action, workspace, command_timeout_seconds)
        else:
            result = ToolExecutionResult(False, "unknown", None, "Unsupported action type")

        results.append(result)

    return results


def changed_paths(results: list[ToolExecutionResult]) -> list[str]:
    return [
        result.path
        for result in results
        if result.ok and result.path and result.action_type in {"create_directory", "write_file", "patch_file"}
    ]


def format_tool_results(results: list[ToolExecutionResult]) -> str:
    if not results:
        return "- no tool actions"

    lines = []
    for result in results:
        status = "OK" if result.ok else "BLOCKED"
        path = f" {result.path}" if result.path else ""
        lines.append(f"- {status} {result.action_type}{path}: {result.message}")
    return "\n".join(lines)


def _execute_create_directory(path: str, workspace: Path, writes_enabled: bool) -> ToolExecutionResult:
    if not writes_enabled:
        return ToolExecutionResult(False, "create_directory", path, "Writes are disabled")
    if not path:
        return ToolExecutionResult(False, "create_directory", None, "Missing path")

    try:
        target = create_directory(path, workspace)
    except (OSError, ValueError) as exc:
        return ToolExecutionResult(False, "create_directory", path, str(exc))

    return ToolExecutionResult(True, "create_directory", str(target), "Directory created")


def _execute_write_file(path: str, content: Any, workspace: Path, writes_enabled: bool) -> ToolExecutionResult:
    if not writes_enabled:
        return ToolExecutionResult(False, "write_file", path, "Writes are disabled")
    if not path:
        return ToolExecutionResult(False, "write_file", None, "Missing path")
    if not isinstance(content, str):
        return ToolExecutionResult(False, "write_file", path, "Missing string content")

    try:
        target = write_file(path, content, workspace)
    except (OSError, ValueError) as exc:
        return ToolExecutionResult(False, "write_file", path, str(exc))

    return ToolExecutionResult(True, "write_file", str(target), "File written")


def _execute_patch_file(path: str, old_text: str, new_text: str, workspace: Path, writes_enabled: bool) -> ToolExecutionResult:
    if not writes_enabled:
        return ToolExecutionResult(False, "patch_file", path, "Writes are disabled")

    try:
        target = patch_file(path, old_text, new_text, workspace)
    except (OSError, ValueError) as exc:
        return ToolExecutionResult(False, "patch_file", path, str(exc))

    return ToolExecutionResult(True, "patch_file", str(target), "File patched")


def _execute_read_file(path: str, workspace: Path) -> ToolExecutionResult:
    try:
        content = read_text_file(path, workspace, max_bytes=120_000)
    except (OSError, ValueError) as exc:
        return ToolExecutionResult(False, "read_file", path, str(exc))

    return ToolExecutionResult(True, "read_file", path, f"File content:\n{content[:8000]}")


def _execute_run_command(action: RunCommandAction, workspace: Path, timeout_seconds: int) -> ToolExecutionResult:
    command_action = CommandAction(command=action.command, args=tuple(action.args), cwd=action.cwd)
    try:
        returncode, output = run_allowed_command(command_action, workspace, timeout_seconds)
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        return ToolExecutionResult(False, "run_command", f"{action.command} {' '.join(action.args)}".strip(), str(exc))

    status = "Command passed" if returncode == 0 else f"Command failed with exit code {returncode}"
    if output:
        status = f"{status}\n{output[:6000]}"
    return ToolExecutionResult(returncode == 0, "run_command", f"{action.command} {' '.join(action.args)}".strip(), status)


def _extract_json_payload(text: str) -> str | None:
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    start_candidates = [idx for idx in (text.find("{"), text.find("[")) if idx != -1]
    if not start_candidates:
        return None

    start = min(start_candidates)
    end_char = "}" if text[start] == "{" else "]"
    end = text.rfind(end_char)
    if end <= start:
        return None

    return text[start : end + 1].strip()
