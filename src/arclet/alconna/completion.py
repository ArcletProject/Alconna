from __future__ import annotations


from dataclasses import dataclass, field
from typing import Any

from .manager import command_manager
from .output import output_manager
from .config import config


@dataclass(eq=True, frozen=True)
class Prompt:
    text: str
    can_use: bool = field(default=True)


class CompInterface:
    _source: str
    index: int
    prompts: list[Prompt]

    def __init__(self, source: str):
        self._source = source
        self.index = 0
        self.prompts = []

    @property
    def source(self):
        return command_manager.get_command(self._source)

    def tab(self, offset: int = 1):
        self.index += offset
        self.index %= len(self.prompts)
        return self.prompts[self.index].text

    def enter(self, content: Any | None = None):
        if content:
            ...
        prompt = self.prompts[self.index]
        if not prompt.can_use:
            raise ValueError("This prompt cannot be used.")

    def push(self, *suggests: Prompt):
        self.prompts.extend(suggests)
        return self

    def __repr__(self):
        return (
            f"{config.lang.common_completion_arg}\n* "
            + "\n* ".join([sug.text for sug in self.prompts])
        )

    def send_prompt(self):
        return output_manager.send(self.source.name, lambda: self.__repr__())
