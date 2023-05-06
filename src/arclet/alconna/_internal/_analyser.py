from __future__ import annotations

import re
import traceback
from re import Match
from typing import TYPE_CHECKING, Any, Generic, Callable
from dataclasses import dataclass, field
from typing_extensions import Self, TypeAlias
from tarina import lang

from ..manager import command_manager, ShortcutArgs
from ..exceptions import (
    ParamsUnmatched,
    ArgumentMissing,
    FuzzyMatchSuccess,
    PauseTriggered,
    SpecialOptionTriggered,
    TerminateLoop
)
from ..args import Args
from ..base import Option, Subcommand
from ..completion import comp_ctx
from ..model import Sentence, HeadResult, OptionResult, SubcommandResult
from ..arparma import Arparma
from ..typing import TDC
from ..config import Namespace, config
from ..output import output_manager
from ..util import levenshtein
from ._handlers import (
    analyse_args, analyse_param, analyse_header, handle_help, handle_shortcut, handle_completion, prompt
)
from ._header import Header


if TYPE_CHECKING:
    from ._argv import Argv
    from ..core import Alconna

_SPECIAL = {
    "help": handle_help,
    "shortcut": handle_shortcut,
    "completion": handle_completion
}


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


def default_compiler(analyser: SubAnalyser, _config: Namespace, pids: set[str]):
    """默认的编译方法

    Args:
        analyser (SubAnalyser): 任意子解析器
        _config (Namespace): 命名空间配置
        pids (set[str]): 节点名集合
    """
    require_len = 0
    for opts in analyser.command.options:
        if isinstance(opts, Option):
            if opts.compact or opts.action.type == 2 or not set(analyser.command.separators).issuperset(opts.separators):
                analyser.compact_params.append(opts)
            _compile_opts(opts, analyser.compile_params)  # type: ignore
            pids.update(opts.aliases)
        elif isinstance(opts, Subcommand):
            sub = SubAnalyser(opts)
            analyser.compile_params[opts.name] = sub
            pids.add(opts.name)
            default_compiler(sub, _config, pids)
            if not set(analyser.command.separators).issuperset(opts.separators):
                analyser.compact_params.append(sub)
        if opts.requires:
            pids.update(opts.requires)
            require_len = max(len(opts.requires), require_len)
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

    def _clr(self):
        """清除自身的解析结果"""
        self.reset()
        ks = list(self.__dict__.keys())
        for k in ks:
            delattr(self, k)

    def __post_init__(self):
        self.reset()
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
        res = SubcommandResult(
            self.value_result, self.args_result.copy(), self.options_result.copy(), self.subcommands_result.copy()
        )
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
        sub = argv.context = self.command
        name, _ = argv.next(sub.separators)
        if name != sub.name:  # 先匹配节点名称
            if argv.fuzzy_match and levenshtein(name, sub.name) >= config.fuzzy_threshold:
                raise FuzzyMatchSuccess(lang.require("fuzzy", "matched").format(source=name, target=sub.name))
            raise ParamsUnmatched(lang.require("subcommand", "name_error").format(target=name, source=sub.name))

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
        while True:
            try:
                analyse_param(self, argv, self.command.separators)
            except TerminateLoop:
                break
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

    def __init__(self, alconna: Alconna[TDC], compiler: TCompile | None = None):
        """初始化解析器

        Args:
            alconna (Alconna[TDC]): 命令实例
            compiler (TCompile | None, optional): 编译器方法
        """
        super().__init__(alconna)
        self.fuzzy_match = alconna.meta.fuzzy_match
        self.used_tokens = set()
        self.command_header = Header.generate(alconna.command, alconna.prefixes, alconna.meta.compact)
        compiler = compiler or default_compiler
        compiler(
            self,
            alconna.namespace_config,
            command_manager.resolve(self.command).param_ids
        )

    def _clr(self):
        self.used_tokens.clear()
        super()._clr()

    def __repr__(self):
        return f"<{self.__class__.__name__} of {self.command.path}>"

    def shortcut(
        self, argv: Argv[TDC], data: list[Any], short: Arparma | ShortcutArgs, reg: Match | None
    ) -> Arparma[TDC]:
        """处理被触发的快捷命令

        Args:
            argv (Argv[TDC]): 命令行参数
            data (list[Any]): 剩余参数
            short (Arparma | ShortcutArgs): 快捷命令
            reg (Match | None): 可能的正则匹配结果

        Returns:
            Arparma[TDC]: Arparma 解析结果

        Raises:
            ParamsUnmatched: 若不允许快捷命令后随其他参数，则抛出此异常
        """
        if isinstance(short, Arparma):
            return short
        argv.build(short.get('command', self.command.command or self.command.name))
        if not short.get('fuzzy') and data:
            exc = ParamsUnmatched(lang.require("analyser", "param_unmatched").format(target=data[0]))
            if self.command.meta.raise_exception:
                raise exc
            return self.export(argv, True, exc)
        data_index = 0
        for i, unit in enumerate(argv.raw_data):
            if not data:
                break
            if not isinstance(unit, str):
                continue
            if unit == f"{{%{data_index}}}":
                argv.raw_data[i] = data.pop(0)
                data_index += 1
            elif f"{{%{data_index}}}" in unit:
                argv.raw_data[i] = unit.replace(f"{{%{data_index}}}", str(data.pop(0)))
                data_index += 1
            elif mat := re.search(r"\{\*(.*)\}", unit, re.DOTALL):
                sep = mat[1]
                argv.raw_data[i] = unit.replace(f"{{*{sep}}}", (sep or ' ').join(map(str, data)))
                data.clear()

        argv.bak_data = argv.raw_data.copy()
        argv.addon(*data).addon(*short.get('args', []))
        if reg:
            groups: tuple[str, ...] = reg.groups()
            gdict: dict[str, str] = reg.groupdict()
            for j, unit in enumerate(argv.raw_data):
                if not isinstance(unit, str):
                    continue
                for i, c in enumerate(groups):
                    unit = unit.replace(f"{{{i}}}", c)
                for k, v in gdict.items():
                    unit = unit.replace(f"{{{k}}}", v)
                argv.raw_data[j] = unit
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
            ParamsUnmatched: 参数不匹配
            ArgumentMissing: 参数缺失
        """
        if (
            argv.message_cache and
            argv.token in self.used_tokens and
            (res := command_manager.get_record(argv.token))
        ):
            return res
        try:
            self.header_result = analyse_header(self.command_header, argv)
        except ParamsUnmatched as e:
            argv.raw_data = argv.bak_data.copy()
            argv.current_index = 0
            try:
                _res = command_manager.find_shortcut(self.command, argv.next(move=False)[0])
            except ValueError as exc:
                if self.command.meta.raise_exception:
                    raise e from exc
                return self.export(argv, True, e)
            else:
                argv.next()
                data = argv.release()
                self.reset()
                argv.reset()
                return self.shortcut(argv, data, *_res)

        except FuzzyMatchSuccess as Fuzzy:
            output_manager.send(self.command.name, lambda: str(Fuzzy))
            return self.export(argv, True)

        except RuntimeError as e:
            exc = ParamsUnmatched(lang.require("header", "error").format(target=argv.release(recover=True)[0]))
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
                last = argv.bak_data[-1]
                argv.bak_data[-1] = last[:last.rfind(rest[-1])]
                return handle_completion(self, argv, rest[-2])
            exc = ParamsUnmatched(lang.require("analyser", "param_unmatched").format(target=argv.next(move=False)[0]))
        else:
            exc = ArgumentMissing(lang.require("analyser", "param_missing"))
        if isinstance(exc, ArgumentMissing) and comp_ctx.get(None):
            raise PauseTriggered(prompt(self, argv))
        if self.command.meta.raise_exception:
            raise exc
        return self.export(argv, True, exc)

    def analyse(self, argv: Argv[TDC]) -> Arparma[TDC] | None:
        while True:
            try:
                analyse_param(self, argv)
            except TerminateLoop:
                break
            except FuzzyMatchSuccess as e:
                output_manager.send(self.command.name, lambda: str(e))
                return self.export(argv, True)
            except SpecialOptionTriggered as sot:
                return _SPECIAL[sot.args[0]](self, argv)
            except (ParamsUnmatched, ArgumentMissing) as e1:
                if (rest := argv.release()) and isinstance(rest[-1], str):
                    if rest[-1] in argv.completion_names:
                        last = argv.bak_data[-1]
                        argv.bak_data[-1] = last[:last.rfind(rest[-1])]
                        return handle_completion(self, argv)
                    if handler := argv.special.get(rest[-1]):
                        return _SPECIAL[handler](self, argv)
                if isinstance(e1, ArgumentMissing) and comp_ctx.get(None):
                    raise PauseTriggered(prompt(self, argv)) from e1
                if self.command.meta.raise_exception:
                    raise
                return self.export(argv, True, e1)
            if argv.current_index == argv.ndata:
                break

        if self.default_main_only and not self.args_result:
            self.args_result = analyse_args(argv, self.self_args)

    def export(
        self,
        argv: Argv[TDC],
        fail: bool = False,
        exception: BaseException | None = None,
    ) -> Arparma[TDC]:
        """创建 `Arparma` 解析结果, 其一定是一次解析的最后部分

        Args:
            argv (Argv[TDC]): 命令行参数
            fail (bool, optional): 是否解析失败. Defaults to False.
            exception (BaseException | None, optional): 解析失败时的异常. Defaults to None.
        """
        result = Arparma(self.command.path, argv.origin, not fail, self.header_result)
        if fail:
            result.error_info = repr(exception or traceback.format_exc(limit=1))
            result.error_data = argv.release()
        else:
            result.main_args = self.args_result
            result.options = self.options_result
            result.subcommands = self.subcommands_result
            result.unpack()
            if argv.message_cache:
                command_manager.record(argv.token, result)
                self.used_tokens.add(argv.token)
        self.reset()
        return result  # type: ignore


TCompile: TypeAlias = "Callable[[SubAnalyser, Namespace, set[str]], None]"
