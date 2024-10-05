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
        "main_ref",
        "_alter_ref",
    )

    traverses: dict[PointerData, SubcommandPattern]
    endpoint: Pointer | None
    mix: Mix

    main_ref: Pointer
    _alter_ref: Pointer | None

    _pending_options: list[tuple[Pointer, str, set[str]]]
    _ref_cache_option: dict[PointerData, OptionPattern]

    def __init__(self, main_ref: Pointer, alter_ref: Pointer | None, traverses: dict[PointerData, SubcommandPattern]):
        self.main_ref = main_ref
        self._alter_ref = alter_ref

        self.traverses = traverses

        self.endpoint = None
        self.mix = Mix()

        self._pending_options = []
        self._ref_cache_option = {}

        self.update_pending()

    @property
    def current_ref(self):
        return self._alter_ref or self.main_ref

    @property
    def context(self):
        return self.traverses[self.main_ref.data]

    def set_alter(self, ref: Pointer):
        self._alter_ref = ref

    def unset_alter(self):
        self._alter_ref = None

    def set_traverse(self, ref: Pointer, cmd: SubcommandPattern):
        self.main_ref = ref
        self.traverses[ref.data] = cmd

    def enter_subcommand(self, trigger: str, pattern: SubcommandPattern):
        ref = self.main_ref.subcommand(pattern.header)

        self.mix.update(ref, pattern.preset)
        track = self.mix.tracks[self.main_ref.data]
        track.emit_header(self.mix, trigger)
        self.pop_pendings()

        self.set_traverse(ref, pattern)
        self.update_pending()

    def enter_option(self, trigger: str, ref: Pointer, pattern: OptionPattern):
        track = self.mix.tracks[ref.data]

        if track.emitted and not pattern.allow_duplicate:
            return False
        
        track.emit_header(self.mix, trigger)

        if track:
            track.reset()
            self.set_alter(ref)
            self._ref_cache_option[ref.data] = pattern
        
        return True

    @property
    def determined(self):
        return self.endpoint is not None

    @property
    def stage_satisfied(self):
        conda = self.mix.tracks[self.main_ref.data].satisfied
        if conda:
            subcommand = self.traverses[self.main_ref.data]
            for ref, keyword, _ in self._pending_options:
                if keyword in subcommand._exit_options and not self.mix.tracks[ref.option(keyword).data].satisfied:
                    return False

        return conda

    def determine(self, endpoint: Pointer | None = None):
        self.endpoint = endpoint or self.main_ref

    def update_pending(self):
        subcommand_ref = self.main_ref
        subcommand_pattern = self.traverses[subcommand_ref.data]

        self._pending_options.extend(
            [(subcommand_ref, option.keyword, {option.keyword, *option.aliases}) for option in subcommand_pattern._options]
        )

    def get_option(self, trigger: str):
        for subcommand_ref, option_keyword, triggers in self._pending_options:
            if trigger in triggers:
                owned_subcommand = self.traverses[subcommand_ref.data]
                target_option = owned_subcommand._options_bind[option_keyword]
                return target_option, subcommand_ref.option(option_keyword)

    def pop_pendings(self):
        current = self.main_ref
        exit_options = self.context._exit_options
        self._pending_options = [
            (ref, keyword, triggers)
            for ref, keyword, triggers in self._pending_options
            if not (ref.data == current.data and keyword in exit_options)
        ]

    def complete(self):
        self.mix.complete()
