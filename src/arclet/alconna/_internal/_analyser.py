from __future__ import annotations

import re
from dataclasses import dataclass, field
from re import Match
from typing import TYPE_CHECKING, Any, Callable, Generic, Set
from typing_extensions import Self, TypeAlias

from tarina import Empty, lang

from ..action import Action
from ..args import Args
from ..arparma import Arparma
from ..base import Completion, Help, Option, Shortcut, Subcommand
from ..completion import comp_ctx
from ..constraint import SHORTCUT_ARGS, SHORTCUT_REGEX_MATCH, SHORTCUT_REST, SHORTCUT_TRIGGER
from ..exceptions import (
    ArgumentMissing,
    FuzzyMatchSuccess,
    InvalidParam,
    ParamsUnmatched,
    PauseTriggered,
    SpecialOptionTriggered,
)
from ..manager import command_manager
from ..model import HeadResult, OptionResult, Sentence, SubcommandResult
from ..output import output_manager
from ..typing import TDC, InnerShortcutArgs
from ._handlers import (
    HEAD_HANDLES,
    _handle_shortcut_data,
    _handle_shortcut_reg,
    analyse_args,
    analyse_param,
    handle_completion,
    handle_help,
    handle_opt_default,
    handle_shortcut,
    prompt,
)
from ._header import Header
from ._util import levenshtein

if TYPE_CHECKING:
    from ..core import Alconna
    from ._argv import Argv

_SPECIAL = {"help": handle_help, "shortcut": handle_shortcut, "completion": handle_completion}


def _compile_opts(option: Option, data: dict[str, Sentence | Option | list[Option] | SubAnalyser]):
    """处理选项

    Args:
        option (Option): 选项
        data (dict[str, Sentence | Option | list[Option] | SubAnalyser]): 编译的节点
    """
    for alias in option.aliases:
        if li := data.get(alias):
            if isinstance(li, SubAnalyser):
                continue
            if isinstance(li, list):
                li.append(option)
                li.sort(key=lambda x: x.priority, reverse=True)
            elif isinstance(li, Sentence):
                data[alias] = option
                continue
            else:
                data[alias] = sorted([li, option], key=lambda x: x.priority, reverse=True)
        else:
            data[alias] = option


def default_compiler(analyser: SubAnalyser, pids: set[str]):
    """默认的编译方法

    Args:
        analyser (SubAnalyser): 任意子解析器
        pids (set[str]): 节点名集合
    """
    for opts in analyser.command.options:
        if isinstance(opts, Option) and not isinstance(opts, (Help, Shortcut, Completion)):
            if opts.compact or opts.action.type == 2 or not set(analyser.command.separators).issuperset(opts.separators):  # noqa: E501
                analyser.compact_params.append(opts)
            _compile_opts(opts, analyser.compile_params)  # type: ignore
            if opts.default is not Empty:
                analyser.default_opt_result[opts.dest] = (opts.default, opts.action)
            pids.update(opts.aliases)
        elif isinstance(opts, Subcommand):
            sub = SubAnalyser(opts)
            for alias in opts.aliases:
                analyser.compile_params[alias] = sub
            pids.update(opts.aliases)
            default_compiler(sub, pids)
            if not set(analyser.command.separators).issuperset(opts.separators):
                analyser.compact_params.append(sub)
            if sub.command.default is not Empty:
                analyser.default_sub_result[opts.dest] = sub.command.default
        if opts.requires:
            pids.update(opts.requires)
            for k in opts.requires:
                analyser.compile_params.setdefault(k, Sentence(name=k))


@dataclass
class SubAnalyser(Generic[TDC]):
    """子解析器, 用于子命令的解析"""

    command: Subcommand
    """子命令"""
    default_main_only: bool = field(default=False)
    """命令是否只有主参数"""
    need_main_args: bool = field(default=False)
    """是否需要主参数"""
    compile_params: dict[str, Sentence | Option | list[Option] | SubAnalyser[TDC]] = field(default_factory=dict)
    """编译的节点"""
    compact_params: list[Option | SubAnalyser[TDC]] = field(default_factory=list)
    """可能紧凑的需要逐个解析的节点"""
    self_args: Args = field(init=False)
    """命令自身参数"""
    subcommands_result: dict[str, SubcommandResult] = field(init=False)
    """子命令的解析结果"""
    options_result: dict[str, OptionResult] = field(init=False)
    """选项的解析结果"""
    args_result: dict[str, Any] = field(init=False)
    """参数的解析结果"""
    header_result: HeadResult | None = field(init=False)
    """头部的解析结果"""
    value_result: Any = field(init=False)
    """值的解析结果"""
    sentences: list[str] = field(init=False)
    """暂存传入的所有句段"""
    default_opt_result: dict[str, tuple[OptionResult, Action]] = field(default_factory=dict)
    """默认选项的解析结果"""
    default_sub_result: dict[str, SubcommandResult] = field(default_factory=dict)
    """默认子命令的解析结果"""
    extra_allow: bool = field(default=False)
    """是否允许额外的参数"""

    def _clr(self):
        """清除自身的解析结果"""
        self.reset()
        ks = list(self.__dict__.keys())
        for k in ks:
            delattr(self, k)

    def __post_init__(self):
        self.reset()
        self.__calc_args__()

    def __calc_args__(self):
        self.self_args = self.command.args
        if self.command.nargs > 0 and self.command.nargs > self.self_args.optional_count:
            self.need_main_args = True  # 如果need_marg那么match的元素里一定得有main_argument
        _de_count = sum(arg.field.default is not None for arg in self.self_args.argument)
        if _de_count and _de_count == self.command.nargs:
            self.default_main_only = True

    def result(self) -> SubcommandResult:
        """生成子命令解析结果

        Returns:
            SubcommandResult: 子命令解析结果
        """
        if self.default_opt_result:
            handle_opt_default(self.default_opt_result, self.options_result)
        if self.default_sub_result:
            for k, v in self.default_sub_result.items():
                if k not in self.subcommands_result:
                    self.subcommands_result[k] = v
        res = SubcommandResult(self.value_result, self.args_result, self.options_result, self.subcommands_result)
        self.reset()
        return res

    def reset(self):
        """重置解析器"""
        self.args_result = {}
        self.options_result = {}
        self.subcommands_result = {}
        self.sentences = []
        self.value_result = None
        self.header_result = None

    def process(self, argv: Argv[TDC]) -> Self:
        """处理传入的参数集合

        Args:
            argv (Argv[TDC]): 命令行参数

        Returns:
            Self: 自身

        Raises:
            ParamsUnmatched: 名称不匹配
            FuzzyMatchSuccess: 模糊匹配成功
        """
        sub = argv.current_node = self.command
        name, _ = argv.next(sub.separators)
        if name not in sub.aliases:
            argv.rollback(name)
            if not argv.fuzzy_match:
                raise InvalidParam(lang.require("subcommand", "name_error").format(source=sub.dest, target=name))
            for al in sub.aliases:
                if levenshtein(name, al) >= argv.fuzzy_threshold:
                    raise FuzzyMatchSuccess(lang.require("fuzzy", "matched").format(source=al, target=name))
            raise InvalidParam(lang.require("subcommand", "name_error").format(source=sub.dest, target=name))

        self.value_result = sub.action.value
        return self.analyse(argv)

    def analyse(self, argv: Argv[TDC]) -> Self:
        """解析传入的参数集合

        Args:
            argv (Argv[TDC]): 命令行参数

        Returns:
            Self: 自身

        Raises:
            ArgumentMissing: 参数缺失
        """
        while analyse_param(self, argv, self.command.separators):
            pass
        if self.default_main_only and not self.args_result:
            self.args_result = analyse_args(argv, self.self_args)
        if not self.args_result and self.need_main_args:
            raise ArgumentMissing(lang.require("subcommand", "args_missing").format(name=self.command.dest))
        return self

    def get_sub_analyser(self, target: Subcommand) -> SubAnalyser[TDC] | None:
        """获取子解析器

        Args:
            target (Subcommand): 目标子命令

        Returns:
            SubAnalyser[TDC] | None: 子解析器
        """
        if target == self.command:
            return self
        for param in self.compile_params.values():
            if isinstance(param, SubAnalyser):
                return param.get_sub_analyser(target)


class Analyser(SubAnalyser[TDC], Generic[TDC]):
    """命令解析器"""

    command: Alconna
    """命令实例"""
    used_tokens: set[int]
    """已使用的token"""
    command_header: Header
    """命令头部"""
    header_handler: Callable[[Header, Argv], HeadResult]
    """头部处理器"""

    def __init__(self, alconna: Alconna[TDC], compiler: TCompile | None = None):
        """初始化解析器

        Args:
            alconna (Alconna[TDC]): 命令实例
            compiler (TCompile | None, optional): 编译器方法
        """
        super().__init__(alconna)
        self._compiler = compiler or default_compiler
        self.used_tokens = set()

    def compile(self, param_ids: set[str]):
        self.extra_allow = not self.command.meta.strict or not self.command.namespace_config.strict
        self.command_header = Header.generate(self.command.command, self.command.prefixes, self.command.meta.compact)
        self.header_handler = HEAD_HANDLES[self.command_header.flag]
        self._compiler(self, param_ids)
        return self

    def _clr(self):
        self.used_tokens.clear()
        super()._clr()

    def __repr__(self):
        return f"<{self.__class__.__name__} of {self.command.path}>"

    def shortcut(
        self, argv: Argv[TDC], data: list[Any], short: Arparma | InnerShortcutArgs, reg: Match | None = None
    ) -> Arparma[TDC]:
        """处理被触发的快捷命令

        Args:
            argv (Argv[TDC]): 命令行参数
            data (list[Any]): 剩余参数
            short (Arparma | InnerShortcutArgs): 快捷命令
            reg (Match | None): 可能的正则匹配结果

        Returns:
            Arparma[TDC]: Arparma 解析结果

        Raises:
            ParamsUnmatched: 若不允许快捷命令后随其他参数，则抛出此异常
        """
        if isinstance(short, Arparma):
            return short

        argv.build(short.command)  # type: ignore
        if not short.fuzzy and data:
            exc = ParamsUnmatched(lang.require("analyser", "param_unmatched").format(target=data[0]))
            if self.command.meta.raise_exception:
                raise exc
            return self.export(argv, True, exc)
        argv.addon(short.args, merge_str=False)
        data = _handle_shortcut_data(argv, data)
        if not data and argv.raw_data and any(isinstance(i, str) and bool(re.search(r"\{%(\d+)|\*(.*?)\}", i)) for i in argv.raw_data):
            exc = ArgumentMissing(lang.require("analyser", "param_missing"))
            if self.command.meta.raise_exception:
                raise exc
            return self.export(argv, True, exc)
        argv.bak_data = argv.raw_data.copy()
        argv.addon(data, merge_str=False)
        if reg:
            data = _handle_shortcut_reg(argv, reg.groups(), reg.groupdict(), short.wrapper)
            argv.raw_data.clear()
            argv.ndata = 0
            argv.current_index = 0
            argv.addon(data)
        argv.bak_data = argv.raw_data.copy()
        if argv.message_cache:
            argv.token = argv.generate_token(argv.raw_data)
        return self.process(argv)

    def process(self, argv: Argv[TDC]) -> Arparma[TDC]:
        """主体解析函数, 应针对各种情况进行解析

        Args:
            argv (Argv[TDC]): 命令行参数

        Returns:
            Arparma[TDC]: Arparma 解析结果

        Raises:
            ValueError: 快捷命令查找失败
            InvalidParam: 参数不匹配
            ArgumentMissing: 参数缺失
        """
        if argv.message_cache and argv.token in self.used_tokens and (res := command_manager.get_record(argv.token)):
            return res
        try:
            self.header_result = self.header_handler(self.command_header, argv)
        except InvalidParam as e:
            _next = e.args[1]
            if _next.__class__ is not str or not _next:
                if self.command.meta.raise_exception:
                    raise e
                return self.export(argv, True, e)
            argv.context[SHORTCUT_TRIGGER] = _next
            try:
                rest, short, mat = command_manager.find_shortcut(self.command, [_next] + argv.release())
            except ValueError as exc:
                if self.command.meta.raise_exception:
                    raise e from exc
                return self.export(argv, True, e)
            else:
                argv.context[SHORTCUT_ARGS] = short
                argv.context[SHORTCUT_REST] = rest
                argv.context[SHORTCUT_REGEX_MATCH] = mat
                self.reset()
                return self.shortcut(argv, rest, short, mat)

        except FuzzyMatchSuccess as Fuzzy:
            output_manager.send(self.command.name, lambda: str(Fuzzy))
            return self.export(argv, True)

        except RuntimeError as e:
            exc = InvalidParam(lang.require("header", "error").format(target=argv.release(recover=True)[0]))
            if self.command.meta.raise_exception:
                raise exc from e
            return self.export(argv, True, exc)

        if fail := self.analyse(argv):
            return fail

        if argv.done and (not self.need_main_args or self.args_result):
            return self.export(argv)

        rest = argv.release()
        if len(rest) > 0:
            if isinstance(rest[-1], str) and rest[-1] in argv.completion_names:
                argv.bak_data[-1] = argv.bak_data[-1][: -len(rest[-1])].rstrip()
                return handle_completion(self, argv, rest[-2])
            exc = ParamsUnmatched(lang.require("analyser", "param_unmatched").format(target=argv.next(move=False)[0]))
        else:
            exc = ArgumentMissing(lang.require("analyser", "param_missing"))
        if comp_ctx.get(None) and isinstance(exc, ArgumentMissing):
            raise PauseTriggered(prompt(self, argv), exc, argv)
        if self.command.meta.raise_exception:
            raise exc
        return self.export(argv, True, exc)

    def analyse(self, argv: Argv[TDC]) -> Arparma[TDC] | None:
        try:
            while analyse_param(self, argv) and argv.current_index != argv.ndata:
                pass
        except FuzzyMatchSuccess as e:
            output_manager.send(self.command.name, lambda: str(e))
            return self.export(argv, True)
        except SpecialOptionTriggered as sot:
            return _SPECIAL[sot.args[0]](self, argv)
        except (InvalidParam, ArgumentMissing) as e1:
            if (rest := argv.release()) and isinstance(rest[-1], str):
                if rest[-1] in argv.completion_names and "completion" not in argv.namespace.disable_builtin_options:
                    argv.bak_data[-1] = argv.bak_data[-1][: -len(rest[-1])].rstrip()
                    return handle_completion(self, argv)
                if (handler := argv.special.get(rest[-1])) and handler not in argv.namespace.disable_builtin_options:
                    return _SPECIAL[handler](self, argv)
            if comp_ctx.get(None):
                if isinstance(e1, InvalidParam):
                    argv.free(argv.current_node.separators if argv.current_node else None)
                raise PauseTriggered(prompt(self, argv), e1, argv) from e1
            if self.command.meta.raise_exception:
                raise
            return self.export(argv, True, e1)

        if self.default_main_only and not self.args_result:
            self.args_result = analyse_args(argv, self.self_args)

    def export(
        self,
        argv: Argv[TDC],
        fail: bool = False,
        exception: Exception | None = None,
    ) -> Arparma[TDC]:
        """创建 `Arparma` 解析结果, 其一定是一次解析的最后部分

        Args:
            argv (Argv[TDC]): 命令行参数
            fail (bool, optional): 是否解析失败. Defaults to False.
            exception (Exception | None, optional): 解析失败时的异常. Defaults to None.
        """
        result = Arparma(self.command.path, argv.origin, not fail, self.header_result, ctx=argv.exit())
        if fail:
            result.error_info = exception
            result.error_data = argv.release()
        else:
            if self.default_opt_result:
                handle_opt_default(self.default_opt_result, self.options_result)
            if self.default_sub_result:
                for k, v in self.default_sub_result.items():
                    if k not in self.subcommands_result:
                        self.subcommands_result[k] = v
            result.main_args = self.args_result
            result.options = self.options_result
            result.subcommands = self.subcommands_result
            result.unpack()
            if argv.message_cache:
                command_manager.record(argv.token, result)
                self.used_tokens.add(argv.token)
        self.reset()
        return result  # type: ignore


TCompile: TypeAlias = Callable[[SubAnalyser, Set[str]], None]
