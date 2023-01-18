from __future__ import annotations

from collections import namedtuple
from typing import TYPE_CHECKING, Callable, Any 
import traceback

from .analyser import TAnalyser, SubAnalyser, Analyser
from .container import DataCollectionContainer
from .parts import analyse_args as ala, analyse_header as alh, analyse_option as alo
from ..typing import DataCollection, TDataCollection
from ..base import Option, Subcommand
from ..model import Sentence
from ..args import Args
from ..config import config, Namespace

if TYPE_CHECKING:
    from ..arparma import Arparma
    from ..core import Alconna


def _compile_opts(option: Option, data: dict[str, Sentence | list[Option] | SubAnalyser]):
    for alias in option.aliases:
        if (li := data.get(alias)) and isinstance(li, list):
            li.append(option)  # type: ignore
            li.sort(key=lambda x: x.priority, reverse=True)
        else:
            data[alias] = [option]



def default_params_parser(analyser: SubAnalyser, _config: Namespace):
    require_len = 0
    for opts in analyser.command.options:
        if isinstance(opts, Option):
            _compile_opts(opts, analyser.compile_params)  # type: ignore
            analyser.container.param_ids.update(opts.aliases)
        elif isinstance(opts, Subcommand):
            analyser.compile_params[opts.name] = SubAnalyser(opts, analyser.container, _config, analyser.fuzzy_match)
            analyser.container.param_ids.add(opts.name)
            default_params_parser(analyser.compile_params[opts.name], _config)
        if not set(analyser.container.separators).issuperset(opts.separators):
            analyser.container.default_separate &= False
        if opts.requires:
            analyser.container.param_ids.update(opts.requires)
            require_len = max(len(opts.requires), require_len)
            for k in opts.requires:
                analyser.compile_params.setdefault(k, Sentence(name=k))
    analyser.part_len = range(
        len(analyser.command.options) + analyser.need_main_args + require_len
    )


def compile(alconna: Alconna, params_parser: Callable[[TAnalyser, Namespace], None] = default_params_parser) -> TAnalyser:
    _analyser = alconna.analyser_type(alconna)
    params_parser(_analyser, alconna.namespace_config)
    return _analyser


def analyse(alconna: Alconna, command: TDataCollection) -> Arparma[TDataCollection]:
    return compile(alconna).process(command).analyse().execute()


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
        cls.container = DataCollectionContainer(message_cache=False, filter_crlf=True)
        cls.special = {}
        for i in config.default_namespace.builtin_option_name.values():
            cls.special.fromkeys(i, True)  # noqa
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
