"""Alconna 主体"""
import sys
from functools import reduce
from typing import Dict, List, Optional, Union, Type, Callable, Tuple, TypeVar, overload, Iterable, Any, Literal
from dataclasses import dataclass, field
from .config import config, Namespace
from .analysis.base import compile
from .args import Args, Arg
from .base import CommandNode, Option, Subcommand
from .typing import TDataCollection
from .manager import command_manager
from .arpamar import Arpamar
from .exceptions import PauseTriggered
from .analysis.analyser import TAnalyser, Analyser
from .components.action import ActionHandler, ArgAction
from .components.output import TextFormatter
from .components.behavior import T_ABehavior
from .components.duplication import Duplication
from .components.executor import ArpamarExecutor, T

T_Duplication = TypeVar('T_Duplication', bound=Duplication)
T_Header = Union[List[Union[str, object]], List[Tuple[object, str]]]


@dataclass(unsafe_hash=True)
class CommandMeta:
    description: str = field(default="Unknown")
    usage: Optional[str] = field(default=None)
    example: Optional[str] = field(default=None)
    author: Optional[str] = field(default=None)
    fuzzy_match: bool = field(default=False)
    raise_exception: bool = field(default=False)
    hide: bool = field(default=False)
    keep_crlf: bool = field(default=False)


class AlconnaGroup(CommandNode):
    _group = True
    meta: CommandMeta
    commands: List['Alconna']

    def __init__(
        self,
        name: str,
        *commands: "Alconna",
        namespace: Optional[Union[str, Namespace]] = None,
    ):
        if not namespace:
            self.namespace = config.default_namespace.name
        elif isinstance(namespace, Namespace):
            self.namespace = config.namespaces.setdefault(namespace.name, namespace).name
        else:
            self.namespace = config.namespaces.setdefault(namespace, Namespace(namespace)).name
        self.commands = list(commands)
        self.meta = CommandMeta()
        name = command_manager.sign + name
        super().__init__(name, )
        self.name.replace(command_manager.sign, '')
        self.__handler_help_text__()

    def __handler_help_text__(self):
        self.meta.description = "\n"
        for command in self.commands:
            self.meta.description += f" * {command.name} : {command.meta.description}\n"
        return self

    @property
    def path(self) -> str:
        return f"{self.namespace}::{self.name.replace(command_manager.sign, '')}"

    def get_help(self) -> str:
        """返回该命令的帮助信息"""
        return self.commands[0].formatter_type(self).format_node()

    def append(self, *commands: "Alconna"):
        self.commands += list(commands)
        self.__handler_help_text__()
        return self

    def __union__(self, other: Union["AlconnaGroup", "Alconna"]):
        if isinstance(other, AlconnaGroup):
            self.commands += other.commands
            self.__handler_help_text__()
        else:
            self.commands.append(other)
        return self

    def reset_namespace(self, namespace: Union[str, Namespace]):
        """重新设置命名空间"""
        command_manager.delete(self)
        if isinstance(namespace, str):
            namespace = config.namespaces.setdefault(namespace, Namespace(namespace))
        self.namespace = namespace.name
        self._hash = self._calc_hash()
        command_manager.register(self)
        return self

    def __iter__(self):
        yield from self.commands

    def __getitem__(self, item: str):
        try:
            return next(filter(lambda x: x.name == item, self.commands))
        except StopIteration as e:
            raise KeyError(item) from e

    def __or__(self, other):
        return self.__union__(other)

    def parse(self, message: TDataCollection) -> Optional[Arpamar[TDataCollection]]:
        res = None
        for command in self.commands:
            if (res := command.parse(message)).matched:
                return res
        return res


class Alconna(CommandNode):
    """
    亚尔康娜 (Alconna), Cesloi 的妹妹

    用于更加精确的命令解析

    Examples:

        >>> from arclet.alconna import Alconna
        >>> alc = Alconna(
        ...     "name",
        ...     ["h1", "h2"],
        ...     Option("opt", Args["opt_arg", "opt_arg"]),
        ...     Subcommand(
        ...         "sub_name",
        ...         [Option("sub_opt", Args["sub_arg", "sub_arg"])],
        ...          Args["sub_main_args", "sub_main_args"]
        ...     ),
        ...     Args["main_args", "main_args"],
        ...  )
        >>> alc.parse("name opt opt_arg")
    """
    _group = False
    headers: Union[List[Union[str, object]], List[Tuple[object, str]]]
    command: Union[str, Any]
    options: List[Union[Option, Subcommand]]
    analyser_type: Type[Analyser]
    formatter_type: Type[TextFormatter]
    namespace: str
    meta: CommandMeta
    behaviors: List[T_ABehavior]
    action_list: Dict[str, Union[None, ArgAction, Dict[str, ArgAction]]]
    custom_types = {}

    global_analyser_type: Type["Analyser"] = Analyser

    @classmethod
    def default_analyser(cls, __t: Optional[Type[TAnalyser]] = None):
        """配置 Alconna 的默认解析器"""
        if __t is not None:
            cls.global_analyser_type = __t
        return cls

    def __init__(
        self,
        *args: Union[Option, Subcommand, str, T_Header, Any, Args, Arg],
        action: Optional[Union[ArgAction, Callable]] = None,
        meta: Optional[CommandMeta] = None,
        namespace: Optional[Union[str, Namespace]] = None,
        separators: Optional[Union[str, Iterable[str]]] = None,
        analyser_type: Optional[Type[TAnalyser]] = None,
        behaviors: Optional[List[T_ABehavior]] = None,
        formatter_type: Optional[Type[TextFormatter]] = None
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
        self.headers = next(filter(lambda x: isinstance(x, list), args + (np_config.headers,)))  # type: ignore
        try:
            self.command = next(filter(lambda x: not isinstance(x, (list, Option, Subcommand, Args, Arg)), args))
        except StopIteration:
            self.command = "" if self.headers else sys.argv[0]
        self.options = [i for i in args if isinstance(i, (Option, Subcommand))]
        self.action_list = {"options": {}, "subcommands": {}, "main": None}
        self.namespace = np_config.name
        self.options.append(
            Option("|".join(np_config.builtin_option_name['help']), help_text=config.lang.builtin_option_help),
        )
        self.options.append(
            Option(
                "|".join(np_config.builtin_option_name['shortcut']),
                Args["delete;O", "delete"]["name", str]["command", str, "_"],
                help_text=config.lang.builtin_option_shortcut
            )
        )
        self.options.append(
            Option(
                "|".join(np_config.builtin_option_name['completion']), help_text=config.lang.builtin_option_completion
            )
        )
        self.analyser_type = analyser_type or self.__class__.global_analyser_type  # type: ignore
        self.behaviors = behaviors or []
        self.behaviors.insert(0, ActionHandler())
        self.behaviors.extend(np_config.behaviors)
        self.formatter_type = formatter_type or np_config.formatter_type or TextFormatter
        self.meta = meta or CommandMeta()
        self.meta.fuzzy_match = self.meta.fuzzy_match or np_config.fuzzy_match
        self.meta.raise_exception = self.meta.raise_exception or np_config.raise_exception
        super().__init__(
            command_manager.sign,
            reduce(lambda x, y: x + y, [Args()] + [i for i in args if isinstance(i, (Arg, Args))]),
            action=action,
            separators=separators or np_config.separators,  # type: ignore
        )
        self.name = f"{self.command or self.headers[0]}".replace(command_manager.sign, "")  # type: ignore
        self._hash = self._calc_hash()
        command_manager.register(self)
        self._executors: List[ArpamarExecutor] = []

    def __union__(self, other: Union["Alconna", AlconnaGroup]) -> AlconnaGroup:
        """
        合并两个 重名的 Alconna 实例
        """
        if self.path != other.path:
            raise ValueError("两个命令的命令名称不一致")
        if isinstance(other, Alconna):
            return AlconnaGroup(self.name, self, other, namespace=self.namespace)
        return other.append(self)

    @property
    def path(self) -> str:
        return f"{self.namespace}::{self.name.replace(command_manager.sign, '')}"

    @property
    def namespace_config(self) -> Namespace:
        return config.namespaces[self.namespace]

    def reset_namespace(self, namespace: Union[Namespace, str], header: bool = True):
        """重新设置命名空间"""
        command_manager.delete(self)
        if isinstance(namespace, str):
            namespace = config.namespaces.setdefault(namespace, Namespace(namespace))
        self.namespace = namespace.name
        if header:
            self.headers = namespace.headers.copy()
        self.behaviors[1:] = namespace.behaviors[:]
        self.formatter_type = namespace.formatter_type or self.formatter_type
        self.options[-3] = Option(
            "|".join(namespace.builtin_option_name['help']), help_text=config.lang.builtin_option_help
        )
        self.options[-2] = Option(
            "|".join(namespace.builtin_option_name['shortcut']),
            Args["delete;O", "delete"]["name", str]["command", str, "_"],
            help_text=config.lang.builtin_option_shortcut
        )
        self.options[-1] = Option(
            "|".join(namespace.builtin_option_name['completion']), help_text=config.lang.builtin_option_completion
        )
        self.meta.fuzzy_match = namespace.fuzzy_match
        self.meta.raise_exception = namespace.raise_exception
        self._hash = self._calc_hash()
        command_manager.register(self)
        return self

    def reset_behaviors(self, behaviors: List[T_ABehavior]):
        """重新设置解析行为器"""
        self.behaviors = behaviors
        self.behaviors.insert(0, ActionHandler())
        return self

    def get_help(self) -> str:
        """返回该命令的帮助信息"""
        return self.formatter_type(self).format_node()

    @classmethod
    def set_custom_types(cls, **types: Type):
        """设置Alconna内的自定义类型"""
        cls.custom_types = types

    def shortcut(
        self, short_key: str, command: Optional[TDataCollection] = None, delete: bool = False
    ):
        """添加快捷命令"""
        try:
            if delete:
                command_manager.delete_shortcut(short_key, self)
                return config.lang.shortcut_delete_success.format(shortcut=short_key, target=self.path.split(".")[-1])
            if command:
                command_manager.add_shortcut(self, short_key, command)
                return config.lang.shortcut_add_success.format(shortcut=short_key, target=self.path.split(".")[-1])
            elif cmd := command_manager.recent_message:
                alc = command_manager.last_using
                if alc and alc == self:
                    command_manager.add_shortcut(self, short_key, cmd)
                    return config.lang.shortcut_add_success.format(shortcut=short_key, target=self.path.split(".")[-1])
                raise ValueError(
                    config.lang.shortcut_recent_command_error.format(
                        target=self.path, source=getattr(alc, "path", "Unknown"))
                )
            else:
                raise ValueError(config.lang.shortcut_no_recent_command)
        except Exception as e:
            if self.meta.raise_exception:
                raise e
            return str(e)

    def __repr__(self):
        return f"{self.namespace}::{self.name}(args={self.args}, options={self.options})"

    def add(self, name: str, *alias: str, args: Optional[Args] = None, sep: str = " ", help_: Optional[str] = None):
        """链式注册一个 Option"""
        command_manager.delete(self)
        names = name.split(sep)
        name, requires = names[-1], names[:-1]
        opt = Option(name, args, list(alias), separators=sep, help_text=help_, requires=requires)
        self.options.insert(-3, opt)
        self._hash = self._calc_hash()
        command_manager.register(self)
        return self

    @overload
    def parse(
        self, message: TDataCollection
    ) -> Arpamar[TDataCollection]:
        ...

    @overload
    def parse(
        self, message, *, duplication: Type[T_Duplication]
    ) -> T_Duplication:
        ...

    @overload
    def parse(
        self, message: TDataCollection, *, interrupt: Literal[True]
    ) -> Analyser[TDataCollection]:
        ...

    def parse(
        self, message: TDataCollection, *, duplication: Optional[Type[T_Duplication]] = None,
        interrupt: bool = False, static: bool = True
    ) -> Union[Analyser[TDataCollection], Arpamar[TDataCollection], T_Duplication]:
        """命令分析功能, 传入字符串或消息链, 返回一个特定的数据集合类"""
        analyser = command_manager.require(self) if static else compile(self)
        analyser.process(message)
        try:
            arp: Arpamar[TDataCollection] = analyser.analyse(interrupt=interrupt)
        except PauseTriggered:
            return analyser
        if arp.matched:
            arp = arp.execute()
        return duplication(self).set_target(arp) if duplication else arp

    def bind(self, target: Callable[..., T]) -> ArpamarExecutor[T]:
        ext = ArpamarExecutor(target)
        ext.binding = lambda: command_manager.get_result(self)
        self._executors.append(ext)
        return self._executors[-1]

    def __truediv__(self, other):
        self.reset_namespace(other)
        return self

    def __rtruediv__(self, other):
        self.reset_namespace(other)
        return self

    def __add__(self, other):
        command_manager.delete(self)
        if isinstance(other, CommandMeta):
            self.meta = other
        elif isinstance(other, Option):
            self.options.append(other)
        elif isinstance(other, Args):
            self.args += other
            self.nargs = len(self.args)
        elif isinstance(other, str):
            _part = other.split("/")
            self.options.append(Option(_part[0], _part[1] if len(_part) > 1 else None))
        self._hash = self._calc_hash()
        command_manager.register(self)
        return self

    def __or__(self, other):
        if isinstance(other, Alconna):
            return AlconnaGroup(self.name, self, other, namespace=self.namespace)
        return self

    def _calc_hash(self):
        return hash(
            (self.path + str([i.name for i in self.args.argument]) + str([i.value for i in self.args.argument])
             + str(self.headers), *self.options, self.meta)
        )
