from __future__ import annotations

import re
import traceback
from copy import copy
from typing import TYPE_CHECKING, Any, Generic, TypeVar, Callable
from dataclasses import dataclass, field, InitVar
from typing_extensions import Self

from nepattern import pattern_map, type_parser, BasePattern
from nepattern.util import TPattern

from ..manager import command_manager
from ..exceptions import (
    ParamsUnmatched,
    ArgumentMissing,
    FuzzyMatchSuccess,
    CompletionTriggered,
    PauseTriggered,
    SpecialOptionTriggered,
    NullMessage
)
from ..args import Args
from ..base import Option, Subcommand
from ..model import Sentence, HeadResult, OptionResult, SubcommandResult
from ..arparma import Arparma
from ..typing import DataCollection, TDataCollection
from ..config import config, Namespace
from ..components.output import output_manager
from .parts import analyse_args, analyse_param, analyse_header
from .special import handle_help, handle_shortcut, handle_completion
from .container import DataCollectionContainer

if TYPE_CHECKING:
    from ..core import Alconna


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
class SubAnalyser:
    command: Subcommand
    container: DataCollectionContainer
    namespace: InitVar[Namespace]

    fuzzy_match: bool = field(default=False)
    default_main_only: bool = field(default=False)  # 默认只有主参数
    part_len: range = field(default=range(0))  # 分段长度
    need_main_args: bool = field(default=False)  # 是否需要主参数

    compile_params: dict[str, Sentence | list[Option] | SubAnalyser] = field(default_factory=dict)

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
        self.special = {}
        self.special.update(
            [(i, handle_help) for i in namespace.builtin_option_name['help']] +
            [(i, handle_completion) for i in namespace.builtin_option_name['completion']] +
            [(i, handle_shortcut) for i in namespace.builtin_option_name['shortcut']]
        )
        self.completion_names = namespace.builtin_option_name['completion']
        self.self_args = self.command.args
        self.__handle_args__()

    def export(self) -> SubcommandResult:
        res = SubcommandResult(
            self.value_result,
            self.args_result.copy(),
            self.options_result.copy(),
            self.subcommands_result.copy()
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


class Analyser(SubAnalyser, Generic[TDataCollection]):
    command: Alconna  # Alconna实例
    used_tokens: set[int]  # 已使用的token
    # 命令头部
    command_header: (
        BasePattern | TPattern | list[tuple[Any, TPattern]] |
        tuple[tuple[list[Any], TPattern] | list[Any], TPattern | BasePattern]
    )
    _cache = {}


    def __init__(self, alconna: Alconna):
        super().__init__(
            alconna,
            DataCollectionContainer(
                separators=alconna.separators,
                filter_crlf=not alconna.meta.keep_crlf,
                message_cache=alconna.namespace_config.enable_message_cache,
                preprocessors=self._cache.get(self.__class__, {}).get("processors", {}),
                text_sign=self._cache.get(self.__class__, {}).get("text_sign", "text"),
                filter_out=self._cache.get(self.__class__, {}).get("filter_out", []),
            ),
            alconna.namespace_config
        )
        self.raise_exception = alconna.meta.raise_exception
        self.fuzzy_match = alconna.meta.fuzzy_match
        self.used_tokens = set()
        self.default_separate = True
        self.__init_header__(alconna.command, alconna.headers)

    @classmethod
    def config(
        cls,
        processors: dict[str, Callable[..., Any]] | None = None,
        text_sign: str | None = None,
        filter_out: list[str] | None = None
    ):
        """特殊方法，用于自定义 preprocessors、text_sign、filter_out之类"""
        processors = processors or {}
        text_sign = text_sign or "text"
        filter_out = filter_out or []
        cls._cache.setdefault(cls, {}).update(locals())

    def _clr(self):
        self.used_tokens.clear()
        super()._clr()

    @staticmethod
    def converter(command: str) -> TDataCollection:
        return command  # type: ignore
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

    def process(self, message: DataCollection[str | Any] | None = None, interrupt: bool = False) -> Arparma[TDataCollection]:
        """主体解析函数, 应针对各种情况进行解析"""
        if command_manager.is_disable(self.command):
            return self.export(fail=True)

        if self.container.ndata == 0:
            if not message:
                raise NullMessage(config.lang.analyser_handle_null_message.format(target=message))
            try:
                self.container.build(message)
            except Exception as e:
                return self.export(fail=True, exception=e)
        if (res := command_manager.get_record(self.container.temp_token)) and self.container.temp_token in self.used_tokens:
            self.reset()
            return res
        try:
            self.header_result = analyse_header(self)
            # self.head_pos = self.current_index
        except ParamsUnmatched as e:
            self.container.current_index = 0
            try:
                _res = command_manager.find_shortcut(self.container.popitem(move=False)[0], self.command)
                self.reset()
                self.container.reset()
                return _res if isinstance(_res, Arparma) else self.process(_res)
            except ValueError as exc:
                if self.raise_exception:
                    raise e from exc
                return self.export(fail=True, exception=e)
        except FuzzyMatchSuccess as Fuzzy:
            output_manager.send(self.command.name, lambda: str(Fuzzy), self.raise_exception)
            return self.export(fail=True)

        if fail := self.analyse(interrupt):
            return fail

        if self.container.done and (not self.need_main_args or self.args_result):
            return self.export()

        rest = self.container.release()
        if len(rest) > 0:
            if rest[-1] in self.completion_names:
                return handle_completion(self, rest[-2])
            exc = ParamsUnmatched(config.lang.analyser_param_unmatched.format(target=self.container.popitem(move=False)[0]))
        else:
            exc = ArgumentMissing(config.lang.analyser_param_missing)
        if interrupt and isinstance(exc, ArgumentMissing):
            raise PauseTriggered
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
            except SpecialOptionTriggered as sot:
                return sot.args[0](self)
            except CompletionTriggered as comp:
                return handle_completion(self, comp.args[0])
            except (ParamsUnmatched, ArgumentMissing) as e1:
                if rest := self.container.release():
                    if rest[-1] in self.completion_names:
                        return handle_completion(self, self.context)  # type: ignore
                    if handler := self.special.get(rest[-1]):
                        return handler(self)
                if interrupt and isinstance(e1, ArgumentMissing):
                    raise PauseTriggered from e1
                if self.raise_exception:
                    raise
                return self.export(fail=True, exception=e1)
            if self.container.done:
                break

        if self.default_main_only and not self.args_result:
            self.args_result = analyse_args(self, self.self_args, self.command.nargs)

    def export(self, exception: BaseException | None = None, fail: bool = False) -> Arparma[TDataCollection]:
        """创建arpamar, 其一定是一次解析的最后部分"""
        result = Arparma(self.command.path, self.container.origin, not fail, HeadResult(*self.header_result))
        if fail:
            result.error_info = repr(exception or traceback.format_exc(limit=1))
            result.error_data = self.container.release()
        else:
            result.encapsulate_result(self.args_result, self.options_result, self.subcommands_result)
            if self.container.message_cache:
                command_manager.record(self.container.temp_token, result)
                self.used_tokens.add(self.container.temp_token)
        self.reset()
        return result  # type: ignore


TAnalyser = TypeVar("TAnalyser", bound=Analyser)
