from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Generic, TypeVar

from ..utils.misc import Some, Value

if TYPE_CHECKING:
    from .pattern import SubcommandPattern, OptionPattern
    from .pointer import Pointer
    from .track import Mix, Track

T = TypeVar("T")


class OptionTraverse:
    __slots__ = ("trigger", "is_compact", "completed", "option", "track")

    trigger: str
    is_compact: bool
    completed: bool
    option: OptionPattern
    track: Track

    def __init__(self, trigger: str, is_compact: bool, completed: bool, option: OptionPattern, track: Track):
        self.trigger = trigger
        self.is_compact = is_compact
        self.completed = completed
        self.option = option
        self.track = track


class IndexedOptionTraversesRecord:
    __slots__ = ("traverses", "_by_trigger", "_by_keyword", "_count")

    traverses: list[OptionTraverse]

    _by_trigger: dict[str, list[OptionTraverse]]
    _by_keyword: dict[str, list[OptionTraverse]]
    _count: defaultdict[str, int]

    def __init__(self, traverses: list[OptionTraverse] | None = None):
        self.traverses = traverses or []
        self._by_trigger = {}
        self._by_keyword = {}
        self._count = defaultdict(lambda: 0)

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


class SubcommandTraverse:
    __slots__ = ("subcommand", "trigger", "ref", "mix", "option_traverses")

    subcommand: SubcommandPattern
    trigger: str
    ref: Pointer
    mix: Mix
    option_traverses: IndexedOptionTraversesRecord

    def __init__(self, subcommand: SubcommandPattern, trigger: str, ref: Pointer, mix: Mix):
        self.subcommand = subcommand
        self.trigger = trigger
        self.ref = ref
        self.mix = mix
        self.option_traverses = IndexedOptionTraversesRecord()


class AnalyzeSnapshot(Generic[T]):
    __slots__ = ("traverses", "endpoint")

    traverses: list[SubcommandTraverse]
    endpoint: Some[Pointer]

    def __init__(self, traverses: list[SubcommandTraverse] | None = None, endpoint: Some[Pointer] = None):
        self.traverses = traverses or []
        self.endpoint = endpoint

    @property
    def determined(self):
        return self.endpoint is not None

    def determine(self, endpoint: Pointer):
        self.endpoint = Value(endpoint)
