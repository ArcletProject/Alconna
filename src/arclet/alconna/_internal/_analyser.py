from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable
from typing_extensions import Self, TypeAlias

from tarina import Empty, lang

from ..action import Action
from ..args import Args
from ..arparma import Arparma
from ..base import Option, Subcommand
from ..completion import comp_ctx, prompt
from ..exceptions import (
    ArgumentMissing,
    AnalyseException,
    FuzzyMatchSuccess,
    InvalidHeader,
    InvalidParam,
    ParamsUnmatched,
    PauseTriggered,
)
from ..manager import command_manager
from ..model import HeadResult, OptionResult, SubcommandResult
from ..typing import TDC
from ._handlers import (
    analyse_header,
    analyse_args,
    analyse_param,
    handle_opt_default,
)
from ._util import levenshtein

if TYPE_CHECKING:
    from ..core import Alconna
    from ._argv import Argv


def default_compiler(analyser: SubAnalyser):
    """默认的编译方法

    Args:
        analyser (SubAnalyser): 任意子解析器
    """
    for opts in analyser.command.options:
        if isinstance(opts, Option):
            if opts.compact or opts.action.type == 2 or not set(analyser.command.separators).issuperset(opts.separators):  # noqa: E501
                analyser.compact_params.append(opts)
            for alias in opts.aliases:
                analyser.compile_params[alias] = opts
            if opts.default is not Empty:
                analyser.default_opt_result[opts.dest] = (opts.default, opts.action)
        elif isinstance(opts, Subcommand):
            sub = SubAnalyser(opts)
            for alias in opts.aliases:
                analyser.compile_params[alias] = sub
            default_compiler(sub)
            if not set(analyser.command.separators).issuperset(opts.separators):
                analyser.compact_params.append(sub)
            if sub.command.default is not Empty:
                analyser.default_sub_result[opts.dest] = sub.command.default


@dataclass
class SubAnalyser:
    """子解析器, 用于子命令的解析"""

    command: Subcommand
    """子命令"""
    default_main_only: bool = field(default=False)
    """命令是否只有主参数"""
    need_main_args: bool = field(default=False)
    """是否需要主参数"""
    compile_params: dict[str, Option | SubAnalyser] = field(default_factory=dict)
    """编译的节点"""
    compact_params: list[Option | SubAnalyser] = field(default_factory=list)
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
    default_opt_result: dict[str, tuple[OptionResult, Action]] = field(default_factory=dict)
    """默认选项的解析结果"""
    default_sub_result: dict[str, SubcommandResult] = field(default_factory=dict)
    """默认子命令的解析结果"""
    extra_allow: bool = field(default=False)
    """是否允许额外的参数"""
    soft_keyword: bool = field(default=False)

    def _clr(self):
        """清除自身的解析结果"""
        self.reset()
        ks = list(self.__dict__.keys())
        for k in ks:
            delattr(self, k)

    def __post_init__(self):
        self.reset()
        self.soft_keyword = self.command.soft_keyword
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
        self.value_result = None
        self.header_result = None

    def process(self, argv: Argv, name_validated: bool = True) -> Self:
        """处理传入的参数集合

        Args:
            argv (Argv): 命令行参数
            name_validated (bool, optional): 是否已经验证过名称. Defaults to True.

        Returns:
            Self: 自身

        Raises:
            ParamsUnmatched: 名称不匹配
            FuzzyMatchSuccess: 模糊匹配成功
        """
        sub = self.command
        if not name_validated:
            name, _ = argv.next(sub.separators)
            if name not in sub.aliases:
                argv.rollback(name)
                if not argv.fuzzy_match:
                    raise InvalidParam(lang.require("subcommand", "name_error").format(source=sub.dest, target=name), sub)
                for al in sub.aliases:
                    if levenshtein(name, al) >= argv.fuzzy_threshold:
                        raise FuzzyMatchSuccess(lang.require("fuzzy", "matched").format(source=al, target=name), sub)
                raise InvalidParam(lang.require("subcommand", "name_error").format(source=sub.dest, target=name), sub)

        self.value_result = sub.action.value
        argv.stack_params.enter(self.compile_params)
        while analyse_param(self, argv, self.command.separators) and argv.current_index != argv.ndata:
            pass
        if self.default_main_only and not self.args_result:
            self.args_result = analyse_args(argv, self.self_args)
        if not self.args_result and self.need_main_args:
            raise ArgumentMissing(
                self.self_args.argument[0].field.get_missing_tips(
                    lang.require("subcommand", "args_missing").format(name=self.command.dest)
                ),
                sub
            )
        argv.stack_params.leave()
        return self


class Analyser(SubAnalyser):
    """命令解析器"""

    command: Alconna
    """命令实例"""
    argv: Argv
    """命令行参数"""

    def __init__(self, alconna: Alconna, argv: Argv, compiler: TCompile | None = None):
        """初始化解析器

        Args:
            alconna (Alconna): 命令实例
            argv (Argv): 命令行参数
            compiler (TCompile | None, optional): 编译器方法
        """
        super().__init__(alconna)
        self.argv = argv
        self.extra_allow = not self.command.config.strict or not self.command.namespace_config.strict
        (compiler or default_compiler)(self)
        self.argv.stack_params.base = self.compile_params

    def __repr__(self):
        return f"<{self.__class__.__name__} of {self.command.path}>"

    def process(self, argv: Argv, name_validated: bool = True) -> Exception | None:
        """主体解析函数, 应针对各种情况进行解析

        Args:
            argv (Argv): 命令行参数
            name_validated (bool, optional): 是否已经验证过名称. Defaults to True.
        """
        if not self.header_result or not name_validated:
            try:
                self.header_result = analyse_header(self.command._header, argv)
            except InvalidHeader as e:
                return e
            except RuntimeError:
                exc = InvalidParam(lang.require("header", "error").format(target=argv.release(recover=True)[0]))
                return exc

        try:
            while analyse_param(self, argv) and argv.current_index != argv.ndata:
                pass
        except FuzzyMatchSuccess as e:
            return e
        except (InvalidParam, ArgumentMissing) as e1:
            if comp_ctx.get(None):
                if isinstance(e1, InvalidParam):
                    argv.free(e1.context_node.separators if e1.context_node else None)
                return PauseTriggered(
                    prompt(self.command, argv, [*self.args_result.keys()], [*self.options_result.keys(), *self.subcommands_result.keys()], e1.context_node),
                    e1,
                    argv
                )
            return e1

        if self.default_main_only and not self.args_result:
            try:
                self.args_result = analyse_args(argv, self.self_args)
            except FuzzyMatchSuccess as e1:
                return e1
            except AnalyseException as e2:
                e2.context_node = None
                if not argv.error:
                    argv.error = e2

        if argv.current_index == argv.ndata and (not self.need_main_args or self.args_result):
            return

        rest = argv.release()
        if len(rest) > 0:
            exc = ParamsUnmatched(lang.require("analyser", "param_unmatched").format(target=argv.next()[0]))
        else:
            exc = ArgumentMissing(
                self.self_args.argument[0].field.get_missing_tips(lang.require("analyser", "param_missing"))
            )
            if comp_ctx.get(None):
                return PauseTriggered(
                    prompt(self.command, argv, [*self.args_result.keys()], [*self.options_result.keys(), *self.subcommands_result.keys()]),
                    exc,
                    argv
                )
        return exc

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
        if argv.error:
            fail = True
            exception = argv.error
        result = Arparma(self.command._hash, argv.origin, not fail, self.header_result, ctx=argv.exit())
        if fail:
            if self.command.config.raise_exception and not isinstance(exception, FuzzyMatchSuccess):
                raise exception
            result.error_info = exception
            result.error_data = argv.release()
            if isinstance(exception, FuzzyMatchSuccess):
                result.output = str(exception)

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
        if not fail and argv.message_cache:
            command_manager.record(argv.token, result)
        self.reset()
        return result  # type: ignore


TCompile: TypeAlias = Callable[[SubAnalyser], None]
