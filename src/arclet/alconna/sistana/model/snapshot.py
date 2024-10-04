from __future__ import annotations

from typing import TYPE_CHECKING

from .mix import Mix
from .pointer import Pointer, PointerData

if TYPE_CHECKING:
    from .pattern import OptionPattern, SubcommandPattern


# @dataclass
class AnalyzeSnapshot:
    __slots__ = (
        "traverses",
        "endpoint",
        "mix",
        "_pending_options",
        "_ref_cache_option",
        "_main_ref",
        "_alter_ref",
    )

    traverses: dict[PointerData, SubcommandPattern]
    endpoint: Pointer | None
    mix: Mix

    _main_ref: Pointer
    _alter_ref: Pointer | None

    _pending_options: list[tuple[Pointer, str, set[str]]]
    _ref_cache_option: dict[Pointer, OptionPattern]

    def __init__(self, main_ref: Pointer, alter_ref: Pointer | None, traverses: dict[PointerData, SubcommandPattern]):
        self._main_ref = main_ref
        self._alter_ref = alter_ref

        self.traverses = traverses

        self.endpoint = None
        self.mix = Mix()

        self._pending_options = []
        self._ref_cache_option = {}

        self.update_pending()

    @property
    def current_ref(self):
        return self._alter_ref or self._main_ref

    def set_alter(self, ref: Pointer):
        self._alter_ref = ref

    def unset_alter(self):
        self._alter_ref = None

    @property
    def context(self):
        return self.traverses[self._main_ref.data]

    @context.setter
    def context(self, value: tuple[Pointer, SubcommandPattern]):
        ref, cmd = value
        self._main_ref = ref
        self.traverses[ref.data] = cmd

    @property
    def determined(self):
        return self.endpoint is not None

    @property
    def stage_satisfied(self):
        conda = self.mix.tracks[self._main_ref.data].satisfied
        if conda:
            subcommand = self.traverses[self._main_ref.data]
            for ref, keyword, _ in self._pending_options:
                if keyword in subcommand._exit_options:
                    if not self.mix.tracks[ref.option(keyword).data].satisfied:
                        return False

        return conda

    def determine(self, endpoint: Pointer | None = None):
        self.endpoint = endpoint or self._main_ref

    def update_pending(self):
        subcommand_ref = self._main_ref
        subcommand_pattern = self.traverses[subcommand_ref.data]
        # for option in subcommand_pattern._options:
        #     self._pending_options.append((subcommand_ref, option.keyword, {option.keyword, *option.aliases}))

        self._pending_options.extend([
            (subcommand_ref, option.keyword, {option.keyword, *option.aliases})
            for option in subcommand_pattern._options
        ])

    def get_option(self, trigger: str):
        for subcommand_ref, option_keyword, triggers in self._pending_options:
            if trigger in triggers:
                return subcommand_ref, option_keyword

    def pop_pendings(self):
        current = self._main_ref
        exit_options = self.context._exit_options
        self._pending_options = [
            (ref, keyword, triggers) for ref, keyword, triggers in self._pending_options if ref != current or keyword not in exit_options
        ]

    def complete(self):
        self.mix.complete()
