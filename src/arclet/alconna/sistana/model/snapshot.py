from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, TypeVar


if TYPE_CHECKING:
    from .track import Mix
    from .pattern import OptionPattern, SubcommandPattern
    from .pointer import Pointer

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
    cache: dict[str, Any] = field(default_factory=dict)
