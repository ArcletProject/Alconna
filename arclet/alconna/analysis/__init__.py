from typing import TYPE_CHECKING, Union, Callable, Optional, List, Any, Tuple
import traceback

from .analyser import Analyser
from .arg_handlers import multi_arg_handler, anti_arg_handler, common_arg_handler
from .parts import analyse_args as ala, analyse_header as alh, analyse_option as alo, analyse_subcommand as als
from ..arpamar import Arpamar
from ..types import DataCollection, MultiArg, ArgPattern, AntiArg, UnionArg, ObjectPattern, SequenceArg, MappingArg
from ..base import Args, Option, Subcommand

if TYPE_CHECKING:
    from ..main import Alconna


def compile(alconna: "Alconna", params_generator: Optional[Callable[[Analyser], None]] = None):
    _analyser = alconna.analyser_type(alconna)
    if params_generator:
        params_generator(_analyser)
    else:
        Analyser.default_params_generator(_analyser)
    return _analyser


def analyse(alconna: "Alconna", command: Union[str, DataCollection]) -> Arpamar:
    ana = compile(alconna)
    ana.process_message(command)
    return ana.analyse()


class AnalyseError(Exception):
    """分析时发生错误"""


class _DummyAnalyser(Analyser):
    filter_out = ["Source", "File", "Quote"]

    class _DummyALC:
        is_fuzzy_match = False

    def __new__(cls, *args, **kwargs):
        cls.alconna = cls._DummyALC()  # type: ignore
        cls.add_arg_handler(MultiArg, multi_arg_handler)
        cls.add_arg_handler(ArgPattern, common_arg_handler)
        cls.add_arg_handler(AntiArg, anti_arg_handler)
        cls.add_arg_handler(UnionArg, common_arg_handler)
        cls.add_arg_handler(ObjectPattern, common_arg_handler)
        cls.add_arg_handler(SequenceArg, common_arg_handler)
        cls.add_arg_handler(MappingArg, common_arg_handler)
        cls.command_params = {}
        cls.param_ids = []
        return super().__new__(cls)

    def analyse(self, message: Union[str, DataCollection, None] = None):
        pass

    def add_param(self, opt):
        pass


def analyse_args(
        args: Args,
        command: Union[str, DataCollection]
):
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.separator = ' '
    _analyser.is_raise_exception = True
    try:
        _analyser.process_message(command)
        return ala(_analyser, args, len(args))
    except Exception as e:
        traceback.print_exception(AnalyseError, e, e.__traceback__)


def analyse_header(
        headers: Union[List[Union[str, Any]], List[Tuple[Any, str]]],
        command_name: str,
        command: Union[str, DataCollection],
        sep: str = " "
):
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.separator = sep
    _analyser.is_raise_exception = True
    _analyser.process_message(command)
    _analyser.__init_header__(command_name, headers)
    r = alh(_analyser)
    if r is False:
        traceback.print_exception(
            AnalyseError, AnalyseError(f"header {_analyser.recover_raw_data()} analyse failed"), None
        )
    return r


def analyse_option(
        option: Option,
        command: Union[str, DataCollection],
):
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.separator = " "
    _analyser.is_raise_exception = True
    try:
        _analyser.process_message(command)
        return alo(_analyser, option)
    except Exception as e:
        traceback.print_exception(AnalyseError, e, e.__traceback__)


def analyse_subcommand(
        subcommand: Subcommand,
        command: Union[str, DataCollection],
):
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.separator = " "
    _analyser.is_raise_exception = True
    try:
        _analyser.process_message(command)
        return als(_analyser, subcommand)
    except Exception as e:
        traceback.print_exception(AnalyseError, e, e.__traceback__)
