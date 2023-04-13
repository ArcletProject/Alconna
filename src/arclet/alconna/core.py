"""Alconna 主体"""
from __future__ import annotations

import sys
from dataclasses import InitVar, dataclass, field
from functools import reduce
from typing import Any, Callable, Generic, Sequence, TypeVar, overload

from tarina import init_spec
from typing_extensions import Self

from .action import ArgAction, exec_, exec_args
from .analyser import Analyser
from .args import Arg, Args
from .arparma import Arparma, ArparmaBehavior
from .base import Option, Subcommand
from .config import Namespace, config
from .lang import lang
from .duplication import Duplication
from .exceptions import NullMessage
from .executor import ArparmaExecutor, T
from .formatter import TextFormatter
from .manager import ShortcutArgs, command_manager
from .typing import TDataCollection, THeader

T_Duplication = TypeVar('T_Duplication', bound=Duplication)


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
    description: str = field(default="Unknown")
    usage: str | None = field(default=None)
    example: str | None = field(default=None)
    author: str | None = field(default=None)
    fuzzy_match: bool = field(default=False)
    raise_exception: bool = field(default=False)
    hide: bool = field(default=False)
    keep_crlf: bool = field(default=False)


class Alconna(Subcommand, Generic[TDataCollection]):
    """
    更加精确的命令解析

    Examples:

        >>> from arclet.alconna import Alconna
        >>> alc = Alconna(
        ...     "name",
        ...     ["h1", "h2"],
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
    headers: THeader
    command: str | Any
    analyser_type: type[Analyser]
    formatter: TextFormatter
    namespace: str
    meta: CommandMeta
    behaviors: list[ArparmaBehavior]

    global_analyser_type: type[Analyser] = Analyser

    def compile(self) -> Analyser:
        return self.analyser_type.compile(self)

    @classmethod
    def default_analyser(cls, __t: type[Analyser] | None = None):
        """配置 Alconna 的默认解析器"""
        if __t is not None:
            cls.global_analyser_type = __t
        return cls

    def __init__(
        self,
        *args: Option | Subcommand | str | THeader | Any | Args | Arg,
        action: ArgAction | Callable | None = None,
        meta: CommandMeta | None = None,
        namespace: str | Namespace | None = None,
        separators: str | set[str] | Sequence[str] | None = None,
        analyser_type: type[Analyser] | None = None,
        behaviors: list[ArparmaBehavior] | None = None,
        formatter_type: type[TextFormatter] | None = None
    ):
        """
        以标准形式构造 Alconna

        Args:
            args: 命令选项、主参数、命令名称或命令头
            action: 命令解析后针对主参数的回调函数
            meta: 命令元信息
            namespace: 命令命名空间, 默认为 'Alconna'
            separators: 命令参数分隔符, 默认为空格
            analyser_type: 命令解析器类型, 默认为 DisorderCommandAnalyser
            behaviors: 命令解析行为，默认为 None
            formatter_type: 命令帮助文本格式器类型, 默认为 DefaultHelpTextFormatter
        """
        if not namespace:
            np_config = config.default_namespace
        elif isinstance(namespace, Namespace):
            np_config = config.namespaces.setdefault(namespace.name, namespace)
        else:
            np_config = config.namespaces.setdefault(namespace, Namespace(namespace))
        self.headers = next(filter(lambda x: isinstance(x, list), args + (np_config.headers.copy(),)))  # type: ignore
        try:
            self.command = next(filter(lambda x: not isinstance(x, (list, Option, Subcommand, Args, Arg)), args))
        except StopIteration:
            self.command = "" if self.headers else sys.argv[0]
        self.namespace = np_config.name
        self.analyser_type = analyser_type or self.__class__.global_analyser_type  # type: ignore
        self.formatter = (formatter_type or np_config.formatter_type or TextFormatter)()
        self.meta = meta or CommandMeta()
        self.meta.fuzzy_match = self.meta.fuzzy_match or np_config.fuzzy_match
        self.meta.raise_exception = self.meta.raise_exception or np_config.raise_exception
        options = [i for i in args if isinstance(i, (Option, Subcommand))]
        options.append(
            Option("|".join(np_config.builtin_option_name['help']), help_text=lang.builtin.option_help),
        )
        options.append(
            Option(
                "|".join(np_config.builtin_option_name['shortcut']),
                Args["delete;?", "delete"]["name", str]["command", str, "_"],
                help_text=lang.builtin.option_shortcut
            )
        )
        options.append(
            Option(
                "|".join(np_config.builtin_option_name['completion']), help_text=lang.builtin.option_completion
            )
        )
        name = f"{self.command or self.headers[0]}".replace(command_manager.sign, "")  # type: ignore
        self.path = f"{self.namespace}::{name}"
        super().__init__(
            "ALCONNA::",
            reduce(lambda x, y: x + y, [Args()] + [i for i in args if isinstance(i, (Arg, Args))]),  # type: ignore
            *options,
            dest=name,
            action=action,
            separators=separators or np_config.separators,
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
        """重新设置命名空间"""
        command_manager.delete(self)
        if isinstance(namespace, str):
            namespace = config.namespaces.setdefault(namespace, Namespace(namespace))
        self.namespace = namespace.name
        self.path = f"{self.namespace}::{self.name}"
        if header:
            self.headers = namespace.headers.copy()
        self.options[-3] = Option(
            "|".join(namespace.builtin_option_name['help']), help_text=lang.builtin.option_help
        )
        self.options[-2] = Option(
            "|".join(namespace.builtin_option_name['shortcut']),
            Args["delete;?", "delete"]["name", str]["command", str, "_"],
            help_text=lang.builtin.option_shortcut
        )
        self.options[-1] = Option(
            "|".join(namespace.builtin_option_name['completion']), help_text=lang.builtin.option_completion
        )
        self.meta.fuzzy_match = namespace.fuzzy_match or self.meta.fuzzy_match
        self.meta.raise_exception = namespace.raise_exception or self.meta.raise_exception
        self._hash = self._calc_hash()
        command_manager.register(self)
        return self

    def reset_behaviors(self, behaviors: list[ArparmaBehavior]) -> Self:
        """重新设置解析行为器"""
        self.behaviors[1:] = behaviors
        return self

    def get_help(self) -> str:
        """返回该命令的帮助信息"""
        return self.formatter.format_node()

    def shortcut(self, key: str, args: ShortcutArgs[TDataCollection] | None = None, delete: bool = False):
        """添加快捷命令"""
        try:
            if delete:
                command_manager.delete_shortcut(self, key)
                return lang.shortcut.delete_success.format(shortcut=key, target=self.path)
            if args:
                command_manager.add_shortcut(self, key, args)
                return lang.shortcut.add_success.format(shortcut=key, target=self.path)
            elif cmd := command_manager.recent_message:
                alc = command_manager.last_using
                if alc and alc == self:
                    command_manager.add_shortcut(self, key, {"command": cmd})
                    return lang.shortcut.add_success.format(shortcut=key, target=self.path)
                raise ValueError(
                    lang.shortcut.recent_command_error.format(target=self.path, source=getattr(alc, "path", "Unknown"))
                )
            else:
                raise ValueError(lang.shortcut.no_recent_command)
        except Exception as e:
            if self.meta.raise_exception:
                raise e
            return str(e)

    def __repr__(self):
        return f"{self.namespace}::{self.name}(args={self.args}, options={self.options})"

    def add(self, opt: Option | Subcommand) -> Self:
        command_manager.delete(self)
        self.options.insert(-3, opt)
        self.behaviors[0] = ActionHandler(self)
        self._hash = self._calc_hash()
        command_manager.register(self)
        return self

    @init_spec(Option, True)
    def option(self, opt: Option) -> Self:
        return self.add(opt)

    @init_spec(Subcommand, True)
    def subcommand(self, sub: Subcommand) -> Self:
        return self.add(sub)

    def _parse(self, message: TDataCollection) -> Arparma[TDataCollection]:
        if self.union:
            for ana in command_manager.requires(*self.union):
                ana.container.build(message)
                if (res := ana.process()).matched:
                    return res
        analyser = command_manager.require(self)
        analyser.container.build(message)
        return analyser.process()

    @overload
    def parse(self, message: TDataCollection) -> Arparma[TDataCollection]:
        ...

    @overload
    def parse(self, message, *, duplication: type[T_Duplication]) -> T_Duplication:
        ...

    def parse(
        self, message: TDataCollection, *, duplication: type[T_Duplication] | None = None
    ) -> Arparma[TDataCollection] | T_Duplication:
        """命令分析功能, 传入字符串或消息链, 返回一个特定的数据集合类"""
        try:
            arp = self._parse(message)
        except NullMessage as e:
            if self.meta.raise_exception:
                raise e
            return Arparma(self.path, message, False, error_info=e)
        if arp.matched:
            self.behaviors[0].operate(arp)
            arp = arp.execute()
        return duplication(arp) if duplication else arp

    def bind(self, target: Callable[..., T]) -> ArparmaExecutor[T]:
        ext = ArparmaExecutor(target)
        ext.binding = lambda: command_manager.get_result(self)
        self._executors.append(ext)
        return self._executors[-1]

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
        return hash(
            (self.path + str(self.headers), self.meta, *self.options, *self.args.argument)
        )


__all__ = ["Alconna", "CommandMeta"]
