from __future__ import annotations

from collections import namedtuple
from typing import Any
import traceback

from arclet.alconna.analysis.analyser import Analyser, default_params_parser
from arclet.alconna.analysis.container import DataCollectionContainer
from arclet.alconna.analysis.parts import analyse_args as ala, analyse_header as alh, analyse_option as alo
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
        cls.container = DataCollectionContainer(filter_crlf=True)
        cls.special = {}
        for i in config.default_namespace.builtin_option_name.values():
            cls.special.fromkeys(i, True)  # noqa  # type: ignore
        return super().__new__(cls)


def analyse_args(args: Args, command: DataCollection[str | Any], raise_exception: bool = True):
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.need_main_args = True
    _analyser.raise_exception = True
    try:
        _analyser.container.build(command)
        return ala(_analyser, args, len(args))
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
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.container.separators = (sep, )
    _analyser.need_main_args = False
    _analyser.__init_header__(command_name, headers)
    try:
        _analyser.container.build(command)
        return alh(_analyser)
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return


def analyse_option(option: Option, command: DataCollection[str | Any], raise_exception: bool = True):
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.container.separators = (" ", )
    _analyser.need_main_args = False
    _analyser.raise_exception = True
    _analyser.command.options.append(option)
    default_params_parser(_analyser, _analyser.command.namespace_config)
    _analyser.command.options.clear()
    try:
        _analyser.container.build(command)
        return alo(_analyser, option)
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return


def analyse_subcommand(subcommand: Subcommand, command: DataCollection[str | Any], raise_exception: bool = True):
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.container.separators = (" ", )
    _analyser.need_main_args = False
    _analyser.raise_exception = True
    _analyser.command.options.append(subcommand)
    default_params_parser(_analyser, _analyser.command.namespace_config)
    _analyser.command.options.clear()
    try:
        _analyser.container.build(command)
        return _analyser.compile_params[subcommand.name].process().export()  # type: ignore
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return