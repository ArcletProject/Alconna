from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable, MutableMapping

from elaina_segment import SEPARATORS
from elaina_triehard import TrieHard

from arclet.alconna._dcls import safe_dcls_kw

from .pointer import Pointer
from .mix import Preset, Track
from .snapshot import AnalyzeSnapshot, SubcommandTraverse

if TYPE_CHECKING:
    from .fragment import _Fragment


@dataclass(**safe_dcls_kw(slots=True))
class SubcommandPattern:
    header: str
    preset: Preset
    options: MutableMapping[str, OptionPattern] = field(default_factory=dict)
    subcommands: MutableMapping[str, SubcommandPattern] = field(default_factory=dict)

    soft_keyword: bool = False
    separators: str = SEPARATORS

    prefixes: TrieHard | None = field(default=None)  # 后面改成 init=False
    compact_keywords: TrieHard | None = field(default=None)  # 后面改成 init=False
    compact_header: bool = False
    satisfy_previous: bool = True
    header_fragment: _Fragment | None = None

    @classmethod
    def build(
        cls,
        header: str,
        *fragments: _Fragment,
        prefixes: Iterable[str] = (),
        compact_header: bool = False,
        satisfy_previous: bool = True,
        separators: str = SEPARATORS,
        soft_keyword: bool = False,
        header_fragment: _Fragment | None = None,
    ):
        subcommand = cls(
            header=header,
            preset=Preset(),
            prefixes=TrieHard(list(prefixes)),
            compact_header=compact_header,
            satisfy_previous=satisfy_previous,
            separators=separators,
            soft_keyword=soft_keyword,
            header_fragment=header_fragment,
        )
        subcommand.add_track(header, fragments, header=header_fragment)

        return subcommand

    @property
    def root_ref(self):
        return Pointer().subcommand(self.header)

    def create_snapshot(self, ref: Pointer):
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

    def add_track(self, name: str, fragments: Iterable[_Fragment], header: _Fragment | None = None):
        self.preset.tracks[name] = Track(deque(fragments), header=header)

    def subcommand(
        self,
        header: str,
        *fragments: _Fragment,
        aliases: Iterable[str] = (),
        soft_keyword: bool = False,
        separators: str = SEPARATORS,
        compact_header: bool = False,
        compact_aliases: bool = False,
        satisfy_previous: bool = True,
        header_fragment: _Fragment | None = None,
    ):
        pattern = SubcommandPattern(
            header=header,
            preset=Preset(),
            soft_keyword=soft_keyword,
            separators=separators,
            compact_header=compact_header,
            satisfy_previous=satisfy_previous,
            header_fragment=header_fragment,
        )
        self.subcommands[header] = pattern
        for alias in aliases:
            self.subcommands[alias] = pattern
        
        if fragments:
            pattern.add_track(header, fragments, header=header_fragment)

        if compact_header:
            self.compact_keywords = TrieHard([header, *aliases, *(self.compact_keywords or []), *(aliases if compact_aliases else [])])

        return pattern

    def option(
        self,
        keyword: str,
        *fragments: _Fragment,
        aliases: Iterable[str] = (),
        soft_keyword: bool = False,
        allow_duplicate: bool = False,
        compact_header: bool = False,
        compact_aliases: bool = False,
        header_fragment: _Fragment | None = None,
    ):
        pattern = OptionPattern(
            keyword,
            separators=self.separators,
            allow_duplicate=allow_duplicate,
            soft_keyword=soft_keyword,
            header_fragment=header_fragment
        )
        self.options[keyword] = pattern
        for alias in aliases:
            self.options[alias] = pattern
        
        if fragments:
            self.add_track(keyword, fragments, header=header_fragment)

        if compact_header:
            self.compact_keywords = TrieHard([keyword, *aliases, *(self.compact_keywords or []), *(aliases if compact_aliases else [])])

        return self


@dataclass(**safe_dcls_kw(slots=True))
class OptionPattern:
    keyword: str
    separators: str = SEPARATORS

    soft_keyword: bool = False
    allow_duplicate: bool = False
    keep_previous_assignes: bool = False
    header_fragment: _Fragment | None = None
