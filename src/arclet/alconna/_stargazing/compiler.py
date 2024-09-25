from __future__ import annotations

from collections import deque
from typing import overload

import tarina
from elaina_triehard import TrieHard

from arclet.alconna import Alconna, Arg, Args, Arparma, HeadResult, Option, OptionResult, Subcommand, SubcommandResult
from arclet.alconna.sistana import Analyzer, Fragment, LoopflowDescription, OptionPattern, Preset, SubcommandPattern, Track, Value
from arclet.alconna.sistana.model.fragment import _Fragment
from arclet.alconna.exceptions import ArgumentMissing, InvalidArgs, InvalidParam, ParamsUnmatched, UnexpectedElement, NullMessage

def _alc_args_to_fragments(args: Args) -> deque[_Fragment]:
    alc_argument = args.argument
    fragments = deque()

    for ag in alc_argument:
        if ag.field.default is tarina.const.Empty:
            default = None
        else:
            default = Value(ag.field.default)

        frag = Fragment(
            name=ag.name,
            default=default,
        )
        frag.apply_nepattern(ag.value)
        fragments.append(frag)

    return fragments


@overload
def into_sistana(alconna: Alconna) -> SubcommandPattern: ...


@overload
def into_sistana(alconna: Subcommand) -> SubcommandPattern: ...


@overload
def into_sistana(alconna: Option) -> OptionPattern: ...


def into_sistana(alconna: Alconna | Subcommand | Option):
    if isinstance(alconna, Alconna):
        alconna.compile()

        subcommands = {}
        options = {}

        for subcommand in alconna.options:
            if isinstance(subcommand, Subcommand):
                pattern = into_sistana(subcommand)
                subcommands[subcommand.name] = pattern
                for alias in subcommand.aliases:
                    subcommands[alias] = pattern
            elif isinstance(subcommand, Option):
                pattern = into_sistana(subcommand)
                options[subcommand.name] = pattern
                for alias in subcommand.aliases:
                    options[alias] = pattern

        return SubcommandPattern(
            header=alconna.command,
            preset=Preset(
                {
                    alconna.name: Track(deque(_alc_args_to_fragments(alconna.args))),
                    **{
                        option.name: Track(deque(_alc_args_to_fragments(option.args)))
                        for option in alconna.options
                        if isinstance(option, Option)
                    },
                }
            ),
            options=options,
            subcommands=subcommands,
            prefixes=TrieHard(alconna.prefixes),
            soft_keyword=alconna.soft_keyword,
        )
    elif isinstance(alconna, Subcommand):
        subcommands = {}
        options = {}

        for subcommand in alconna.options:
            if not isinstance(subcommand, Subcommand):
                continue

            pattern = into_sistana(subcommand)
            subcommands[subcommand.name] = pattern
            for alias in subcommand.aliases:
                subcommands[alias] = pattern

        for option in alconna.options:
            if not isinstance(option, Option):
                continue

            pattern = into_sistana(option)
            options[option.name] = pattern
            for alias in option.aliases:
                options[alias] = pattern

        return SubcommandPattern(
            header=alconna.name,
            preset=Preset(
                {
                    alconna.name: Track(deque(_alc_args_to_fragments(alconna.args))),
                    **{
                        option.name: Track(deque(_alc_args_to_fragments(option.args)))
                        for option in alconna.options
                        if isinstance(option, Option)
                    },
                }
            ),
            options=options,
            subcommands=subcommands,
            soft_keyword=alconna.soft_keyword,
        )
    else:
        return OptionPattern(
            keyword=alconna.name,
            soft_keyword=alconna.soft_keyword,
        )


def reason_raise_alc_exception(reason: LoopflowDescription) -> None:
    if reason == LoopflowDescription.completed:
        return

    if reason in {
        LoopflowDescription.unsatisfied,
        LoopflowDescription.previous_unsatisfied,
        LoopflowDescription.switch_unsatisfied_option,
        LoopflowDescription.unsatisfied_switch_subcommand,
    }:
        raise ParamsUnmatched(f"LoopflowDescription: {reason.value}")

    if reason in {
        LoopflowDescription.out_of_data_subcommand,
        LoopflowDescription.out_of_data_option,
    }:
        raise ArgumentMissing(f"LoopflowDescription: {reason.value}")

    if reason in {
        LoopflowDescription.prefix_expect_str,
        LoopflowDescription.header_expect_str,
    }:
        raise InvalidParam(f"LoopflowDescription: {reason.value}")

    if reason in {
        LoopflowDescription.prefix_mismatch,
        LoopflowDescription.header_mismatch,
    }:
        raise InvalidArgs(f"LoopflowDescription: {reason.value}")

    if reason == LoopflowDescription.unexpected_segment:
        raise UnexpectedElement(f"LoopflowDescription: {reason.value}")

    if reason == LoopflowDescription.option_duplicated_prohibited:
        raise NullMessage(f"LoopflowDescription: {reason.value}")





def process_adapt(): ...
