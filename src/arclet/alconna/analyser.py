from __future__ import annotations

import re
import traceback
from re import Match
from typing import TYPE_CHECKING, Any, Generic, Callable
from dataclasses import dataclass, field, InitVar
from typing_extensions import Self, TypeVar

from nepattern import BasePattern
from nepattern.util import TPattern

from .manager import command_manager, ShortcutArgs
from .exceptions import (
    ParamsUnmatched,
    ArgumentMissing,
    FuzzyMatchSuccess,
    PauseTriggered,
    SpecialOptionTriggered,
    NullMessage
)
from .args import Args
from .header import handle_header, Pair, Double
from .base import Option, Subcommand
from .completion import comp_ctx
from .model import Sentence, HeadResult, OptionResult, SubcommandResult
from .arparma import Arparma
from .typing import TDataCollection
from .config import config, Namespace
from .output import output_manager
from .handlers import analyse_args, analyse_param, analyse_header, handle_help, handle_shortcut, handle_completion, prompt
from .container import DataCollectionContainer, TContainer

if TYPE_CHECKING:
    from .core import Alconna


def _compile_opts(option: Option, data: dict[str, Sentence | list[Option] | SubAnalyser]):
    for alias in option.aliases:
        if (li := data.get(alias)) and isinstance(li, list):
            li.append(option)  # type: ignore
            li.sort(key=lambda x: x.priority, reverse=True)
        else:
            data[alias] = [option]


def default_compiler(analyser: SubAnalyser, _config: Namespace):
    require_len = 0
    for opts in analyser.command.options:
        if isinstance(opts, Option):
            _compile_opts(opts, analyser.compile_params)  # type: ignore
            analyser.container.param_ids.update(opts.aliases)
        elif isinstance(opts, Subcommand):
            sub = SubAnalyser(opts, analyser.container, _config, analyser.fuzzy_match)
            analyser.compile_params[opts.name] = sub
            analyser.container.param_ids.add(opts.name)
            default_compiler(sub, _config)
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


@dataclass
class SubAnalyser(Generic[TContainer]):
    command: Subcommand
    container: TContainer
    namespace: InitVar[Namespace]

    fuzzy_match: bool = field(default=False)
    default_main_only: bool = field(default=False)  # 默认只有主参数
    part_len: range = field(default=range(0))  # 分段长度
    need_main_args: bool = field(default=False)  # 是否需要主参数

    compile_params: dict[str, Sentence | list[Option] | SubAnalyser[TContainer]] = field(default_factory=dict)

    self_args: Args = field(init=False)  # 自身参数
    subcommands_result: dict[str, SubcommandResult] = field(init=False)
    options_result: dict[str, OptionResult] = field(init=False)  # 存放解析到的所有选项
    args_result: dict[str, Any] = field(init=False)  # 参数的解析结果
    header_result: HeadResult | None = field(init=False)
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
            self.value_result, self.args_result.copy(), self.options_result.copy(), self.subcommands_result.copy()
        )
        self.reset()
        return res

    def reset(self):
        """重置分析器"""
        self.args_result, self.options_result, self.subcommands_result = {}, {}, {}
        self.sentences, self.value_result, self.header_result = [], None, None

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
            analyse_param(self, *self.container.popitem(self.command.separators, move=False))
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
    used_tokens: set[int]  # 已使用的token
    # 命令头部
    command_header: TPattern | BasePattern | list[Pair] | Double
    _global_container_type = DataCollectionContainer

    def __init__(self, alconna: Alconna, container_type: type[TContainer] | None = None):
        _type: type[TContainer] = container_type or self.__class__._global_container_type  # type: ignore
        super().__init__(
            alconna,
            _type(
                to_text=alconna.namespace_config.to_text,
                separators=alconna.separators,
                message_cache=alconna.namespace_config.enable_message_cache,
                filter_crlf=not alconna.meta.keep_crlf,
            ),
            alconna.namespace_config
        )
        self.fuzzy_match = alconna.meta.fuzzy_match
        self.used_tokens = set()
        self.command_header = handle_header(alconna.command, alconna.headers)

    @classmethod
    def default_container(cls, __t: type[TContainer] | None = None) -> type[Analyser[TContainer, TDataCollection]]:
        """配置 Analyser 的默认容器"""
        if __t is not None:
            cls._global_container_type = __t
        return cls

    def _clr(self):
        self.used_tokens.clear()
        super()._clr()

    @staticmethod
    def converter(command: str) -> TDataCollection:
        return command  # type: ignore

    def __repr__(self):
        return f"<{self.__class__.__name__} of {self.command.path}>"

    def shortcut(self, data: list[Any], short: Arparma | ShortcutArgs, reg: Match | None) -> Arparma[TDataCollection]:
        if isinstance(short, Arparma):
            return short
        self.container.build(short['command'])
        data_index = 0
        for i, unit in enumerate(self.container.raw_data):
            if not data:
                break
            if not isinstance(unit, str):
                continue
            if unit == f"{{%{data_index}}}":
                self.container.raw_data[i] = data.pop(0)
                data_index += 1
            elif f"{{%{data_index}}}" in unit:
                self.container.raw_data[i] = unit.replace(f"{{%{data_index}}}", str(data.pop(0)))
                data_index += 1
            elif mat := re.search(r"\{\*(.*)\}", unit, re.DOTALL):
                sep = mat[1]
                self.container.raw_data[i] = unit.replace(f"{{*{sep}}}", (sep or ' ').join(map(str, data)))
                data.clear()

        self.container.bak_data = self.container.raw_data.copy()
        self.container.rebuild(*data).rebuild(*short.get('args', []))
        if reg:
            groups: tuple[str, ...] = reg.groups()
            gdict: dict[str, str] = reg.groupdict()
            for j, unit in enumerate(self.container.raw_data):
                if not isinstance(unit, str):
                    continue
                for i, c in enumerate(groups):
                    unit = unit.replace(f"{{{i}}}", c)
                for k, v in gdict.items():
                    unit = unit.replace(f"{{{k}}}", v)
                self.container.raw_data[j] = unit
        if self.container.message_cache:
            self.container.temp_token = self.container.generate_token(self.container.raw_data)
        return self.process()

    def process(self, message: TDataCollection | None = None) -> Arparma[TDataCollection]:
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
        if (
            self.container.message_cache and
            self.container.temp_token in self.used_tokens and
            (res := command_manager.get_record(self.container.temp_token))
        ):
            return res
        try:
            self.header_result = analyse_header(self)
        except ParamsUnmatched as e:
            self.container.raw_data = self.container.bak_data.copy()
            self.container.current_index = 0
            try:
                _res = command_manager.find_shortcut(self.command, self.container.popitem(move=False)[0])
            except ValueError as exc:
                if self.command.meta.raise_exception:
                    raise e from exc
                return self.export(fail=True, exception=e)
            else:
                self.container.popitem()
                data = self.container.release()
                self.reset()
                self.container.reset()
                return self.shortcut(data, *_res)

        except FuzzyMatchSuccess as Fuzzy:
            output_manager.send(self.command.name, lambda: str(Fuzzy))
            return self.export(fail=True)

        if fail := self.analyse():
            return fail

        if self.container.done and (not self.need_main_args or self.args_result):
            return self.export()

        rest = self.container.release()
        if len(rest) > 0:
            if isinstance(rest[-1], str) and rest[-1] in self.completion_names:
                return handle_completion(self, rest[-2])
            exc = ParamsUnmatched(config.lang.analyser_param_unmatched.format(target=self.container.popitem(move=False)[0]))
        else:
            exc = ArgumentMissing(config.lang.analyser_param_missing)
        if isinstance(exc, ArgumentMissing) and comp_ctx.get(None):
            raise PauseTriggered(prompt(self, self.container.context))
        if self.command.meta.raise_exception:
            raise exc
        return self.export(fail=True, exception=exc)

    def analyse(self) -> Arparma[TDataCollection] | None:
        for _ in self.part_len:
            try:
                analyse_param(self, *self.container.popitem(move=False))
            except FuzzyMatchSuccess as e:
                output_manager.send(self.command.name, lambda: str(e))
                return self.export(fail=True)
            except SpecialOptionTriggered as sot:
                return sot.args[0](self)
            except (ParamsUnmatched, ArgumentMissing) as e1:
                if (rest := self.container.release()) and isinstance(rest[-1], str):
                    if rest[-1] in self.completion_names:
                        return handle_completion(self)
                    if handler := self.special.get(rest[-1]):
                        return handler(self)
                if isinstance(e1, ArgumentMissing) and comp_ctx.get(None):
                    raise PauseTriggered(prompt(self, self.container.context)) from e1
                if self.command.meta.raise_exception:
                    raise
                return self.export(fail=True, exception=e1)
            if self.container.done:
                break

        if self.default_main_only and not self.args_result:
            self.args_result = analyse_args(self, self.self_args, self.command.nargs)

    def export(self, exception: BaseException | None = None, fail: bool = False) -> Arparma[TDataCollection]:
        """创建arpamar, 其一定是一次解析的最后部分"""
        result = Arparma(self.command.path, self.container.origin, not fail, self.header_result)
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

    @classmethod
    def compile(
        cls: type[TAnalyser],
        command: Alconna[TAnalyser],
        compiler: Callable[[TAnalyser, Namespace], None] = default_compiler
    ) -> TAnalyser:
        _analyser = command.analyser_type(command)
        compiler(_analyser, command.namespace_config)
        return _analyser


TAnalyser = TypeVar("TAnalyser", bound=Analyser, default=Analyser)
