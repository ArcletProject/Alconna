from __future__ import annotations

from collections import namedtuple
from typing import Any
import traceback

from arclet.alconna.analyser import Analyser, default_compiler
from arclet.alconna.argv import Argv
from arclet.alconna.handlers import analyse_args as ala, analyse_header as alh, analyse_option as alo
from arclet.alconna.header import Header
from arclet.alconna.typing import DataCollection
from arclet.alconna.base import Option, Subcommand
from arclet.alconna.args import Args
from arclet.alconna.config import config


class AnalyseError(Exception):
    """分析时发生错误"""


class _DummyAnalyser(Analyser):
    filter_out = []

    class _DummyALC:
        options = []
        meta = namedtuple("Meta", ["keep_crlf", "fuzzy_match"])(False, False)
        namespace_config = config.default_namespace

    def __new__(cls, *args, **kwargs):
        cls.command = cls._DummyALC()  # type: ignore
        cls.compile_params = {}
        cls.compact_params = []
        return super().__new__(cls)


def analyse_args(args: Args, command: list[str | Any], raise_exception: bool = True):
    argv = Argv(config.default_namespace, message_cache=False, filter_crlf=True)
    try:
        argv.build(["test"] + command)
        argv.next()
        return ala(argv, args)
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return


def analyse_header(
    headers: list[str | Any] | list[tuple[Any, str]],
    command_name: str,
    command: DataCollection[str | Any],
    sep: str = " ",
    raise_exception: bool = True
):
    argv = Argv(
        config.default_namespace,
        message_cache=False,
        filter_crlf=True,
        separators=(sep, )
    )
    command_header = Header.generate(command_name, headers)
    try:
        argv.build(command)
        return alh(command_header, argv)
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return


def analyse_option(option: Option, command: DataCollection[str | Any], raise_exception: bool = True):
    argv = Argv(config.default_namespace, message_cache=False, filter_crlf=True)
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.command.separators = (" ",)
    _analyser.need_main_args = False
    _analyser.raise_exception = True
    _analyser.command.options.append(option)
    default_compiler(_analyser, _analyser.command.namespace_config, argv.param_ids)
    _analyser.command.options.clear()
    try:
        argv.build(command)
        return alo(argv, option)
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return


def analyse_subcommand(subcommand: Subcommand, command: DataCollection[str | Any], raise_exception: bool = True):
    argv = Argv(config.default_namespace, message_cache=False, filter_crlf=True)
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.command.separators = (" ", )
    _analyser.need_main_args = False
    _analyser.raise_exception = True
    _analyser.command.options.append(subcommand)
    default_compiler(_analyser, _analyser.command.namespace_config, argv.param_ids)
    _analyser.command.options.clear()
    try:
        argv.build(command)
        return _analyser.compile_params[subcommand.name].process(argv).result()  # type: ignore
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return
