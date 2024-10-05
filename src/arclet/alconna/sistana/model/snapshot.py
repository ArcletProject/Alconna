from __future__ import annotations

from typing import TYPE_CHECKING

from .mix import Mix
from .pointer import PointerData, PointerRole

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
        "alter_ref",
    )

    traverses: dict[PointerData, SubcommandPattern]
    endpoint: PointerData | None
    mix: Mix

    main_ref: PointerData
    alter_ref: PointerData | None

    _pending_options: list[tuple[OptionPattern, PointerData, set[str]]]
    _ref_cache_option: dict[PointerData, OptionPattern]

    def __init__(self, main_ref: PointerData, alter_ref: PointerData | None, traverses: dict[PointerData, SubcommandPattern]):
        self.main_ref = main_ref
        self.alter_ref = alter_ref
        self.traverses = traverses
        self.endpoint = None
        self.mix = Mix()
        self._pending_options = []
        self._ref_cache_option = {}
        self.update_pending()

    @property
    def current_ref(self):
        return self.alter_ref or self.main_ref

    @property
    def context(self):
        return self.traverses[self.main_ref]

    def enter_subcommand(self, trigger: str, pattern: SubcommandPattern):
        ref = self.main_ref + ((PointerRole.SUBCOMMAND, pattern.header),)

        self.mix.update(ref, pattern.preset)
        track = self.mix.tracks[self.main_ref]
        track.emit_header(self.mix, trigger)
        self.pop_pendings()

        self.main_ref = ref
        self.alter_ref = None
        self.traverses[ref] = pattern
        self.update_pending()

    def enter_option(self, trigger: str, ref: PointerData, pattern: OptionPattern):
        track = self.mix.tracks[ref]

        if track.emitted and not pattern.allow_duplicate:
            return False

        track.emit_header(self.mix, trigger)

        if track:
            track.reset()
            self.alter_ref = ref
            self._ref_cache_option[ref] = pattern

        return True

    @property
    def determined(self):
        return self.endpoint is not None

    @property
    def stage_satisfied(self):
        cond = self.mix.tracks[self.main_ref].satisfied
        if cond:
            subcommand = self.traverses[self.main_ref]
            for option, ref, _ in self._pending_options:
                if option.keyword in subcommand._exit_options and not self.mix.tracks[ref].satisfied:
                    return False

        return cond

    def determine(self, endpoint: PointerData | None = None):
        self.endpoint = endpoint or self.main_ref

    def update_pending(self):
        subcommand_ref = self.main_ref
        subcommand_pattern = self.traverses[subcommand_ref]

        self._pending_options.extend(
            [
                (option, subcommand_ref + ((PointerRole.OPTION, option.keyword),), {option.keyword, *option.aliases})
                for option in subcommand_pattern._options
            ]
        )

    def get_option(self, trigger: str):
        for option, ref, triggers in self._pending_options:
            if trigger in triggers:
                return option, ref

    def pop_pendings(self):
        current = self.main_ref
        exit_options = self.context._exit_options

        self._pending_options = [
            (option, ref, triggers)
            for option, ref, triggers in self._pending_options
            if not (ref[:-1] == current and option.keyword in exit_options)
        ]
