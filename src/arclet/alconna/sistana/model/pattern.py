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

    @classmethod
    def build(
        cls,
        header: str,
        fragments: list[_Fragment] | None = None,
        options: list[OptionPattern] | None = None,
        options_fragments: dict[str, list[_Fragment]] | None = None,
        prefixes: Iterable[str] = (),
        compact_keywords: Iterable[str] = (),
        compact_header: bool = False,
        satisfy_previous: bool = True,
        separators: str = SEPARATORS,
        soft_keyword: bool = False,
    ):
        preset = Preset(
            {
                header: Track(deque(fragments) if fragments else deque()),
                **(
                    {
                        option.keyword: Track(deque(options_fragments[option.keyword]))
                        for option in options
                        if option.keyword in options_fragments
                    }
                    if options and options_fragments
                    else {}
                ),
            }
        )

        return cls(
            header=header,
            preset=preset,
            options={option.keyword: option for option in options} if options else {},
            prefixes=TrieHard(list(prefixes)),
            compact_keywords=TrieHard(list(compact_keywords)),
            compact_header=compact_header,
            satisfy_previous=satisfy_previous,
            separators=separators,
            soft_keyword=soft_keyword,
        )

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

    def subcommand(
        self,
        header: str,
        aliases: Iterable[str] = (),
        soft_keyword: bool = False,
        separators: str = SEPARATORS,
        compact_header: bool = False,
        satisfy_previous: bool = True,
    ):
        pattern = SubcommandPattern(
            header=header,
            preset=Preset(),
            soft_keyword=soft_keyword,
            separators=separators,
            compact_header=compact_header,
            satisfy_previous=satisfy_previous,
        )
        self.subcommands[header] = pattern
        for alias in aliases:
            self.subcommands[alias] = pattern

        if compact_header:
            self.compact_keywords = TrieHard([header, *aliases, *(self.compact_keywords or [])])

        return self

    def option(
        self,
        keyword: str,
        aliases: Iterable[str] = (),
        soft_keyword: bool = False,
        allow_duplicate: bool = False,
        compact_header: bool = False,
    ):
        pattern = OptionPattern(
            keyword,
            separators=self.separators,
            allow_duplicate=allow_duplicate,
            soft_keyword=soft_keyword,
        )
        self.options[keyword] = pattern
        for alias in aliases:
            self.options[alias] = pattern

        if compact_header:
            self.compact_keywords = TrieHard([keyword, *aliases, *(self.compact_keywords or [])])

        return self


@dataclass(**safe_dcls_kw(slots=True))
class OptionPattern:
    keyword: str
    separators: str = SEPARATORS

    soft_keyword: bool = False
    allow_duplicate: bool = False
    net_fragment: _Fragment | None = None
