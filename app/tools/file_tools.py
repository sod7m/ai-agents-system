from __future__ import annotations

from pathlib import Path


def is_inside_workspace(path: Path, workspace: Path) -> bool:
    resolved_path = path.resolve()
    resolved_workspace = workspace.resolve()
    return resolved_path == resolved_workspace or resolved_workspace in resolved_path.parents

