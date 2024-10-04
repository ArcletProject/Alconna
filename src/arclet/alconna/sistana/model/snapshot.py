from __future__ import annotations
from typing import TYPE_CHECKING

from arclet.alconna.sistana.model.mix import Mix

if TYPE_CHECKING:
    from .pattern import SubcommandPattern, OptionPattern
    from .pointer import Pointer


# @dataclass
class AnalyzeSnapshot:
    __slots__ = ("current", "traverses", "endpoint", "mix", "_pendings", "_ref_cache_option")


    current: Pointer

    traverses: dict[Pointer, SubcommandPattern]
    endpoint: Pointer | None
    mix: Mix

    _pendings: list[tuple[Pointer, str, set[str]]]
    _ref_cache_option: dict[Pointer, OptionPattern]

    def __init__(self, current: Pointer, traverses: dict[Pointer, SubcommandPattern]):
        self.current = current
        self.traverses = traverses

        self.endpoint = None
        self.mix = Mix()
        
        self._pendings = []
        self._ref_cache_option = {}

        self.update_pending()

    @property
    def context(self):
        return next(reversed(self.traverses.values()))

    @context.setter
    def context(self, value: SubcommandPattern):
        self.traverses[self.current.subcommand(value.header)] = value

    @property
    def determined(self):
        return self.endpoint is not None

    @property
    def stage_satisfied(self):
        conda = self.mix.tracks[self.current].satisfied
        if conda:
            subcommand = self.traverses[self.current]
            for ref, keyword, _ in self._pendings:
                if keyword in subcommand._exit_options:
                    if not self.mix.tracks[ref.option(keyword)].satisfied:
                        return False

        return conda

    def determine(self, endpoint: Pointer | None = None):
        self.endpoint = endpoint or self.current

    def update_pending(self):
        subcommand_ref, subcommand_pattern = next(reversed(self.traverses.items()))
        for option in subcommand_pattern._options:
            self._pendings.append((subcommand_ref, option.keyword, {option.keyword, *option.aliases}))

    def get_option(self, trigger: str):
        for subcommand_ref, option_keyword, triggers in self._pendings:
            if trigger in triggers:
                return subcommand_ref, option_keyword

    def get_option_strict(self, trigger: str):
        result = self.get_option(trigger)
        if result is None:
            raise RuntimeError
        return result

    def leave_context(self):
        exit_options = self.context._exit_options
        current = self.current
        self._pendings = [
            (ref, keyword, triggers)
            for ref, keyword, triggers in self._pendings
            if ref != current or keyword not in exit_options
        ]

    def complete(self):
        self.mix.complete()
