from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Mapping

from elaina_segment import SEPARATORS
from elaina_triehard import TrieHard

from .pointer import Pointer
from .receiver import Rx
from .track import Preset

if TYPE_CHECKING:
    pass


@dataclass
class SubcommandPattern:
    header: str
    preset: Preset
    options: Mapping[str, OptionPattern] = field(default_factory=dict)
    subcommands: Mapping[str, SubcommandPattern] = field(default_factory=dict)

    soft_keyword: bool = False
    separators: str = SEPARATORS

    prefixes: TrieHard | None = field(default=None)  # 后面改成 init=False
    compacts: TrieHard | None = field(default=None)  # 后面改成 init=False
    compact_header: bool = False
    satisfy_previous: bool = True

    @property
    def root_ref(self):
        return Pointer().subcommand(self.header)

    def new_snapshot(self):
        from .snapshot import AnalyzeSnapshot, SubcommandTraverse

        return AnalyzeSnapshot(
            # context=self,
            traverses=[
                SubcommandTraverse(self, self.root_ref.header(), self.preset.new_mix()),
            ],
        )

    def new_snapshot_from_prefix(self):
        from .snapshot import AnalyzeSnapshot, SubcommandTraverse

        return AnalyzeSnapshot(
            # context=self,
            traverses=[
                SubcommandTraverse(self, self.root_ref.prefix(), self.preset.new_mix()),
            ],
        )


@dataclass
class OptionPattern:
    keyword: str
    receiver: Rx[str] | None = None  # 评估一下这个的用途。
    separators: str = SEPARATORS

    soft_keyword: bool = False
    allow_duplicate: bool = False
