from typing import TYPE_CHECKING, Union, Callable, Optional, List, Any, Tuple
import traceback

from .analyser import Analyser
from .parts import analyse_args as ala, analyse_header as alh, analyse_option as alo, analyse_subcommand as als
from ..typing import DataCollection
from ..base import Args, Option, Subcommand

if TYPE_CHECKING:
    from ..arpamar import Arpamar
    from ..core import Alconna


def compile(alconna: "Alconna", params_generator: Optional[Callable[[Analyser], None]] = None):
    _analyser = alconna.analyser_type(alconna)
    if params_generator:
        params_generator(_analyser)
    else:
        Analyser.default_params_generator(_analyser)
    return _analyser


def analyse(alconna: "Alconna", command: Union[str, DataCollection]) -> "Arpamar":
    ana = compile(alconna)
    ana.process_message(command)
    return ana.analyse().execute()


class AnalyseError(Exception):
    """分析时发生错误"""


class _DummyAnalyser(Analyser):
    filter_out = ["Source", "File", "Quote"]

    class _DummyALC:
        is_fuzzy_match = False

    def __new__(cls, *args, **kwargs):
        cls.alconna = cls._DummyALC()  # type: ignore
        cls.command_params = {}
        cls.param_ids = []
        return super().__new__(cls)

    def analyse(self, message: Union[str, DataCollection, None] = None):
        pass


def analyse_args(
        args: Args,
        command: Union[str, DataCollection],
        raise_exception: bool = True
):
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.separators = {' '}
    _analyser.is_raise_exception = True
    try:
        _analyser.process_message(command)
        return ala(_analyser, args, len(args))
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return


def analyse_header(
        headers: Union[List[Union[str, Any]], List[Tuple[Any, str]]],
        command_name: str,
        command: Union[str, DataCollection],
        sep: str = " ",
        raise_exception: bool = True
):
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.separators = {sep}
    _analyser.is_raise_exception = True
    _analyser.__init_header__(command_name, headers)
    try:
        _analyser.process_message(command)
        return alh(_analyser)
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return


def analyse_option(
        option: Option,
        command: Union[str, DataCollection],
        raise_exception: bool = True
):
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.separators = {" "}
    _analyser.is_raise_exception = True
    try:
        _analyser.process_message(command)
        return alo(_analyser, option)
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return


def analyse_subcommand(
        subcommand: Subcommand,
        command: Union[str, DataCollection],
        raise_exception: bool = True
):
    _analyser = _DummyAnalyser.__new__(_DummyAnalyser)
    _analyser.reset()
    _analyser.separators = {" "}
    _analyser.is_raise_exception = True
    try:
        _analyser.process_message(command)
        return als(_analyser, subcommand)
    except Exception as e:
        if raise_exception:
            traceback.print_exception(AnalyseError, e, e.__traceback__)
        return
