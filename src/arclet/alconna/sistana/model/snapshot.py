from __future__ import annotations

from collections import defaultdict
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
    _count: defaultdict[str, int] = field(default_factory=lambda: defaultdict(lambda: 0), repr=False)

    def append(self, traverse: OptionTraverse):
        self.traverses.append(traverse)

        if traverse.trigger in self._by_trigger:
            self._by_trigger[traverse.trigger].append(traverse)
        else:
            self._by_trigger[traverse.trigger] = [traverse]
        
        if traverse.option.keyword in self._by_keyword:
            self._by_keyword[traverse.option.keyword].append(traverse)
        else:
            self._by_keyword[traverse.option.keyword] = [traverse]

        self._count[traverse.option.keyword] += 1

    def by_trigger(self, trigger: str):
        return self._by_trigger.get(trigger, [])

    def by_keyword(self, keyword: str):
        return self._by_keyword.get(keyword, [])

    def count(self, keyword: str):
        return self._count[keyword]

    def __getitem__(self, ix: int):
        return self.traverses[ix]

    def __contains__(self, keyword: str):
        return keyword in self._by_keyword


@dataclass
class SubcommandTraverse:
    subcommand: SubcommandPattern
    trigger: str
    ref: Pointer
    mix: Mix
    option_traverses: IndexedOptionTraversesRecord = field(default_factory=IndexedOptionTraversesRecord)


@dataclass
class AnalyzeSnapshot(Generic[T]):
    traverses: list[SubcommandTraverse] = field(default_factory=list)
    endpoint: Some[Pointer] = None

    @property
    def determined(self):
        return self.endpoint is not None

    def determine(self, endpoint: Pointer):
        self.endpoint = Value(endpoint)
