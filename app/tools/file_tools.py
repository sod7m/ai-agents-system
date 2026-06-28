from __future__ import annotations

from pathlib import Path

MAX_TEXT_FILE_BYTES = 300_000


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


def write_file(path_text: str, content: str, workspace: Path) -> Path:
    target = resolve_workspace_path(path_text, workspace)
    if not is_inside_workspace(target, workspace):
        raise ValueError(f"Path is outside workspace: {target}")

    if target.name.lower() == ".env":
        raise ValueError(".env edits are blocked")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    return target


def patch_file(path_text: str, old_text: str, new_text: str, workspace: Path) -> Path:
    target = resolve_workspace_path(path_text, workspace)
    if not is_inside_workspace(target, workspace):
        raise ValueError(f"Path is outside workspace: {target}")

    if target.name.lower() == ".env":
        raise ValueError(".env edits are blocked")

    content = target.read_text(encoding="utf-8")
    occurrences = content.count(old_text)
    if occurrences == 0:
        raise ValueError("old_text was not found in file")
    if occurrences > 1:
        raise ValueError("old_text is not unique in file")

    target.write_text(content.replace(old_text, new_text, 1), encoding="utf-8", newline="\n")
    return target


def read_text_file(path_text: str, workspace: Path, max_bytes: int = MAX_TEXT_FILE_BYTES) -> str:
    target = resolve_workspace_path(path_text, workspace)
    if not is_inside_workspace(target, workspace):
        raise ValueError(f"Path is outside workspace: {target}")

    data = target.read_bytes()
    if len(data) > max_bytes:
        raise ValueError(f"File is too large to read: {target}")

    return data.decode("utf-8", errors="replace")


def list_files(workspace: Path, max_files: int = 200) -> list[str]:
    ignored_dirs = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache", "logs"}
    files: list[str] = []
    root = workspace.resolve()

    for path in root.rglob("*"):
        if len(files) >= max_files:
            break
        if any(part in ignored_dirs for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            files.append(path.relative_to(root).as_posix())

    return files
