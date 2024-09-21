from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Generic, TypeVar

from ..utils.misc import Some, Value

if TYPE_CHECKING:
    from .pattern import SubcommandPattern, OptionPattern
    from .pointer import Pointer
    from .track import Mix, Track

T = TypeVar("T")


@dataclass
class OptionTraverse:
    trigger: str
    is_compact: bool
    completed: bool
    option: OptionPattern
    track: Track


@dataclass
class IndexedOptionTraversesRecord:
    traverses: list[OptionTraverse] = field(default_factory=list)

    _by_trigger: dict[str, list[OptionTraverse]] = field(default_factory=dict, repr=False)
    _by_keyword: dict[str, list[OptionTraverse]] = field(default_factory=dict, repr=False)

    def append(self, traverse: OptionTraverse):
        self.traverses.append(traverse)
        self._by_trigger.setdefault(traverse.trigger, []).append(traverse)
        self._by_keyword.setdefault(traverse.option.keyword, []).append(traverse)

    def by_trigger(self, trigger: str):
        return self._by_trigger.get(trigger, [])

    def by_keyword(self, keyword: str):
        return self._by_keyword.get(keyword, [])

    def __getitem__(self, ix: int):
        return self.traverses[ix]

    def __contains__(self, keyword: str):
        return keyword in self._by_keyword


@dataclass
class SubcommandTraverse:
    subcommand: SubcommandPattern
    ref: Pointer
    mix: Mix
    option_traverses: IndexedOptionTraversesRecord = field(default_factory=IndexedOptionTraversesRecord)

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
