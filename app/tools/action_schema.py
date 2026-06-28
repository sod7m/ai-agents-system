from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class BaseAction(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateDirectoryAction(BaseAction):
    type: Literal["create_directory", "mkdir"]
    path: str = Field(min_length=1)


class WriteFileAction(BaseAction):
    type: Literal["write_file", "create_file"]
    path: str = Field(min_length=1)
    content: str


class PatchFileAction(BaseAction):
    type: Literal["patch_file"]
    path: str = Field(min_length=1)
    old_text: str = Field(min_length=1)
    new_text: str


class ReadFileAction(BaseAction):
    type: Literal["read_file"]
    path: str = Field(min_length=1)


class RunCommandAction(BaseAction):
    type: Literal["run_command"]
    command: str = Field(min_length=1)
    args: list[str] = Field(default_factory=list)
    cwd: str | None = None


Action = Annotated[
    Union[CreateDirectoryAction, WriteFileAction, PatchFileAction, ReadFileAction, RunCommandAction],
    Field(discriminator="type"),
]

ACTION_ADAPTER: TypeAdapter[Action] = TypeAdapter(Action)
