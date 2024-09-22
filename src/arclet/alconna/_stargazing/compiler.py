from __future__ import annotations

from collections import deque
from typing import overload

import tarina

from arclet.alconna import Alconna, Arg, Args, Arparma, HeadResult, Option, OptionResult, Subcommand, SubcommandResult
from arclet.alconna.sistana import Analyzer, Buffer, Fragment, LoopflowDescription, OptionPattern, Preset, SubcommandPattern
from arclet.alconna.sistana import Value
from arclet.alconna.sistana.model.fragment import _Fragment
from elaina_triehard import TrieHard

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
def into_sistana(alconna: Alconna) -> SubcommandPattern:
    ...

@overload
def into_sistana(alconna: Subcommand) -> SubcommandPattern:
    ...

@overload
def into_sistana(alconna: Option) -> OptionPattern:
    ...


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
            preset=Preset({
                alconna.name: _alc_args_to_fragments(alconna.args),
                **{
                    option.name: _alc_args_to_fragments(option.args)
                    for option in alconna.options if isinstance(option, Option)
                },
            }),
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
            preset=Preset({
                alconna.name: _alc_args_to_fragments(alconna.args),
                **{
                    option.name: _alc_args_to_fragments(option.args)
                    for option in alconna.options if isinstance(option, Option)
                },
            }),
            options=options,
            subcommands=subcommands,
            soft_keyword=alconna.soft_keyword,
        )
    else:
        return OptionPattern(
            keyword=alconna.name,
            soft_keyword=alconna.soft_keyword,
        )
