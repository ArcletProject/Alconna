from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from .mix import Mix

if TYPE_CHECKING:
    from .pattern import OptionPattern, SubcommandPattern


class ProcessingState(int, Enum):
    COMMAND = 0
    PREFIX = 1
    HEADER = 2
    OPTION = 3


class AnalyzeSnapshot:
    __slots__ = (
        "state",
        "command",
        "option",

        "traverses",
        "endpoint",
        "mix",

        "_pending_options",
        "_ref_cache_option",
    )

    state: ProcessingState
    command: list[str]
    option: tuple[tuple[str, ...], str] | None

    traverses: dict[tuple[str, ...], SubcommandPattern]
    endpoint: tuple[str, ...] | None
    mix: Mix

    _pending_options: list[tuple[OptionPattern, tuple[str, ...], set[str]]]  # (pattern, owner, triggers)
    _ref_cache_option: dict[tuple[tuple[str, ...], str], OptionPattern]

    def __init__(
        self,
        command: list[str],
        traverses: dict[tuple[str], SubcommandPattern],
        state: ProcessingState = ProcessingState.COMMAND,
    ):
        self.command = command
        self.state = state

        self.traverses = traverses
        self.endpoint = None
        self.mix = Mix()
        self._pending_options = []
        self._ref_cache_option = {}
        self.update_pending()

    @property
    def context(self):
        return self.traverses[tuple(self.command)]

    def enter_subcommand(self, trigger: str, pattern: SubcommandPattern):
        self.command.append(pattern.header)
        self.state = ProcessingState.COMMAND
        self.option = None
        key = tuple(self.command)
        self.traverses[key] = pattern

        self.mix.update(key, pattern.preset)
        track = self.mix.command_tracks[key]
        track.emit_header(self.mix, trigger)

        self.pop_pendings()

        self.update_pending()

    def enter_option(self, trigger: str, owned_command: tuple[str, ...], option_keyword: str, pattern: OptionPattern):
        track = self.mix.option_tracks[owned_command, option_keyword]

        if track.emitted and not pattern.allow_duplicate:
            return False

        track.emit_header(self.mix, trigger)

        if track:
            track.reset()
            self.state = ProcessingState.OPTION
            self.option = owned_command, option_keyword
            self._ref_cache_option[self.option] = pattern

        return True

    @property
    def determined(self):
        return self.endpoint is not None

    @property
    def stage_satisfied(self):
        cmd = tuple(self.command)
        cond = self.mix.command_tracks[cmd].satisfied
        if cond:
            subcommand = self.context
            for option, owner, _ in self._pending_options:
                if option.keyword in subcommand._exit_options and not self.mix.option_tracks[owner, option.keyword].satisfied:
                    return False

        return cond

    def determine(self):
        self.state = ProcessingState.COMMAND
        self.endpoint = tuple(self.command)

    def update_pending(self):
        subcommand_ref = tuple(self.command)
        subcommand_pattern = self.traverses[subcommand_ref]

        self._pending_options.extend(
            [
                (option, subcommand_ref, {option.keyword, *option.aliases})
                for option in subcommand_pattern._options
            ]
        )

    def get_option(self, trigger: str):
        for option, owner, triggers in self._pending_options:
            if trigger in triggers:
                return option, owner

    def pop_pendings(self):
        cmd = tuple(self.command)
        exit_options = self.context._exit_options

        self._pending_options = [
            (option, owner, triggers)
            for option, owner, triggers in self._pending_options
            if not (owner == cmd and option.keyword in exit_options)
        ]
