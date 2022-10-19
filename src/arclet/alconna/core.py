"""Alconna 主体"""
import sys
from functools import reduce
from typing import List, Optional, Union, Type, Callable, Tuple, overload, Iterable, Any
from dataclasses import dataclass, field
from .config import config, Namespace
from .analysis.base import compile
from .args import Args
from .base import CommandNode, Option, Subcommand
from .typing import TDataCollection
from .arpamar import Arpamar
from .exceptions import PauseTriggered
from .analysis.analyser import TAnalyser, Analyser
from .action import ArgAction
from .output import TextFormatter

T_Header = Union[List[Union[str, object]], List[Tuple[object, str]]]


@dataclass(unsafe_hash=True)
class CommandMeta:
    description: str = field(default="Unknown")
    usage: Optional[str] = field(default=None)
    example: Optional[str] = field(default=None)
    author: Optional[str] = field(default=None)
    raise_exception: bool = field(default=False)
    hide: bool = field(default=False)
    keep_crlf: bool = field(default=False)


class Alconna(CommandNode):
    """
    亚尔康娜 (Alconna), Cesloi 的妹妹

    用于更加精确的命令解析
    """
    custom_types = {}

    global_analyser_type: Type["Analyser"] = Analyser
    global_formatter_type: Type[TextFormatter] = TextFormatter

    @classmethod
    def config(
            cls,
            *,
            analyser_type: Optional[Type[TAnalyser]] = None,
            formatter_type: Optional[Type[TextFormatter]] = None,
    ):
        """
        配置 Alconna 的默认属性
        """
        if analyser_type is not None:
            cls.global_analyser_type = analyser_type
        if formatter_type is not None:
            cls.global_formatter_type = formatter_type
        return cls

    def __init__(
        self,
        *args: Union[Option, Subcommand, str, T_Header, Any, Args],
        action: Optional[Union[ArgAction, Callable]] = None,
        meta: Optional[CommandMeta] = None,
        namespace: Optional[Union[str, Namespace]] = None,
        separators: Optional[Union[str, Iterable[str]]] = None,
        analyser_type: Optional[Type[TAnalyser]] = None,
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
            self.command = next(filter(lambda x: not isinstance(x, (list, Option, Subcommand, Args)), args))
        except StopIteration:
            self.command = "" if self.headers else sys.argv[0]
        self.options = [i for i in args if isinstance(i, (Option, Subcommand))]
        self.action_list = {"options": {}, "subcommands": {}, "main": None}
        self.namespace = np_config.name
        self.options.append(Option("--help|-h", help_text=config.lang.builtin_option_help))
        self.analyser_type = analyser_type or self.__class__.global_analyser_type  # type: ignore
        self.formatter_type = formatter_type or self.__class__.global_formatter_type
        self.meta = meta or CommandMeta()
        self.meta.fuzzy_match = self.meta.fuzzy_match or np_config.fuzzy_match
        self.meta.raise_exception = self.meta.raise_exception or np_config.raise_exception
        super().__init__(
            f"ALCONNA",
            reduce(lambda x, y: x + y, li) if (li := [i for i in args if isinstance(i, Args)]) else None,
            action=action,
            separators=separators or np_config.separators.copy(),  # type: ignore
        )
        self.name = f"{self.command or self.headers[0]}".replace(command_manager.sign, "")  # type: ignore
        self._hash = self._calc_hash()
        self._analyser = compile(self)

    @property
    def path(self) -> str:
        return f"{self.namespace}::{self.name}"

    @property
    def namespace_config(self) -> Namespace:
        return config.namespaces[self.namespace]

    def reset_namespace(self, namespace: Union[Namespace, str]):
        """重新设置命名空间"""
        if isinstance(namespace, str):
            namespace = config.namespaces.setdefault(namespace, Namespace(namespace))
        self.namespace = namespace.name
        self.options[0] = Option("--help|-h", help_text=config.lang.builtin_option_help)
        self._hash = self._calc_hash()
        self._analyser = compile(self)
        return self

    def get_help(self) -> str:
        """返回该命令的帮助信息"""
        return self.formatter_type(self).format_node()

    @classmethod
    def set_custom_types(cls, **types: Type):
        """设置Alconna内的自定义类型"""
        cls.custom_types = types

    def __repr__(self):
        return f"{self.namespace}::{self.name}(args={self.args}, options={self.options})"

    def add(self, name: str, *alias: str, args: Optional[Args] = None, sep: str = " ", help_: Optional[str] = None):
        """链式注册一个 Option"""
        names = name.split(sep)
        name, requires = names[-1], names[:-1]
        opt = Option(name, args, list(alias), separators=sep, help_text=help_, requires=requires)
        self.options.append(opt)
        self._hash = self._calc_hash()
        self._analyser = compile(self)
        return self

    @overload
    def parse(
        self, message: TDataCollection, static=True, interrupt=False
    ) -> Arpamar[TDataCollection]:
        ...

    @overload
    def parse(
        self, message, static=True, interrupt=True
    ) -> Analyser:
        ...

    def parse(
            self, message: TDataCollection, static: bool = True, interrupt: bool = False
    ) -> Union[Analyser, Arpamar[TDataCollection]]:
        """命令分析功能, 传入字符串或消息链, 返回一个特定的数据集合类"""
        try:
            return self._analyser.process(message).analyse(interrupt=interrupt)
        except PauseTriggered:
            return self._analyser

    def __truediv__(self, other):
        self.reset_namespace(other)
        return self

    def __rtruediv__(self, other):
        self.reset_namespace(other)
        return self

    def _calc_hash(self):
        return hash(
            (self.path + str(self.args.argument.keys()) + str([i['value'] for i in self.args.argument.values()])
             + str(self.headers), *self.options, self.meta)
        )
