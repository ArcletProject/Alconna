from __future__ import annotations

import re
import traceback
from copy import copy
from typing import TYPE_CHECKING, Any, Generic, TypeVar, Callable
from dataclasses import dataclass, field, InitVar
from typing_extensions import Self

from nepattern import pattern_map, type_parser, BasePattern
from nepattern.util import TPattern

from ..exceptions import (
    ParamsUnmatched,
    ArgumentMissing,
    FuzzyMatchSuccess,
    PauseTriggered,
    SpecialOptionTriggered,
    NullMessage
)
from ..args import Args
from ..base import Option, Subcommand
from ..model import Sentence, HeadResult, OptionResult, SubcommandResult
from ..arparma import Arparma
from ..typing import TDataCollection
from ..config import config, Namespace
from ..output import output_manager
from .parts import analyse_args, analyse_param, analyse_header
from .container import DataCollectionContainer, TContainer

if TYPE_CHECKING:
    from ..core import Alconna


def handle_help(analyser: Analyser):
    _help_param = [str(i) for i in analyser.container.release(recover=True) if i not in analyser.special]
    output_manager.send(
        analyser.command.name,
        lambda: analyser.command.formatter.format_node(_help_param),
        analyser.raise_exception
    )
    return analyser.export(fail=True)

def handle_bracket(name: str):
    if len(parts := re.split(r"(\{.*?})", name)) <= 1:
        return name
    for i, part in enumerate(parts):
        if not part:
            continue
        if part.startswith('{') and part.endswith('}'):
            res = part[1:-1].split(':')
            if not res or (len(res) > 1 and not res[1] and not res[0]):
                parts[i] = ".+?"
            elif len(res) == 1 or not res[1]:
                parts[i] = f"(?P<{res[0]}>.+?)"
            elif not res[0]:
                parts[i] = f"{pattern_map[res[1]].pattern if res[1] in pattern_map else res[1]}"
            else:
                parts[i] = f"(?P<{res[0]}>{pattern_map[res[1]].pattern if res[1] in pattern_map else res[1]})"
    return "".join(parts)

@dataclass
class SubAnalyser(Generic[TContainer]):
    command: Subcommand
    container: TContainer
    namespace: InitVar[Namespace]

    default_main_only: bool = field(default=False)  # 默认只有主参数
    part_len: range = field(default=range(0))  # 分段长度
    need_main_args: bool = field(default=False)  # 是否需要主参数

    compile_params: dict[str, Sentence | list[Option] | SubAnalyser[TContainer]] = field(default_factory=dict)

    self_args: Args = field(init=False)  # 自身参数
    subcommands_result: dict[str, SubcommandResult] = field(init=False)
    options_result: dict[str, OptionResult] = field(init=False)  # 存放解析到的所有选项
    args_result: dict[str, Any] = field(init=False)  # 参数的解析结果
    header_result: tuple[Any, ...] = field(init=False)
    value_result: Any = field(init=False)
    sentences: list[str] = field(init=False)  # 存放解析到的所有句子

    def _clr(self):
        self.reset()
        self.container.reset()
        ks = list(self.__dict__.keys())
        for k in ks:
            delattr(self, k)

    def __post_init__(self, namespace: Namespace):
        self.reset()
        self.container.reset()
        self.special = namespace.builtin_option_name['help']
        self.self_args = self.command.args
        self.__handle_args__()

    def export(self) -> SubcommandResult:
        res = SubcommandResult(
            self.value_result, self.args_result.copy(), self.options_result.copy(), self.subcommands_result.copy()
        )
        self.reset()
        return res

    def reset(self):
        """重置分析器"""
        self.args_result, self.options_result, self.subcommands_result = {}, {}, {}
        self.sentences, self.value_result, self.header_result = [], None, ()

    def __handle_args__(self):
        if self.command.nargs > 0 and self.command.nargs > self.self_args.optional_count:
            self.need_main_args = True  # 如果need_marg那么match的元素里一定得有main_argument
        _de_count = sum(arg.field.default_gen is not None for arg in self.self_args.argument)
        if _de_count and _de_count == self.command.nargs:
            self.default_main_only = True

    def process(self) -> Self:
        param = self.container.context = self.command
        if param.requires and self.sentences != param.requires:
            raise ParamsUnmatched(f"{param.name}'s required is not '{' '.join(self.sentences)}'")
        self.sentences = []
        if param.is_compact:
            name, _ = self.container.popitem()
            if not name.startswith(param.name):
                raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
            self.container.pushback(name.lstrip(param.name), replace=True)
        else:
            name, _ = self.container.popitem(param.separators)
            if name != param.name:  # 先匹配选项名称
                raise ParamsUnmatched(f"{name} dose not matched with {param.name}")

        if self.part_len.stop == 0:
            self.value_result = Ellipsis
            return self
        return self.analyse()

    def analyse(self) -> Self:
        for _ in self.part_len:
            _t, _s = self.container.popitem(self.command.separators, move=False)
            analyse_param(self, _t, _s)
        if self.default_main_only and not self.args_result:
            self.args_result = analyse_args(self, self.self_args, self.command.nargs)
        if not self.args_result and self.need_main_args:
            raise ArgumentMissing(config.lang.subcommand_args_missing.format(name=self.command.dest))
        return self

    def get_sub_analyser(self, target: Subcommand):
        if target == self.command:
            return self
        for param in self.compile_params.values():
            if isinstance(param, SubAnalyser):
                return param.get_sub_analyser(target)


class Analyser(SubAnalyser[TContainer], Generic[TContainer, TDataCollection]):
    command: Alconna  # Alconna实例
    # 命令头部
    command_header: (
        BasePattern | TPattern | list[tuple[Any, TPattern]] |
        tuple[tuple[list[Any], TPattern] | list[Any], TPattern | BasePattern]
    )
    container_type: type[TContainer]
    _global_container_type = DataCollectionContainer


    def __init__(self, alconna: Alconna, container_type: type[TContainer] | None = None):
        _type: type[TContainer] = container_type or self.__class__._global_container_type  # type: ignore
        super().__init__(
            alconna,
            _type(
                separators=alconna.separators,
                filter_crlf=not alconna.meta.keep_crlf,
            ),
            alconna.namespace_config
        )
        self.raise_exception = alconna.meta.raise_exception
        self.default_separate = True
        self.__init_header__(alconna.command, alconna.headers)

    @classmethod
    def default_container(cls, __t: type[TContainer] | None = None) -> type[Analyser[TContainer, TDataCollection]]:
        """配置 Analyser 的默认容器"""
        if __t is not None:
            cls._global_container_type = __t
        return cls

    def __init_header__(
        self, command_name: str | type | BasePattern, headers: list[Any] | list[tuple[Any, str]]
    ):
        if isinstance(command_name, str):
            command_name = handle_bracket(command_name)

        _cmd_name, _cmd_str = (
            (re.compile(command_name), command_name) if isinstance(command_name, str) else
            (copy(type_parser(command_name)), str(command_name))
        )
        if not headers:
            self.command_header = _cmd_name  # type: ignore
        elif isinstance(headers[0], tuple):
            mixins = [(h[0], re.compile(re.escape(h[1]) + _cmd_str)) for h in headers]  # type: ignore
            self.command_header = mixins
        else:
            elements = []
            ch_text = ""
            for h in headers:
                if isinstance(h, str):
                    ch_text += f"{re.escape(h)}|"
                else:
                    elements.append(h)
            if not elements:
                if isinstance(_cmd_name, TPattern):
                    self.command_header = re.compile(f"(?:{ch_text[:-1]}){_cmd_str}")  # noqa
                else:
                    _cmd_name.pattern = f"(?:{ch_text[:-1]}){_cmd_name.pattern}"  # type: ignore
                    _cmd_name.regex_pattern = re.compile(_cmd_name.pattern)  # type: ignore
                    self.command_header = _cmd_name  # type: ignore
            elif not ch_text:
                self.command_header = (elements, _cmd_name)  # type: ignore
            else:
                self.command_header = (elements, re.compile(f"(?:{ch_text[:-1]})")), _cmd_name  # type: ignore # noqa

    def __repr__(self):
        return f"<{self.__class__.__name__} of {self.command.path}>"

    def process(self, message: TDataCollection | None = None, interrupt: bool = False) -> Arparma[TDataCollection]:
        """主体解析函数, 应针对各种情况进行解析"""

        if self.container.ndata == 0:
            if not message:
                raise NullMessage(config.lang.analyser_handle_null_message.format(target=message))
            try:
                self.container.build(message)
            except Exception as e:
                return self.export(fail=True, exception=e)
        try:
            self.header_result = analyse_header(self)
        except ParamsUnmatched as e:
            self.container.current_index = 0
            if self.raise_exception:
                raise e
            return self.export(fail=True, exception=e)

        if fail := self.analyse(interrupt):
            return fail

        if self.container.done and (not self.need_main_args or self.args_result):
            return self.export()

        rest = self.container.release()
        if len(rest) > 0:
            exc = ParamsUnmatched(config.lang.analyser_param_unmatched.format(target=self.container.popitem(move=False)[0]))
        else:
            exc = ArgumentMissing(config.lang.analyser_param_missing)
        if interrupt and isinstance(exc, ArgumentMissing):
            raise PauseTriggered(self)
        if self.raise_exception:
            raise exc
        return self.export(fail=True, exception=exc)

    def analyse(self, interrupt: bool = False) -> Arparma[TDataCollection] | None:
        for _ in self.part_len:
            try:
                _t, _s = self.container.popitem(move=False)
                analyse_param(self, _t, _s)
            except FuzzyMatchSuccess as e:
                output_manager.send(self.command.name, lambda: str(e), self.raise_exception)
                return self.export(fail=True)
            except SpecialOptionTriggered:
                return handle_help(self)
            except (ParamsUnmatched, ArgumentMissing) as e1:
                if (rest := self.container.release()) and isinstance(rest[-1], str):
                    if rest[-1] in self.special:
                        return handle_help(self)
                if interrupt and isinstance(e1, ArgumentMissing):
                    raise PauseTriggered(self) from e1
                if self.raise_exception:
                    raise
                return self.export(fail=True, exception=e1)
            if self.container.done:
                break

        if self.default_main_only and not self.args_result:
            self.args_result = analyse_args(self, self.self_args, self.command.nargs)

    def export(self, exception: BaseException | None = None, fail: bool = False) -> Arparma[TDataCollection]:
        """创建arpamar, 其一定是一次解析的最后部分"""
        result = Arparma(self.command, self.container.origin, not fail, HeadResult(*self.header_result))
        if fail:
            result.error_info = repr(exception or traceback.format_exc(limit=1))
            result.error_data = self.container.release()
        else:
            result.encapsulate_result(self.args_result, self.options_result, self.subcommands_result)
        self.reset()
        return result  # type: ignore


TAnalyser = TypeVar("TAnalyser", bound=Analyser)

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
            sub = SubAnalyser(opts, analyser.container, _config)
            analyser.compile_params[opts.name] = sub
            analyser.container.param_ids.add(opts.name)
            default_params_parser(sub, _config)
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


def compile(alconna: Alconna[TAnalyser], params_parser: Callable[[TAnalyser, Namespace], None] = default_params_parser) -> TAnalyser:
    _analyser = alconna.analyser_type(alconna)
    params_parser(_analyser, alconna.namespace_config)
    return _analyser


def analyse(alconna: Alconna, command: TDataCollection) -> Arparma[TDataCollection]:
    return compile(alconna).process(command).analyse().execute()