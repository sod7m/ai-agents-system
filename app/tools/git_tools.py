from __future__ import annotations

import subprocess
from pathlib import Path


def git_status(workspace: Path) -> str:
    return _run_git(["status", "--short"], workspace)


def git_diff(workspace: Path, max_chars: int = 12_000) -> str:
    diff = _run_git(["diff", "--", "."], workspace)
    if len(diff) > max_chars:
        return diff[:max_chars] + "\n... diff truncated ..."
    return diff


def _run_git(args: list[str], workspace: Path) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        shell=False,
    )
    output = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
    if completed.returncode != 0:
        return output or f"git {' '.join(args)} failed"
    return output or "clean"
