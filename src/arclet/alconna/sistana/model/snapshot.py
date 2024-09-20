from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Generic, TypeVar

from ..utils.misc import Some, Value

if TYPE_CHECKING:
    from .pattern import SubcommandPattern
    from .pointer import Pointer
    from .track import Mix

T = TypeVar("T")


@dataclass
class SubcommandTraverse:
    subcommand: SubcommandPattern
    ref: Pointer
    mix: Mix

    activated_options: set[str] = field(init=False, default_factory=set)
    # FIXME: 临时措施而已，不够可靠。

    @property
    def satisfied(self):
        return self.mix.satisfied


@dataclass
class AnalyzeSnapshot(Generic[T]):
    traverses: list[SubcommandTraverse] = field(default_factory=list)
    endpoint: Some[Pointer] = None

    @property
    def determined(self):
        return self.endpoint is not None

    def determine(self, endpoint: Pointer):
        self.endpoint = Value(endpoint)
