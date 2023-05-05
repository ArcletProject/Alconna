"""Alconna 主体"""
from __future__ import annotations

import sys
from dataclasses import InitVar, dataclass, field
from functools import partial, reduce
from pathlib import Path
from typing import Any, Callable, Generic, Sequence, TypeVar, overload

from tarina import init_spec, lang
from typing_extensions import Self

from .action import ArgAction, exec_, exec_args
from .analyser import Analyser, TCompile
from .args import Arg, Args
from .arparma import Arparma, ArparmaBehavior
from .base import Option, Subcommand
from .config import Namespace, config
from .duplication import Duplication
from .exceptions import ExecuteFailed, NullMessage
from .formatter import TextFormatter
from .manager import ShortcutArgs, command_manager
from .typing import TDC, TPrefixes, DataCollection

T_Duplication = TypeVar('T_Duplication', bound=Duplication)
T = TypeVar("T")
TDC1 = TypeVar("TDC1", bound=DataCollection[Any])


@dataclass(init=True, unsafe_hash=True)
class ArparmaExecutor(Generic[T]):
    """Arparma 执行器

    Attributes:
        target(Callable[..., T]): 目标函数
    """
    target: Callable[..., T]
    binding: Callable[..., list[Arparma]] = field(default=lambda: [], repr=False)

    __call__ = lambda self, *args, **kwargs: self.target(*args, **kwargs)

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


@dataclass
class ActionHandler(ArparmaBehavior):
    source: InitVar[Alconna]
    main_action: ArgAction | None = field(init=False, default=None)
    options: dict[str, ArgAction] = field(init=False, default_factory=dict)

    def _step(self, src, prefix=None):
        for opt in src.options:
            if opt.action:
                self.options[(f"{prefix}." if prefix else "") + opt.dest] = opt.action
            if hasattr(opt, "options"):
                self._step(opt, (f"{prefix}." if prefix else "") + opt.dest)

    def __post_init__(self, source: Alconna):
        self.main_action = source.action
        self._step(source)

    def operate(self, interface: Arparma):
        self.before_operate(interface)
        source = interface.source
        if action := self.main_action:
            self.update(interface, "main_args", exec_args(interface.main_args, action, source.meta.raise_exception))
        for path, action in self.options.items():
            if d := interface.query(path, None):
                end, value = exec_(d, action, source.meta.raise_exception)  # type: ignore
                self.update(interface, f"{path}.{end}", value)  # type: ignore


@dataclass(unsafe_hash=True)
class CommandMeta:
    """命令元数据"""

    description: str = field(default="Unknown")
    "命令的描述"
    usage: str | None = field(default=None)
    "命令的用法"
    example: str | None = field(default=None)
    "命令的使用样例"
    author: str | None = field(default=None)
    "命令的作者"
    fuzzy_match: bool = field(default=False)
    "命令是否开启模糊匹配"
    raise_exception: bool = field(default=False)
    "命令是否抛出异常"
    hide: bool = field(default=False)
    "命令是否对manager隐藏"
    keep_crlf: bool = field(default=False)
    "命令是否保留换行字符"
    compact: bool = field(default=False)
    "命令是否允许第一个参数紧随头部"


class Alconna(Subcommand, Generic[TDC]):
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
    prefixes: TPrefixes
    """命令前缀"""
    command: str | Any
    """命令名"""
    analyser_type: type[Analyser]
    """解析器类型"""
    formatter: TextFormatter
    """文本格式化器"""
    namespace: str
    """命名空间"""
    meta: CommandMeta
    """命令元数据"""
    behaviors: list[ArparmaBehavior]
    """命令行为器"""

    global_analyser_type: type[Analyser] = Analyser

    @property
    def compile(self) -> Callable[[TCompile | None], Analyser[TDC]]:
        """编译 `Alconna` 为对应的解析器"""
        return partial(self.analyser_type, self)

    @classmethod
    def default_analyser(cls, __t: type[Analyser[TDC1]]) -> type[Alconna[TDC1]]:
        """配置 `Alconna` 的默认解析器

        Args:
            __t (type[Analyser[TDC1]]): 解析器类型

        Returns:
            type[Alconna[TDC1]]: Alconna 类型
        """
        cls.global_analyser_type = __t
        return cls  # type: ignore

    def __init__(
        self,
        *args: Option | Subcommand | str | TPrefixes | Any | Args | Arg,
        action: ArgAction | Callable | None = None,
        meta: CommandMeta | None = None,
        namespace: str | Namespace | None = None,
        separators: str | set[str] | Sequence[str] | None = None,
        analyser_type: type[Analyser[TDC]] | None = None,
        behaviors: list[ArparmaBehavior] | None = None,
        formatter_type: type[TextFormatter] | None = None
    ):
        """
        以标准形式构造 `Alconna`

        Args:
            *args (Option | Subcommand | str | TPrefixes | Any | Args | Arg): 命令选项、主参数、命令名称或命令头
            action (ArgAction | Callable | None, optional): 命令解析后针对主参数的回调函数
            meta (CommandMeta | None, optional): 命令元信息
            namespace (str | Namespace | None, optional): 命令命名空间, 默认为 'Alconna'
            separators (str | set[str] | Sequence[str] | None, optional): 命令参数分隔符, 默认为 `' '`
            analyser_type (type[Analyser[TDC]] | None, optional): 指定的命令解析器类型
            behaviors (list[ArparmaBehavior] | None, optional): 命令解析行为器
            formatter_type (type[TextFormatter] | None, optional): 指定的命令帮助文本格式器类型
        """
        if not namespace:
            ns_config = config.default_namespace
        elif isinstance(namespace, Namespace):
            ns_config = config.namespaces.setdefault(namespace.name, namespace)
        else:
            ns_config = config.namespaces.setdefault(namespace, Namespace(namespace))
        self.prefixes = next(filter(lambda x: isinstance(x, list), args + (ns_config.prefixes.copy(),)))  # type: ignore
        try:
            self.command = next(filter(lambda x: not isinstance(x, (list, Option, Subcommand, Args, Arg)), args))
        except StopIteration:
            if self.prefixes:
                self.command = ""
            else:
                path = Path(sys.argv[0])
                self.command = path.parent.stem if str(path.parent) not in (".", "/", "\\") else path.stem
        self.namespace = ns_config.name
        self.analyser_type = analyser_type or self.__class__.global_analyser_type  # type: ignore
        self.formatter = (formatter_type or ns_config.formatter_type or TextFormatter)()
        self.meta = meta or CommandMeta()
        self.meta.fuzzy_match = self.meta.fuzzy_match or ns_config.fuzzy_match
        self.meta.raise_exception = self.meta.raise_exception or ns_config.raise_exception
        self.meta.compact = self.meta.compact or ns_config.compact
        options = [i for i in args if isinstance(i, (Option, Subcommand))]
        options.append(
            Option("|".join(ns_config.builtin_option_name['help']), help_text=lang.require("builtin", "option_help")),
        )
        options.append(
            Option(
                "|".join(ns_config.builtin_option_name['shortcut']),
                Args["delete;?", "delete"]["name", str]["command", str, "_"],
                help_text=lang.require("builtin", "option_shortcut")
            )
        )
        options.append(
            Option(
                "|".join(ns_config.builtin_option_name['completion']),
                help_text=lang.require("builtin", "option_completion")
            )
        )
        name = f"{self.command or self.prefixes[0]}".replace(command_manager.sign, "")  # type: ignore
        self.path = f"{self.namespace}::{name}"
        super().__init__(
            "ALCONNA::",
            reduce(lambda x, y: x + y, [Args()] + [i for i in args if isinstance(i, (Arg, Args))]),  # type: ignore
            *options,
            dest=name,
            action=action,
            separators=separators or ns_config.separators,
        )
        self.name = name
        self.behaviors = behaviors or []
        self.behaviors.insert(0, ActionHandler(self))
        command_manager.register(self)
        self._executors: list[ArparmaExecutor] = []
        self.union = set()

    @property
    def namespace_config(self) -> Namespace:
        return config.namespaces[self.namespace]

    def reset_namespace(self, namespace: Namespace | str, header: bool = True) -> Self:
        """重新设置命名空间

        Args:
            namespace (Namespace | str): 命名空间
            header (bool, optional): 是否保留命令头, 默认为 `True`
        """
        command_manager.delete(self)
        if isinstance(namespace, str):
            namespace = config.namespaces.setdefault(namespace, Namespace(namespace))
        self.namespace = namespace.name
        self.path = f"{self.namespace}::{self.name}"
        if header:
            self.prefixes = namespace.prefixes.copy()
        self.options[-3] = Option(
            "|".join(namespace.builtin_option_name['help']), help_text=lang.require("builtin", "option_help")
        )
        self.options[-2] = Option(
            "|".join(namespace.builtin_option_name['shortcut']),
            Args["delete;?", "delete"]["name", str]["command", str, "_"],
            help_text=lang.require("builtin", "option_shortcut")
        )
        self.options[-1] = Option(
            "|".join(namespace.builtin_option_name['completion']),
            help_text=lang.require("builtin", "option_completion")
        )
        self.meta.fuzzy_match = namespace.fuzzy_match or self.meta.fuzzy_match
        self.meta.raise_exception = namespace.raise_exception or self.meta.raise_exception
        self._hash = self._calc_hash()
        command_manager.register(self)
        return self

    def reset_behaviors(self, behaviors: list[ArparmaBehavior]) -> Self:
        """重新设置解析行为器

        Args:
            behaviors (list[ArparmaBehavior]): 解析行为器
        """
        self.behaviors[1:] = behaviors
        return self

    def get_help(self) -> str:
        """返回该命令的帮助信息"""
        return self.formatter.format_node()

    def shortcut(self, key: str, args: ShortcutArgs[TDC] | None = None, delete: bool = False):
        """操作快捷命令

        Args:
            key (str): 快捷命令名
            args (ShortcutArgs[TDC] | None, optional): 快捷命令参数, 不传入时则尝试使用最近一次使用的命令
            delete (bool, optional): 是否删除快捷命令, 默认为 `False`

        Returns:
            str: 操作结果

        Raises:
            ValueError: 快捷命令操作失败时抛出
        """
        try:
            if delete:
                command_manager.delete_shortcut(self, key)
                return lang.require("shortcut", "delete_success").format(shortcut=key, target=self.path)
            if args:
                command_manager.add_shortcut(self, key, args)
                return lang.require("shortcut", "add_success").format(shortcut=key, target=self.path)
            elif cmd := command_manager.recent_message:
                alc = command_manager.last_using
                if alc and alc == self:
                    command_manager.add_shortcut(self, key, {"command": cmd})
                    return lang.require("shortcut", "add_success").format(shortcut=key, target=self.path)
                raise ValueError(
                    lang.require("shortcut", "recent_command_error")
                    .format(target=self.path, source=getattr(alc, "path", "Unknown"))
                )
            else:
                raise ValueError(lang.require("shortcut", "no_recent_command"))
        except Exception as e:
            if self.meta.raise_exception:
                raise e
            return str(e)

    def __repr__(self):
        return f"{self.namespace}::{self.name}(args={self.args}, options={self.options})"

    def add(self, opt: Option | Subcommand) -> Self:
        """添加选项或子命令

        Args:
            opt (Option | Subcommand): 选项或子命令

        Returns:
            Self: 命令本身
        """
        command_manager.delete(self)
        self.options.insert(-3, opt)
        self.behaviors[0] = ActionHandler(self)
        self._hash = self._calc_hash()
        command_manager.register(self)
        return self

    @init_spec(Option, True)
    def option(self, opt: Option) -> Self:
        """添加选项"""
        return self.add(opt)

    @init_spec(Subcommand, True)
    def subcommand(self, sub: Subcommand) -> Self:
        """添加子命令"""
        return self.add(sub)

    def _parse(self, message: TDC) -> Arparma[TDC]:
        if self.union:
            for ana, argv in command_manager.requires(*self.union):
                if (res := ana.process(argv.build(message))).matched:
                    return res
        analyser = command_manager.require(self)
        argv = command_manager.resolve(self)
        argv.build(message)
        return analyser.process(argv)

    @overload
    def parse(self, message: TDC) -> Arparma[TDC]:
        ...

    @overload
    def parse(self, message, *, duplication: type[T_Duplication]) -> T_Duplication:
        ...

    def parse(
        self, message: TDC, *, duplication: type[T_Duplication] | None = None
    ) -> Arparma[TDC] | T_Duplication:
        """命令分析功能, 传入字符串或消息链, 返回一个特定的数据集合类
        
        Args:
            message (TDC): 命令消息
            duplication (type[T_Duplication], optional): 指定的`副本`类型
        Returns:
            Arparma[TDC] | T_Duplication: 若`duplication`参数为`None`则返回`Arparma`对象, 否则返回`duplication`类型的对象
        Raises:
            NullMessage: 传入的消息为空时抛出
        """
        try:
            arp = self._parse(message)
        except NullMessage as e:
            if self.meta.raise_exception:
                raise e
            return Arparma(self.path, message, False, error_info=e)
        if arp.matched:
            self.behaviors[0].operate(arp)
            arp = arp.execute()
            if self._executors:
                for ext in self._executors:
                    arp.call(ext.target)
        return duplication(arp) if duplication else arp

    def bind(self, active: bool = True):
        """绑定命令执行器

        Args:
            active (bool, optional): 该执行器是否由 `Alconna` 主动调用, 默认为 `True`
        """
        def wrapper(target: Callable[..., T]) -> ArparmaExecutor[T]:
            ext = ArparmaExecutor(target, lambda: command_manager.get_result(self))
            if active:
                self._executors.append(ext)
            return ext
        return wrapper

    def __truediv__(self, other) -> Self:
        return self.reset_namespace(other)

    __rtruediv__ = __truediv__

    def __add__(self, other) -> Self:
        command_manager.delete(self)
        if isinstance(other, CommandMeta):
            self.meta = other
        elif isinstance(other, Option):
            self.options.append(other)
        elif isinstance(other, Args):
            self.args += other
            self.nargs = len(self.args)
        elif isinstance(other, str):
            self.options.append(Option(other))
        self.behaviors[0] = ActionHandler(self)
        self._hash = self._calc_hash()
        command_manager.register(self)
        return self

    def __or__(self, other: Alconna) -> Self:
        self.union.add(other.path)
        return self

    def _calc_hash(self):
        return hash((self.path + str(self.prefixes), self.meta, *self.options, *self.args))

    def __call__(self, *args, **kwargs):
        if args:
            return self.parse(list(args))  # type: ignore
        path = Path(sys.argv[0])
        head = path.parent.stem if str(path.parent) not in (".", "/", "\\") else path.stem
        if head != self.command:
            return self.parse(sys.argv[1:])  # type: ignore
        return self.parse([head, *sys.argv[1:]])  # type: ignore

    @property
    def headers(self):
        return self.prefixes


__all__ = ["Alconna", "CommandMeta", "ArparmaExecutor"]
