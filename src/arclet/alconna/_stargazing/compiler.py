from __future__ import annotations

from collections import deque
from typing import Any, Iterable, Sequence, overload

import tarina
from elaina_triehard import TrieHard

from arclet.alconna import Alconna, Arg, Args, Arparma, HeadResult, Option, OptionResult, Subcommand, SubcommandResult
from arclet.alconna.exceptions import ArgumentMissing, InvalidArgs, InvalidParam, NullMessage, ParamsUnmatched, UnexpectedElement
from arclet.alconna.sistana import Analyzer, Fragment, LoopflowExitReason, OptionPattern, Preset, SubcommandPattern, Track, Value
from arclet.alconna.sistana.err import ParsePanic, Rejected
from arclet.alconna.sistana.model.fragment import _Fragment
from arclet.alconna.sistana.model.pointer import PointerRole
from arclet.alconna.sistana.model.snapshot import SubcommandTraverse
from .flywheel import build_runes
from elaina_segment import Buffer


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
            prefixes=TrieHard(alconna.prefixes) if alconna.prefixes else None,
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


def _reason_raise_alc_exception(reason: LoopflowExitReason) -> None:
    if reason == LoopflowExitReason.completed:
        return

    if reason in {
        LoopflowExitReason.unsatisfied,
        LoopflowExitReason.previous_unsatisfied,
        LoopflowExitReason.switch_unsatisfied_option,
        LoopflowExitReason.unsatisfied_switch_subcommand,
    }:
        raise ParamsUnmatched(f"LoopflowDescription: {reason.value}")

    if reason in {
        LoopflowExitReason.out_of_data_subcommand,
        LoopflowExitReason.out_of_data_option,
    }:
        raise ArgumentMissing(f"LoopflowDescription: {reason.value}")

    if reason in {
        LoopflowExitReason.prefix_expect_str,
        LoopflowExitReason.header_expect_str,
    }:
        raise InvalidParam(f"LoopflowDescription: {reason.value}")

    if reason in {
        LoopflowExitReason.prefix_mismatch,
        LoopflowExitReason.header_mismatch,
    }:
        raise InvalidArgs(f"LoopflowDescription: {reason.value}")

    if reason == LoopflowExitReason.unexpected_segment:
        raise UnexpectedElement(f"LoopflowDescription: {reason.value}")

    if reason == LoopflowExitReason.option_duplicated_prohibited:
        raise NullMessage(f"LoopflowDescription: {reason.value}")

def _sistana_to_alc_result(traverses: list[SubcommandTraverse]) -> tuple[str, SubcommandResult] | None:
    if not traverses:
        return
    
    first_traverse = traverses[0]
    mix = first_traverse.mix

    def extract_values_and_args(name: str):
        track = mix.get_track(name)
        value = ... if track.header is None else track.assignes[track.header.name]
        args = {k: v for k, v in track.assignes.items() if track.header is None or k != track.header.name}
        return value, args

    value, args = extract_values_and_args(first_traverse.subcommand.header)
    options = {
        opt: OptionResult(*extract_values_and_args(opt))
        for opt in first_traverse.option_traverses._by_keyword
    } if first_traverse.option_traverses.traverses else None
    subcommand_result = _sistana_to_alc_result(traverses[1:])

    subcommands = None
    if subcommand_result is not None:
        subcommand_name, subcommands = subcommand_result
        subcommands = {subcommand_name: subcommands}

    return first_traverse.ref.last_value, SubcommandResult(value, args, options, subcommands)


def process_adapt(pattern: SubcommandPattern, message: Sequence[Any]):
    analyzer = Analyzer()
    buffer = Buffer(build_runes(message), runes=False)
    snapshot = pattern.prefix_entrypoint

    try:
        reason = analyzer.loopflow(snapshot, buffer)
    except Rejected as e:
        raise InvalidParam from e
    except ParsePanic as e:
        raise NullMessage from e
    else:
        _reason_raise_alc_exception(reason)

    subcommands = None
    main_args = None
    subcmds = None
    options = None
    result = _sistana_to_alc_result(snapshot.traverses)
    if result is not None:
        subcommands = result[1]
        main_args = subcommands.args
        subcmds = subcommands.subcommands
        options = subcommands.options

    return Arparma(
        _id=-1,
        origin=message,
        matched=True,
        header_match=HeadResult(matched=True),
        main_args=main_args,
        subcommands=subcmds,
        options=options,
    )


def patch_alconna(alconna: Alconna):
    pattern = into_sistana(alconna)

    alconna._sistana_pattern = pattern  # type: ignore
    alconna._parse = lambda message, _: process_adapt(pattern, message)  # type: ignore
