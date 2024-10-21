"""Alconna 主体"""
from __future__ import annotations

import warnings
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Generic, Literal, Sequence, TypeVar, cast, overload, TYPE_CHECKING
from typing_extensions import Self
from weakref import WeakSet

from nepattern import TPattern
from tarina import init_spec, lang, Empty

from .ingedia._analyser import Analyser, TCompile
from .ingedia._handlers import handle_head_fuzzy, analyse_header
from .ingedia._argv import Argv, __argv_type__
from .args import Arg, Args
from .arparma import Arparma, ArparmaBehavior, requirement_handler
from .base import Completion, Help, Option, OptionResult, Shortcut, Subcommand, Header, SPECIAL_OPTIONS, Config, Metadata
from .config import Namespace, global_config
from .constraint import SHORTCUT_ARGS, SHORTCUT_REGEX_MATCH, SHORTCUT_REST, SHORTCUT_TRIGGER
from .exceptions import (
    AlconnaException,
    AnalyseException,
    ExecuteFailed,
    FuzzyMatchSuccess,
    InvalidHeader,
    PauseTriggered,
)
from .shortcut import wrap_shortcut
from .completion import prompt, comp_ctx
from .formatter import TextFormatter
from .manager import ShortcutArgs, command_manager
from .typing import TDC, InnerShortcutArgs, ShortcutRegWrapper

T = TypeVar("T")


def handle_argv():
    path = Path(sys.argv[0])
    if str(path) == ".":
        path = path.absolute()
    head = path.stem
    if head == "__main__":
        head = path.parent.stem
    return head


def add_builtin_options(options: list[Option | Subcommand], router: Router, conf: Config) -> None:
    if "help" not in conf.disable_builtin_options:
        options.append(Help("|".join(conf.builtin_option_name["help"]), dest="$help", help_text=lang.require("builtin", "option_help"), soft_keyword=False))  # noqa: E501

        @router.route("$help")
        def _(command: Alconna, arp: Arparma):
            argv = command_manager.require(command).argv
            _help_param = [str(i) for i in argv.release(recover=True) if str(i) not in conf.builtin_option_name["help"]]
            arp.output = command.formatter.format_node(_help_param)
            return True
    else:
        router._routes.pop("$help", None)

    if "shortcut" not in conf.disable_builtin_options:
        options.append(
            Shortcut(
                "|".join(conf.builtin_option_name["shortcut"]),
                Args["action?", "delete|list"]["name?", str]["command?", str],
                dest="$shortcut",
                help_text=lang.require("builtin", "option_shortcut"),
                soft_keyword=False,
            )
        )

        @router.route("$shortcut")
        def _(command: Alconna, arp: Arparma):
            res = arp.query[OptionResult]("$shortcut", force_return=True)
            if res.args.get("action") == "list":
                data = command.get_shortcuts()
                arp.output = "\n".join(data)
                return True
            if not res.args.get("name"):
                raise ValueError(lang.require("shortcut", "name_require"))
            if res.args.get("action") == "delete":
                msg = command.shortcut(res.args["name"], delete=True)
            else:
                msg = command.shortcut(res.args["name"], fuzzy=True, command=res.args.get("command"))
            arp.output = msg
            return True
    else:
        router._routes.pop("$shortcut", None)

    if "completion" not in conf.disable_builtin_options:
        options.append(Completion("|".join(conf.builtin_option_name["completion"]), dest="$completion", help_text=lang.require("builtin", "option_completion"), soft_keyword=False))  # noqa: E501

        @router.route("$completion")
        def _(command: Alconna, arp: Arparma):
            argv = command_manager.require(command).argv
            rest = argv.release()
            trigger = None
            if rest and isinstance(rest[-1], str) and rest[-1] in conf.builtin_option_name["completion"]:
                argv.bak_data[-1] = argv.bak_data[-1][: -len(rest[-1])].rstrip()
                trigger = rest[-2]
            elif isinstance(arp.error_info, AnalyseException):
                trigger = arp.error_info.context_node
            if res := prompt(
                command,
                argv,
                list(arp.main_args.keys()),
                [*arp.options.keys(), *arp.subcommands.keys()],
                trigger
            ):
                if comp_ctx.get(None):
                    raise PauseTriggered(res, trigger, argv)
                prompt_other = lang.require("completion", "prompt_other")
                node = lang.require('completion', 'node')
                node = f"{node}\n" if node else ""
                arp.output = f"{node}{prompt_other}" + f"\n{prompt_other}".join([i.text for i in res])
                return True
    else:
        router._routes.pop("$completion", None)


@dataclass(init=True, unsafe_hash=True)
class ArparmaExecutor(Generic[T]):
    """Arparma 执行器

    Attributes:
        target(Callable[..., T]): 目标函数
    """

    target: Callable[..., T]
    binding: Callable[..., list[Arparma]] = field(default=lambda: [], repr=False)

    def __call__(self, *args, **kwargs):
        return self.target(*args, **kwargs)

    @property
    def result(self) -> T:
        """执行结果"""
        if not self.binding:
            raise ExecuteFailed(None)
        arps = self.binding()
        if not arps or not arps[0].matched:
            raise ExecuteFailed("Unmatched")
        try:
            return arps[0].call(self.target)
        except Exception as e:
            raise ExecuteFailed(e) from e


class Router:
    def __init__(self):
        self._routes = {}

    def route(self, path: str):
        def wrapper(target: Callable[[Alconna, Arparma], Any]):
            self._routes[path] = target
            return target
        return wrapper

    def execute(self, cmd: Alconna, arp: Arparma):
        for route, target in self._routes.items():
            if arp.query(route, Empty) is not Empty:
                try:
                    res = target(cmd, arp)
                    if res is True:
                        return
                except Exception as e:
                    return e


class Alconna(Subcommand):
    """
    更加精确的命令解析

    Examples:

        >>> from arclet.alconna import Alconna
        >>> alc = Alconna(
        ...     "name",
        ...     ["p1", "p2"],
        ...     Option("opt", Args["opt_arg", "opt_arg"]),
        ...     Subcommand(
        ...         "sub_name",
        ...         Option("sub_opt", Args["sub_arg", "sub_arg"]),
        ...         Args["sub_main_args", "sub_main_args"]
        ...     ),
        ...     Args["main_args", "main_args"],
        ...  )
        >>> alc.parse("name opt opt_arg")
    """

    prefixes: list[str]
    """命令前缀"""
    command: str | Any
    """命令名"""
    _header: Header
    """命令头部"""
    formatter: TextFormatter
    """文本格式化器"""
    namespace: str
    """命名空间"""
    meta: Metadata
    """命令元数据"""
    config: Config
    """命令配置"""
    behaviors: list[ArparmaBehavior]
    """命令行为器"""

    def compile(self, compiler: TCompile | None = None) -> Analyser:
        """编译 `Alconna` 为对应的解析器"""
        if TYPE_CHECKING:
            argv_type = Argv
        else:
            argv_type: type[Argv] = __argv_type__.get()
        argv = argv_type(self.config, self.namespace_config, self.separators)
        return Analyser(self, argv, compiler)

    def __init__(
        self,
        *args: Option | Subcommand | str | list[str] | Args | Arg | Metadata | Config | ArparmaBehavior | Any,
        namespace: str | Namespace | None = None,
        separators: str | set[str] | Sequence[str] | None = None,
        behaviors: list[ArparmaBehavior] | None = None,
        formatter_type: type[TextFormatter] | None = None,
        meta: tuple[Metadata, Config] | None = None,
    ):
        """
        以标准形式构造 `Alconna`

        Args:
            *args (Option | Subcommand | str | list[str] | Args | Arg | Metadata | Config | ArparmaBehavior | Any): 命令选项、主参数、命令名称或命令头等
            namespace (str | Namespace | None, optional): 命令命名空间, 默认为 'Alconna'
            separators (str | set[str] | Sequence[str] | None, optional): 命令参数分隔符, 默认为 `' '`
            behaviors (list[ArparmaBehavior] | None, optional): 命令解析行为器
            formatter_type (type[TextFormatter] | None, optional): 指定的命令帮助文本格式器类型
        """
        if meta:
            warnings.warn("The `meta` parameter is deprecated, please use `Metadata` and `Config` instead.", DeprecationWarning, stacklevel=2)
            args += meta
        if not namespace:
            ns_config = global_config.default_namespace
        elif isinstance(namespace, str):
            ns_config = global_config.namespaces.setdefault(namespace, Namespace(namespace))
        else:
            ns_config = namespace
        self.prefixes = next((i for i in args if isinstance(i, list)), ns_config.prefixes.copy())  # type: ignore
        try:
            self.command = next(i for i in args if not isinstance(i, (list, Option, Subcommand, Args, Arg, Metadata, Config, ArparmaBehavior)))
        except StopIteration:
            self.command = "" if self.prefixes else handle_argv()
        self.router = Router()
        self.namespace = ns_config.name
        self.formatter = (formatter_type or ns_config.formatter_type or TextFormatter)()
        self.meta = next((i for i in args if isinstance(i, Metadata)), Metadata())
        if self.meta.example:
            self.meta.example = self.meta.example.replace("$", self.prefixes[0] if self.prefixes else "")
        self.config = Config.merge(next((i for i in args if isinstance(i, Config)), Config()), ns_config.config)
        self._header = Header.generate(self.command, self.prefixes, bool(self.config.compact))
        options = [i for i in args if isinstance(i, (Option, Subcommand))]
        add_builtin_options(options, self.router, self.config)
        name = next(iter(self._header.content), self.command or self.prefixes[0])
        self.path = f"{self.namespace}::{name}"
        _args = sum((i for i in args if isinstance(i, (Args, Arg))), Args())
        super().__init__("ALCONNA::", _args, *options, dest=name, separators=separators or ns_config.separators, help_text=self.meta.description)  # noqa: E501
        self.name = name
        self.aliases = frozenset(self._header.content)
        self.behaviors = []
        _behaviors = [i for i in args if isinstance(i, ArparmaBehavior)]
        _behaviors.extend(behaviors or [])
        for behavior in _behaviors:
            self.behaviors.extend(requirement_handler(behavior))
        command_manager.register(self)
        self.formatter.add(self)
        self._executors: dict[ArparmaExecutor, Any] = {}
        self.union: "WeakSet[Alconna]" = WeakSet()

    @property
    def namespace_config(self) -> Namespace:
        return global_config.namespaces[self.namespace]

    def reset_namespace(self, namespace: Namespace | str, header: bool = True) -> Self:
        """重新设置命名空间

        Args:
            namespace (Namespace | str): 命名空间
            header (bool, optional): 是否保留命令头, 默认为 `True`
        """
        with command_manager.update(self):
            if isinstance(namespace, str):
                namespace = global_config.namespaces.setdefault(namespace, Namespace(namespace))
            self.namespace = namespace.name
            if header:
                self.prefixes = namespace.prefixes.copy()
            self.config = Config.merge(self.config, namespace.config)
            self.options = [opt for opt in self.options if not isinstance(opt, SPECIAL_OPTIONS)]
            add_builtin_options(self.options, self.router, self.config)
        return self

    def get_help(self) -> str:
        """返回该命令的帮助信息"""
        return self.formatter.format_node()

    def get_shortcuts(self) -> list[str]:
        """返回该命令注册的快捷命令"""
        result = []
        shortcuts = command_manager.get_shortcut(self)
        for key, short in shortcuts.items():
            if isinstance(short, InnerShortcutArgs):
                prefixes = f"[{'│'.join(short.prefixes)}]" if short.prefixes else ""
                result.append(prefixes + key + (" ...args" if short.fuzzy else ""))
            else:
                result.append(key)
        return result

    def _get_shortcuts(self):
        """返回该命令注册的快捷命令"""
        return command_manager.get_shortcut(self)

    @overload
    def shortcut(self, key: str | TPattern, args: ShortcutArgs) -> str:
        """操作快捷命令

        Args:
            key (str | re.Pattern[str]): 快捷命令名, 可传入正则表达式
            args (ShortcutArgs): 快捷命令参数, 不传入时则尝试使用最近一次使用的命令

        Returns:
            str: 操作结果

        Raises:
            ValueError: 快捷命令操作失败时抛出
        """
        ...

    @overload
    def shortcut(
        self,
        key: str | TPattern,
        *,
        command: str | None = None,
        arguments: list[Any] | None = None,
        fuzzy: bool = True,
        prefix: bool = False,
        wrapper: ShortcutRegWrapper | None = None,
        humanized: str | None = None,
    ) -> str:
        """操作快捷命令

        Args:
            key (str | re.Pattern[str]): 快捷命令名, 可传入正则表达式
            command (str): 快捷命令指向的命令
            arguments (list[Any] | None, optional): 快捷命令参数, 默认为 `None`
            fuzzy (bool, optional): 是否允许命令后随参数, 默认为 `True`
            prefix (bool, optional): 是否调用时保留指令前缀, 默认为 `False`
            wrapper (ShortcutRegWrapper, optional): 快捷指令的正则匹配结果的额外处理函数, 默认为 `None`
            humanized (str, optional): 快捷指令的人类可读描述, 默认为 `None`

        Returns:
            str: 操作结果

        Raises:
            ValueError: 快捷命令操作失败时抛出
        """
        ...

    @overload
    def shortcut(self, key: str | TPattern, *, delete: Literal[True]) -> str:
        """操作快捷命令

        Args:
            key (str | re.Pattern[str]): 快捷命令名, 可传入正则表达式
            delete (bool): 是否删除快捷命令

        Returns:
            str: 操作结果

        Raises:
            ValueError: 快捷命令操作失败时抛出
        """
        ...

    def shortcut(self, key: str | TPattern, args: ShortcutArgs | None = None, delete: bool = False, **kwargs):
        try:
            if delete:
                return command_manager.delete_shortcut(self, key)
            if kwargs and not args:
                kwargs["args"] = kwargs.pop("arguments", None)
                kwargs = {k: v for k, v in kwargs.items() if v is not None}
                if kwargs.get("command") == "$":
                    del kwargs["command"]
                args = cast(ShortcutArgs, kwargs)
            if args is not None:
                return command_manager.add_shortcut(self, key, args)
            else:
                raise ValueError(args)
        except Exception as e:
            if self.config.raise_exception:
                raise e
            return str(e)

    def __repr__(self):
        return f"{self.namespace}::{self.name}(args={self.args!r}, options={self.options})"

    def add(self, opt: Option | Subcommand) -> Self:
        """添加选项或子命令

        Args:
            opt (Option | Subcommand): 选项或子命令

        Returns:
            Self: 命令本身
        """
        with command_manager.update(self):
            self.options.append(opt)
        return self

    @init_spec(Option, is_method=True)
    def option(self, opt: Option) -> Self:
        """添加选项"""
        return self.add(opt)

    @init_spec(Subcommand, is_method=True)
    def subcommand(self, sub: Subcommand) -> Self:
        """添加子命令"""
        return self.add(sub)

    def _parse(self, message: TDC, ctx: dict[str, Any] | None = None) -> Arparma[TDC]:
        if self.union:
            for alc in self.union:
                if (res := alc._parse(message, ctx)).matched:
                    return res
        analyser = command_manager.require(self)
        argv = analyser.argv
        argv.enter(ctx).build(message)
        if argv.message_cache and (res := command_manager.get_record(argv.token)):
            return res
        if not (exc := analyser.process(argv)):
            return analyser.export(argv)
        if isinstance(exc, InvalidHeader):
            trigger = exc.context_node
            if trigger.__class__ is str and trigger:
                argv.context[SHORTCUT_TRIGGER] = trigger
                try:
                    rest, short, mat = command_manager.find_shortcut(self, [trigger] + argv.release(no_split=True))
                    argv.context[SHORTCUT_ARGS] = short
                    argv.context[SHORTCUT_REST] = rest
                    argv.context[SHORTCUT_REGEX_MATCH] = mat
                    argv.reset()
                    argv.addon(wrap_shortcut(rest, short, mat, argv.context), merge_str=False)
                    analyser.header_result = analyse_header(self._header, argv)
                    analyser.header_result.origin = trigger
                    if not (exc := analyser.process(argv)):
                        return analyser.export(argv)
                except ValueError:
                    if argv.fuzzy_match and (res := handle_head_fuzzy(self._header, trigger, argv.fuzzy_threshold)):
                        exc = FuzzyMatchSuccess(res)
                except AlconnaException as e:
                    exc = e
        if isinstance(exc, PauseTriggered):
            raise exc
        return analyser.export(argv, True, exc)

    def parse(self, message: TDC, ctx: dict[str, Any] | None = None) -> Arparma[TDC]:
        """命令分析功能, 传入字符串或消息链, 返回一个特定的数据集合类

        Args:
            message (TDC): 命令消息
            ctx (dict[str, Any], optional): 上下文信息
        Returns:
            Arparma[TDC] | T_Duplication: 若`duplication`参数为`None`则返回`Arparma`对象, 否则返回`duplication`类型的对象
        Raises:
            NullMessage: 传入的消息为空时抛出
        """
        arp = self._parse(message, ctx)
        if arp.matched:
            arp = arp.execute(self.behaviors)
        if arp.matched and self._executors:
            for ext in self._executors:
                self._executors[ext] = arp.call(ext.target)
        if err := self.router.execute(self, arp):
            return arp.fail(err)
        return arp

    def bind(self, active: bool = True):
        """绑定命令执行器

        Args:
            active (bool, optional): 该执行器是否由 `Alconna` 主动调用, 默认为 `True`
        """

        def wrapper(target: Callable[..., T]) -> ArparmaExecutor[T]:
            ext = ArparmaExecutor(target, lambda: command_manager.get_result(self))
            if active:
                self._executors[ext] = None
            return ext

        return wrapper

    @property
    def exec_result(self) -> dict[str, Any]:
        return {ext.target.__name__: res for ext, res in self._executors.items() if res is not None}

    def __truediv__(self, other) -> Self:
        return self.reset_namespace(other)

    __rtruediv__ = __truediv__

    def __add__(self, other) -> Self:
        with command_manager.update(self):
            if isinstance(other, Alconna):
                self.options.extend(other.options)
            elif isinstance(other, Metadata):
                self.meta = other
            elif isinstance(other, Config):
                self.config = other
            elif isinstance(other, Option):
                self.options.append(other)
            elif isinstance(other, Args):
                self.args += other
                self.nargs = len(self.args)
            elif isinstance(other, str):
                self.options.append(Option(other))
        return self

    def __or__(self, other: Alconna) -> Self:
        self.union.add(other)
        return self

    def _calc_hash(self):
        return hash((self.namespace, self.header_display, self.meta, *self.options, *self.args))

    def __call__(self, *args):
        if args:
            res = self.parse(list(args))  # type: ignore
        else:
            head = handle_argv()
            argv = [(f"\"{arg}\"" if any(arg.count(sep) for sep in self.separators) else arg) for arg in sys.argv[1:]]
            if head != self.command:
                return self.parse(argv)  # type: ignore
            res = self.parse([head, *argv])  # type: ignore
        if res.output:
            print(res.output)
        return res

    @property
    def header_display(self):
        return str(self._header)


__all__ = ["Alconna", "ArparmaExecutor"]
