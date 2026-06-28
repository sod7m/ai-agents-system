from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ToolRisk(str, Enum):
    SAFE = "safe"
    CAUTION = "caution"
    DANGEROUS = "dangerous"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    risk: ToolRisk
    enabled: bool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {
            "list_files": ToolSpec("list_files", ToolRisk.SAFE, True),
            "read_file": ToolSpec("read_file", ToolRisk.SAFE, True),
            "project_summary": ToolSpec("project_summary", ToolRisk.SAFE, True),
            "create_directory": ToolSpec("create_directory", ToolRisk.SAFE, True),
            "write_file": ToolSpec("write_file", ToolRisk.SAFE, False),
            "patch_file": ToolSpec("patch_file", ToolRisk.SAFE, True),
            "run_command": ToolSpec("run_command", ToolRisk.SAFE, True),
            "git_status": ToolSpec("git_status", ToolRisk.SAFE, True),
            "git_diff": ToolSpec("git_diff", ToolRisk.SAFE, True),
        }

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def enabled_tools(self) -> list[ToolSpec]:
        return [tool for tool in self._tools.values() if tool.enabled]
