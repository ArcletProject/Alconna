from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING
from tarina import ContextModel

from .exceptions import PauseTriggered
from .manager import command_manager
from .output import output_manager
from .config import config

if TYPE_CHECKING:
    from .core import Alconna


@dataclass(eq=True, frozen=True, unsafe_hash=True)
class Prompt:
    text: str = field(hash=True)
    can_use: bool = field(default=True, hash=False)
    removal_prefix: str | None = field(default=None, hash=False)


class CompInterface:
    """

    ```python
    from arclet.alconna import Alconna, CompInterface

    alc = Alconna(...)

    with CompInterface(alc) as comp:
        res = alc.parse("test")

    if comp.available:
        print(comp.current())
        print(comp.tab())
        with comp:
            res = comp.enter()
        if comp.available:
            print(comp.current())
            print(comp.tab())
            with comp:
                res = comp.enter()
            ...
    ```

    """
    index: int
    prompts: list[Prompt]

    def __init__(self, source: Alconna):
        self.source = command_manager.require(source)
        self.index = 0
        self.prompts = []
        self._token = None

    @property
    def available(self):
        return bool(self.prompts)

    def current(self):
        if not self.prompts:
            raise ValueError("No prompt available.")
        return self.prompts[self.index].text

    def tab(self, offset: int = 1):
        if not self.prompts:
            raise ValueError("No prompt available.")
        self.index += offset
        self.index %= len(self.prompts)
        return self.prompts[self.index].text

    def enter(self, content: Any | None = None):
        if content:
            self.source.container.rebuild(content)
            self.clear()
            return self.source.process()
        if not self.prompts:
            raise ValueError("No prompt available.")
        prompt = self.prompts[self.index]
        if not prompt.can_use:
            raise ValueError("This prompt cannot be used.")
        if prompt.removal_prefix:
            last = self.source.container.bak_data[-1]
            self.source.container.bak_data[-1] = last[:last.rfind(prompt.removal_prefix)]
        self.source.container.rebuild(prompt.text)
        self.clear()
        return self.source.process()

    def push(self, *suggests: Prompt):
        self.prompts.extend(suggests)
        return self

    def clear(self):
        self.index = 0
        self.prompts.clear()
        self.source.reset()
        return self

    def __repr__(self):
        lines = [
            f"{'>' if self.index == index else '*'} {sug.text}"
            for index, sug in enumerate(self.prompts)
        ]
        return (
            f"{config.lang.common_completion_node}\n"
            + "\n".join(lines)
        )

    def send_prompt(self):
        return output_manager.send(self.source.command.name, lambda: self.__repr__())

    def __enter__(self):
        self._token = comp_ctx.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        comp_ctx.reset(self._token)
        if exc_type is PauseTriggered:
            self.clear()
            self.push(*exc_val.args[0])
            return True


comp_ctx: ContextModel[CompInterface] = ContextModel("comp_ctx")
