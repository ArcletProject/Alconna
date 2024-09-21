from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from elaina_segment import SEPARATORS
from elaina_triehard import TrieHard

from .pointer import Pointer
from .track import Preset


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

    def create_snapshot(self, ref: Pointer):
        from .snapshot import AnalyzeSnapshot, SubcommandTraverse

        return AnalyzeSnapshot(
            traverses=[
                SubcommandTraverse(
                    subcommand=self,
                    trigger=self.header,
                    ref=ref,
                    mix=self.preset.new_mix(),
                ),
            ],
        )

    @property
    def root_entrypoint(self):
        return self.create_snapshot(self.root_ref)

    @property
    def prefix_entrypoint(self):
        return self.create_snapshot(self.root_ref.prefix())

    @property
    def header_entrypoint(self):
        return self.create_snapshot(self.root_ref.header())


@dataclass
class OptionPattern:
    keyword: str
    separators: str = SEPARATORS

    soft_keyword: bool = False
    allow_duplicate: bool = False
