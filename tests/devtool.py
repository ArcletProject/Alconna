from __future__ import annotations

import traceback
from collections import namedtuple
from typing import Any, Literal

from arclet.alconna.ingedia._analyser import Analyser
from arclet.alconna.ingedia._handlers import analyse_header as alh
from arclet.alconna.ingedia._handlers import analyse_args as ala
from arclet.alconna.ingedia._handlers import analyse_option as alo
from arclet.alconna.ingedia._handlers import analyse_subcommand as als
from arclet.alconna.base import ARGS_PARAM, handle_args
from arclet.alconna.ingedia._argv import Argv
from arclet.alconna.base import Option, Subcommand, Header, Config, OptionResult, SubcommandResult
from arclet.alconna.config import Namespace
from arclet.alconna.utils import DataCollection


class AnalyseError(Exception):
    """分析时发生错误"""


dev_space = Namespace("devtool", Config(enable_message_cache=False))


class _DummyAnalyser(Analyser):
    filter_out = []

    class _DummyALC:
        options = []
        config = namedtuple("Config", ["keep_crlf", "fuzzy_match", "raise_exception"])(False, False, True)
        namespace_config = dev_space

        @property
        def _lookup_map(self):
            return {al: opt for opt in self.options for al in opt.aliases}

    def __new__(cls, *args, **kwargs):
        cls.command = cls._DummyALC()  # type: ignore
        cls.compact_params = []
        cls.default_value_result = {}
        cls.args_optional = {}
        cls.args_result = {}
        cls._unvisited = {}
        return super().__new__(cls)


def analyse_args(
    args: ARGS_PARAM,
    command: list[str | Any],
    raise_exception: bool = True,
    context_style: Literal["bracket", "parentheses"] | None = None,
    **kwargs,
):
    conf = Config(keep_crlf=False, fuzzy_match=False, raise_exception=raise_exception, context_style=context_style)
    argv: Argv[DataCollection] = Argv(conf, dev_space)
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    try:
        argv.enter(kwargs)
        argv.build(["test"] + command)
        argv.next()
        return ala(_analyser, argv, handle_args(args))
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return {}


def analyse_header(
    headers: list[str | Any] | list[tuple[Any, str]],
    command_name: str,
    command: list[str | Any],
    sep: str = " ",
    compact: bool = False,
    raise_exception: bool = True,
    context_style: Literal["bracket", "parentheses"] | None = None,
    **kwargs,
):
    conf = Config(keep_crlf=False, fuzzy_match=False, raise_exception=raise_exception, context_style=context_style)
    argv: Argv[DataCollection] = Argv(conf, dev_space, separators=sep)
    command_header = Header.generate(command_name, headers, compact=compact)
    try:
        argv.enter(kwargs)
        argv.build(command)
        return alh(command_header, argv)
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return


def analyse_option(
    option: Option,
    command: list[str | Any],
    raise_exception: bool = True,
    context_style: Literal["bracket", "parentheses"] | None = None,
    **kwargs,
):
    conf = Config(keep_crlf=False, fuzzy_match=False, raise_exception=raise_exception, context_style=context_style)
    argv: Argv[DataCollection] = Argv(conf, dev_space)
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.command.separators = " "
    _analyser.args_optional[()] = False
    _analyser.command.options.append(option)
    _analyser.command.options.clear()
    try:
        argv.enter(kwargs)
        argv.build(command)
        alo(_analyser, option, argv, (option.dest,), False)
        return OptionResult(_analyser.value_result[(option.dest,)], _analyser.args_result[(option.dest,)])
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return


def analyse_subcommand(
    subcommand: Subcommand,
    command: list[str | Any],
    raise_exception: bool = True,
    context_style: Literal["bracket", "parentheses"] | None = None,
    **kwargs,
):
    conf = Config(keep_crlf=False, fuzzy_match=False, raise_exception=raise_exception, context_style=context_style)
    argv: Argv[DataCollection] = Argv(conf, dev_space)
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.command.separators = " "
    if subcommand.nargs:
        _analyser.args_optional[(subcommand.dest,)] = subcommand.args.optional_count == len(subcommand.args)
    _analyser.command.options.append(subcommand)
    _analyser.command.options.clear()
    try:
        argv.enter(kwargs)
        argv.build(command)
        _analyser.update(subcommand, ())
        als(_analyser, subcommand, argv, (subcommand.dest,), False)
        res = SubcommandResult(..., _analyser.args_result.get((subcommand.dest,)))
        for k, v in _analyser.value_result.items():
            if len(k) > 1 and k[0] == subcommand.dest:
                res.subcommands[k[1]] = SubcommandResult(v, _analyser.args_result.get(k))
        return res
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return
