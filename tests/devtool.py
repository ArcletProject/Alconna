from __future__ import annotations

import traceback
from collections import namedtuple
from typing import Any, Literal

from arclet.alconna._internal._analyser import Analyser, default_compiler
from arclet.alconna._internal._handlers import analyse_args as ala
from arclet.alconna._internal._handlers import HEAD_HANDLES
from arclet.alconna._internal._handlers import analyse_option as alo
from arclet.alconna._internal._header import Header
from arclet.alconna.args import Args
from arclet.alconna.argv import Argv
from arclet.alconna.base import Option, Subcommand
from arclet.alconna.config import Namespace
from arclet.alconna.typing import DataCollection, CommandMeta


class AnalyseError(Exception):
    """分析时发生错误"""


dev_space = Namespace("devtool", enable_message_cache=False)


class _DummyAnalyser(Analyser):
    filter_out = []

    class _DummyALC:
        options = []
        meta = namedtuple("Meta", ["keep_crlf", "fuzzy_match", "raise_exception"])(False, False, True)
        namespace_config = dev_space

    def __new__(cls, *args, **kwargs):
        cls.command = cls._DummyALC()  # type: ignore
        cls.compile_params = {}
        cls.compact_params = []
        return super().__new__(cls)


def analyse_args(
    args: Args,
    command: list[str | Any],
    raise_exception: bool = True,
    context_style: Literal["bracket", "parentheses"] | None = None,
    **kwargs
):
    meta = CommandMeta(keep_crlf=False, fuzzy_match=False, raise_exception=raise_exception, context_style=context_style)
    argv = Argv(meta, dev_space)
    try:
        argv.enter(kwargs)
        argv.build(["test"] + command)
        argv.next()
        return ala(argv, args)
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return {}


def analyse_header(
    headers: list[str | Any] | list[tuple[Any, str]],
    command_name: str,
    command: DataCollection[str | Any],
    sep: str = " ",
    compact: bool = False,
    raise_exception: bool = True,
    context_style: Literal["bracket", "parentheses"] | None = None,
    **kwargs
):
    meta = CommandMeta(keep_crlf=False, fuzzy_match=False, raise_exception=raise_exception, context_style=context_style)
    argv = Argv(meta, dev_space, separators=(sep,))
    command_header = Header.generate(command_name, headers, compact=compact)
    try:
        argv.enter(kwargs)
        argv.build(command)
        return HEAD_HANDLES[command_header.flag](command_header, argv)
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return


def analyse_option(
    option: Option,
    command: DataCollection[str | Any],
    raise_exception: bool = True,
    context_style: Literal["bracket", "parentheses"] | None = None,
    **kwargs
):
    meta = CommandMeta(keep_crlf=False, fuzzy_match=False, raise_exception=raise_exception, context_style=context_style)
    argv = Argv(meta, dev_space)
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.command.separators = (" ",)
    _analyser.need_main_args = False
    _analyser.command.options.append(option)
    default_compiler(_analyser, argv.param_ids)
    _analyser.command.options.clear()
    try:
        argv.enter(kwargs)
        argv.build(command)
        alo(_analyser, argv, option)
        return _analyser.options_result[option.dest]
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return


def analyse_subcommand(
    subcommand: Subcommand,
    command: DataCollection[str | Any],
    raise_exception: bool = True,
    context_style: Literal["bracket", "parentheses"] | None = None,
    **kwargs
):
    meta = CommandMeta(keep_crlf=False, fuzzy_match=False, raise_exception=raise_exception, context_style=context_style)
    argv = Argv(meta, dev_space)
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.command.separators = (" ",)
    _analyser.need_main_args = False
    _analyser.command.options.append(subcommand)
    default_compiler(_analyser, argv.param_ids)
    _analyser.command.options.clear()
    try:
        argv.enter(kwargs)
        argv.build(command)
        return _analyser.compile_params[subcommand.name].process(argv).result()  # type: ignore
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return
