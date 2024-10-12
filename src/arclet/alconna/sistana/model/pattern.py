from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Iterable, MutableMapping

from elaina_segment import SEPARATORS
from tarina.trie import CharTrie, Trie

from arclet.alconna._dcls import safe_dcls_kw

from .fragment import assert_fragments_order
from .mix import Preset, Track
from .snapshot import AnalyzeSnapshot, ProcessingState

if TYPE_CHECKING:
    from .fragment import _Fragment


@dataclass(**safe_dcls_kw(slots=True))
class SubcommandPattern:
    header: str
    preset: Preset

    soft_keyword: bool = False
    separators: str = SEPARATORS

    prefixes: Trie[str] | None = field(default=None)
    compact_header: bool = False
    enter_instantly: bool = True
    header_fragment: _Fragment | None = None

    _options: list[OptionPattern] = field(default_factory=list)
    _compact_keywords: Trie[str] | None = field(default=None)
    _exit_options: list[str] = field(default_factory=list)

    _options_bind: MutableMapping[str, OptionPattern] = field(default_factory=dict)
    _subcommands_bind: MutableMapping[str, SubcommandPattern] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        header: str,
        *fragments: _Fragment,
        prefixes: Iterable[str] = (),
        compact_header: bool = False,
        enter_instantly: bool = True,
        separators: str = SEPARATORS,
        soft_keyword: bool = False,
        header_fragment: _Fragment | None = None,
    ):
        preset = Preset(Track(fragments, header=header_fragment), {})
        subcommand = cls(
            header=header,
            preset=preset,
            compact_header=compact_header,
            enter_instantly=enter_instantly,
            separators=separators,
            soft_keyword=soft_keyword,
            header_fragment=header_fragment,
        )

        if prefixes:
            subcommand.prefixes = CharTrie.fromkeys(list(prefixes))  # type: ignore

        return subcommand

    @property
    def root_ref(self):
        return [self.header]

    def create_snapshot(self, state: ProcessingState = ProcessingState.COMMAND):
        snapshot = AnalyzeSnapshot(command=[self.header], state=state, traverses={(self.header,): self})
        snapshot.mix.update((self.header,), self.preset)
        return snapshot

    @property
    def root_entrypoint(self):
        return self.create_snapshot()

    @property
    def prefix_entrypoint(self):
        return self.create_snapshot(ProcessingState.PREFIX)

    @property
    def header_entrypoint(self):
        return self.create_snapshot(ProcessingState.HEADER)

    def add_track(self, name: str, fragments: tuple[_Fragment, ...], header: _Fragment | None = None):
        assert_fragments_order(fragments)

        self.preset.option_tracks[name] = Track(fragments, header=header)

    def subcommand(
        self,
        header: str,
        *fragments: _Fragment,
        aliases: Iterable[str] = (),
        soft_keyword: bool = False,
        separators: str = SEPARATORS,
        compact_header: bool = False,
        compact_aliases: bool = False,
        enter_instantly: bool = True,
        header_fragment: _Fragment | None = None,
    ):
        preset = Preset(Track(fragments, header=header_fragment), {})
        pattern = self._subcommands_bind[header] = SubcommandPattern(
            header=header,
            preset=preset,
            soft_keyword=soft_keyword,
            separators=separators,
            compact_header=compact_header,
            enter_instantly=enter_instantly,
            header_fragment=header_fragment,
        )
        self._subcommands_bind[header] = pattern
        for alias in aliases:
            self._subcommands_bind[alias] = pattern

        if compact_header:
            self._compact_keywords = CharTrie.fromkeys(
                [header, *aliases, *(self._compact_keywords or []), *(aliases if compact_aliases else [])]
            )  # type: ignore

        return pattern

    def option(
        self,
        keyword: str,
        *fragments: _Fragment,
        aliases: Iterable[str] = (),
        separators: str | None = None,
        hybrid_separators: bool = False,
        soft_keyword: bool = False,
        allow_duplicate: bool = False,
        compact_header: bool = False,
        header_fragment: _Fragment | None = None,
        header_separators: str | None = None,
        forwarding: bool = True,
    ):
        if separators is None:
            separators = self.separators
        elif hybrid_separators:
            separators = separators + self.separators

        pattern = self._options_bind[keyword] = OptionPattern(
            keyword,
            aliases=list(aliases),
            separators=separators,
            allow_duplicate=allow_duplicate,
            soft_keyword=soft_keyword,
            header_fragment=header_fragment,
            header_separators=header_separators,
            compact_header=compact_header,
        )
        for alias in aliases:
            self._options_bind[alias] = pattern

        self._options.append(pattern)
        self.add_track(keyword, fragments, header=header_fragment)

        if not forwarding:
            self._exit_options.append(keyword)

        if header_separators and not fragments:
            raise ValueError("header_separators must be used with fragments")

        return self


@dataclass
class OptionPattern:
    keyword: str
    aliases: list[str] = field(default_factory=list)
    separators: str = SEPARATORS

    soft_keyword: bool = False
    allow_duplicate: bool = False
    header_fragment: _Fragment | None = None
    header_separators: str | None = None
    compact_header: bool = False

    @cached_property
    def _trigger(self):
        if self.compact_header:
            return CharTrie.fromkeys([self.keyword, *self.aliases])

        return {self.keyword, *self.aliases}
