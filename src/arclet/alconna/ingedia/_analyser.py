from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tarina import Empty, lang

from ..action import Action
from ..arparma import Arparma
from ..base import Option, Subcommand, HeadResult, SubcommandResult
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
from ..typing import TDC
from ._handlers import (
    analyse_header,
    analyse_args,
    analyse_param,
)

if TYPE_CHECKING:
    from ..core import Alconna
    from ._argv import Argv


def _compile(ana: Analyser, sub: Subcommand, path: tuple[str, ...], upper_soft_kws: dict[str, bool] | None = None):
    ana.need_main_args[path] = sub.nargs > 0 and sub.nargs > sub.args.optional_count
    _de_count = sum(arg.field.default is not Empty for arg in sub.args.data)
    ana.default_main_only[path] = bool(_de_count) and _de_count == sub.nargs
    ana.argv.soft_kws[path] = {al: opt.soft_keyword for opt in sub.options for al in opt.aliases} | (upper_soft_kws or {})
    for opt in sub.options:
        if isinstance(opt, Option):
            if opt.compact or opt.action.type == 2 or not set(sub.separators).issuperset(opt.separators):
                ana.compact_params.setdefault(path, []).append(opt)
            if opt.default is not Empty:
                ana.default_value_result[path + (opt.dest,)] = (opt.default.value, opt.action)
                if opt.default.args:
                    ana.default_arg_result[path + (opt.dest,)] = (opt.default.args, opt.action)
        else:
            if not set(sub.separators).issuperset(opt.separators):
                ana.compact_params.setdefault(path, []).append(opt)
            if opt.default is not Empty:
                if opt.default.args:
                    ana.default_arg_result[path + (opt.dest,)] = (opt.default.args, opt.action)
                for key, result in opt.default.options.items():
                    ana.default_value_result[path + (opt.dest, key)] = (result.value, opt.action)
                    if result.args:
                        ana.default_arg_result[path + (opt.dest, key)] = (result.args, opt.action)
            _compile(ana, opt, path + (opt.dest,), ana.argv.soft_kws[path])


class Analyser:
    """命令解析器"""

    command: Alconna
    """命令实例"""
    argv: Argv
    """命令行参数"""

    def __init__(self, alconna: Alconna, argv: Argv):
        """初始化解析器

        _Args:
            alconna (Alconna): 命令实例
            argv (Argv): 命令行参数
        """
        self.command = alconna
        self.argv = argv
        self.extra_allow = not self.command.config.strict
        self.default_main_only: dict[tuple[str, ...], bool] = {(alconna.dest,): False}
        self.need_main_args: dict[tuple[str, ...], bool] = {(alconna.dest,): False}
        self.compact_params: dict[tuple[str, ...], list[Option | Subcommand]] = {}
        self.value_result: dict[tuple[str, ...], Any] = {}
        self.args_result: dict[tuple[str, ...], dict[str, Any]] = {}
        self.header_result: HeadResult | None = None
        self.default_value_result: dict[tuple[str, ...], tuple[Any, Action]] = {}
        self.default_arg_result: dict[tuple[str, ...], tuple[dict[str, Any], Action]] = {}
        _compile(self, alconna, ())

    def _clr(self):
        """清除自身的解析结果"""
        self.reset()
        ks = list(self.__dict__.keys())
        for k in ks:
            delattr(self, k)

    def reset(self):
        """重置解析器"""
        self.args_result = {}
        self.value_result = {}
        self.header_result = None

    def __repr__(self):
        return f"<{self.__class__.__name__} of {self.command.path}>"

    def process(self, argv: Argv, name_validated: bool = True) -> Exception | None:
        """主体解析函数, 应针对各种情况进行解析

        _Args:
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
            while analyse_param(self, self.command, argv, ()) and argv.current_index != argv.ndata:
                pass
        except FuzzyMatchSuccess as e:
            return e
        except (InvalidParam, ArgumentMissing) as e1:
            if comp_ctx.get(None):
                if isinstance(e1, InvalidParam):
                    argv.free(e1.context_node.separators if e1.context_node else None)
                return PauseTriggered(
                    prompt(self.command, argv.release(recover=True), [*self.args_result.get((), {}).keys()], [*self.value_result.keys()], e1.context_node),
                    e1,
                    argv
                )
            return e1

        if self.default_main_only[()] and () not in self.args_result:
            try:
                self.args_result[()] = analyse_args(argv, self.command.args, ())
            except FuzzyMatchSuccess as e1:
                return e1
            except AnalyseException as e2:
                e2.context_node = None
                if not argv.error:
                    argv.error = e2

        if argv.current_index == argv.ndata and (not self.need_main_args[()] or () in self.args_result):
            return

        rest = argv.release()
        if len(rest) > 0:
            exc = ParamsUnmatched(lang.require("analyser", "param_unmatched").format(target=argv.next()[0]))
        else:
            exc = ArgumentMissing(
                self.command.args.data[0].field.get_missing_tips(lang.require("analyser", "param_missing"))
            )
            if comp_ctx.get(None):
                return PauseTriggered(
                    prompt(self.command, argv.release(recover=True), [*self.args_result.get((), {}).keys()], [*self.value_result.keys()]),
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

        _Args:
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
        if self.default_value_result:
            for path, v in self.default_value_result.items():
                if path not in self.value_result:
                    self.value_result[path] = v[0]
        if self.default_arg_result:
            for path, v in self.default_arg_result.items():
                if path not in self.args_result or not self.args_result[path]:
                    if v[1].value == 1:
                        self.args_result[path] = {k: [v] for k, v in v[0].items()}
                    else:
                        self.args_result[path] = v[0]
        # result.main_args = self.args_result
        # result.options = self.options_result
        # result.subcommands = self.subcommands_result
        # result.unpack()
        if () in self.args_result:
            result.main_args = self.args_result[()]
        for path, v in self.value_result.items():
            if path == ():
                continue
            prefixes, key = path[:-1], path[-1]
            if not prefixes:
                if key in result.subcommands:
                    result.subcommands[key].value = v
                else:
                    result.subcommands[key] = SubcommandResult(v)
            else:
                sub = result.subcommands.setdefault(prefixes[0], SubcommandResult())
                for part in prefixes[1:]:
                    sub = sub.subcommands.setdefault(part, SubcommandResult())
                sub.subcommands[key] = SubcommandResult(v)
        for path, v in self.args_result.items():
            if path == ():
                continue
            prefixes, key = path[:-1], path[-1]
            result.other_args.update(v)
            if not prefixes:
                if key in result.subcommands:
                    result.subcommands[key].args = v
                else:
                    result.subcommands[key] = SubcommandResult(..., v)
            else:
                sub = result.subcommands.setdefault(prefixes[0], SubcommandResult())
                for part in prefixes[1:]:
                    sub = sub.subcommands.setdefault(part, SubcommandResult())
                if key in sub.subcommands:
                    sub.subcommands[key].args = v
                else:
                    sub.subcommands[key] = SubcommandResult(..., v)
        if not fail and argv.message_cache:
            command_manager.record(argv.token, result)
        self.reset()
        return result  # type: ignore
