from __future__ import annotations

from pathlib import Path


def is_inside_workspace(path: Path, workspace: Path) -> bool:
    resolved_path = path.resolve()
    resolved_workspace = workspace.resolve()
    return resolved_path == resolved_workspace or resolved_workspace in resolved_path.parents


def resolve_workspace_path(path_text: str, workspace: Path) -> Path:
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = workspace / path
    return path.resolve()


def create_directory(path_text: str, workspace: Path) -> Path:
    target = resolve_workspace_path(path_text, workspace)
    if not is_inside_workspace(target, workspace):
        raise ValueError(f"Path is outside workspace: {target}")

    target.mkdir(parents=True, exist_ok=True)
    return target
