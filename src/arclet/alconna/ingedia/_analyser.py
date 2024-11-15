from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tarina import Empty

from ..i18n import i18n
from ..action import Action
from ..arparma import Arparma
from ..base import Option, Subcommand, HeadResult
from ..prompt import prompt
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
from ..utils import TDC
from ._handlers import (
    analyse_header,
    analyse_args,
    analyse_param,
)
from ._completion import comp_ctx

if TYPE_CHECKING:
    from ..core import Alconna
    from ._argv import Argv


def _compile(ana: Analyser, sub: Subcommand, path: tuple[str, ...]):
    if sub.args:
        ana.args_optional[path] = sub.args.optional_count == len(sub.args.data)
    for opt in sub.options:
        if isinstance(opt, Option):
            if opt.compact or opt.action.type == 2 or not set(sub.separators).issuperset(opt.separators):
                ana.compact_params.setdefault(path, []).append(opt)
            if opt.default is not Empty:
                if opt.default.value is not None:
                    ana.default_value_result[path + (opt.dest,)] = (opt.default.value, opt.action)
                if opt.default.args:
                    ana.default_arg_result[path + (opt.dest,)] = (opt.default.args, opt.action)
        else:
            if not set(sub.separators).issuperset(opt.separators):
                ana.compact_params.setdefault(path, []).append(opt)
            if opt.default is not Empty:
                if opt.default.value is not None:
                    ana.default_value_result[path + (opt.dest,)] = (opt.default.value, opt.action)
                if opt.default.args:
                    ana.default_arg_result[path + (opt.dest,)] = (opt.default.args, opt.action)
                for key, result in opt.default.options.items():
                    if result.value is not None:
                        ana.default_value_result[path + (opt.dest, key)] = (result.value, opt.action)
                    if result.args:
                        ana.default_arg_result[path + (opt.dest, key)] = (result.args, opt.action)
            _compile(ana, opt, path + (opt.dest,))


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
        self.args_optional: dict[tuple[str, ...], bool] = {}
        self.compact_params: dict[tuple[str, ...], list[Option | Subcommand]] = {}
        self.default_value_result: dict[tuple[str, ...], tuple[Any, Action]] = {}
        self.default_arg_result: dict[tuple[str, ...], tuple[dict[str, Any], Action]] = {}
        _compile(self, alconna, ())
        # runtime
        self.value_result: dict[tuple[str, ...], Any] = {}
        self.args_result: dict[tuple[str, ...], dict[str, Any]] = {}
        self.header_result: HeadResult | None = None
        self._error: Exception | None = None
        self._unvisited: dict[str, tuple[Option | Subcommand, tuple[str, ...]]] = {}

        self.update(alconna, ())

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
        self._error = None

    def __repr__(self):
        return f"<{self.__class__.__name__} of {self.command.path}>"

    def update(self, current: Subcommand, path: tuple[str, ...]):
        self._unvisited = {
            k: v
            for k, v in self._unvisited.items()
            if v[1] not in self.value_result
        } | {
            al: (opt, path + (opt.dest,))
            for opt in current.options
            for al in opt.aliases
        }

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
                exc = InvalidParam(i18n.require("header.error").format(target=argv.release(recover=True)[0]))
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

        if argv.current_index == argv.ndata:
            if not () in self.args_optional or () in self.args_result:
                return
            if self.args_optional[()]:
                try:
                    self.args_result[()] = analyse_args(self, argv, self.command.args)
                except FuzzyMatchSuccess as e1:
                    return e1
                except AnalyseException as e2:
                    e2.context_node = None
                    if not self._error:
                        self._error = e2
                return
            exc = ArgumentMissing(
                self.command.args.data[0].field.get_missing_tips(i18n.require("analyser.param_missing"))
            )
            if comp_ctx.get(None):
                return PauseTriggered(
                    prompt(self.command, argv.release(recover=True), [*self.args_result.get((), {}).keys()],
                           [*self.value_result.keys()]),
                    exc,
                    argv
                )
            return exc
        return ParamsUnmatched(i18n.require("analyser.param_unmatched").format(target=argv.next()[0]))

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
        if self._error:
            fail = True
            exception = self._error
        result = Arparma(self.command._hash, argv.origin, not fail, self.header_result, ctx=argv.exit())
        if fail:
            if self.command.config.raise_exception and not isinstance(exception, FuzzyMatchSuccess):
                raise exception
            result.error_info = exception
            result.error_data = argv.release(no_split=True)
            if isinstance(exception, FuzzyMatchSuccess):
                result.output = str(exception)
        if self.default_value_result:
            for path, v in self.default_value_result.items():
                if path not in self.value_result:
                    self.value_result[path] = v[0]
        if self.default_arg_result:
            for path, v in self.default_arg_result.items():
                if path not in self.default_value_result and path not in self.value_result:
                    continue
                if path not in self.args_result or not self.args_result[path]:
                    if v[1].value == 1:
                        self.args_result[path] = {k: [v] for k, v in v[0].items()}
                    else:
                        self.args_result[path] = v[0]
        result.args_result = self.args_result
        result.value_result = self.value_result
        result.buffer = argv.release(recover=True)
        if not fail and argv.message_cache:
            command_manager.record(argv.token, result)
        self.reset()
        return result  # type: ignore
