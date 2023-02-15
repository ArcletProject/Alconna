"""Alconna 主体"""
from __future__ import annotations

import sys
from functools import reduce
from typing import List, Union, Tuple, overload, Any, Literal, Generic, Sequence
from typing_extensions import Self
from dataclasses import dataclass, field
from .config import config, Namespace
from .args import Args, Arg
from .base import Option, Subcommand
from .typing import TDataCollection
from .arparma import Arparma
from .exceptions import PauseTriggered
from .analysis.analyser import Analyser, TAnalyser, compile
from .output import TextFormatter


T_Header = Union[List[Union[str, object]], List[Tuple[object, str]]]


@dataclass(unsafe_hash=True)
class CommandMeta:
    description: str = field(default="Unknown")
    usage: str | None = field(default=None)
    example: str | None = field(default=None)
    author: str | None = field(default=None)
    raise_exception: bool = field(default=False)
    keep_crlf: bool = field(default=False)


class Alconna(Subcommand, Generic[TAnalyser]):
    """更加精确的命令解析"""
    custom_types = {}

    global_analyser_type: type[Analyser] = Analyser

    @classmethod
    def default_analyser(cls, __t: type[TAnalyser] | None = None) -> type[Alconna[TAnalyser]]:
        """配置 Alconna 的默认解析器"""
        if __t is not None:
            cls.global_analyser_type = __t
        return cls

    def __init__(
        self,
        *args: Option | Subcommand | str | T_Header | Any | Args | Arg,
        meta: CommandMeta | None = None,
        namespace: str | Namespace | None = None,
        separators: str | set[str] | Sequence[str] | None = None,
        analyser_type: type[TAnalyser] | None = None,
        formatter_type: type[TextFormatter] | None = None
    ):
        """
        以标准形式构造 Alconna

        Args:
            args: 命令选项、主参数、命令名称或命令头
            meta: 命令元信息
            namespace: 命令命名空间, 默认为 'Alconna'
            separators: 命令参数分隔符, 默认为空格
            analyser_type: 命令解析器类型, 默认为 DisorderCommandAnalyser
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
        self.formatter = (formatter_type or TextFormatter)()
        self.meta = meta or CommandMeta()
        self.meta.raise_exception = self.meta.raise_exception or np_config.raise_exception
        super().__init__(
            "ALCONNA",
            reduce(lambda x, y: x + y, [Args()] + [i for i in args if isinstance(i, (Arg, Args))]),  # type: ignore
            separators=separators or np_config.separators,
        )
        self.options = [i for i in args if isinstance(i, (Option, Subcommand))]
        self.options.append(
            Option("|".join(np_config.builtin_option_name['help']), help_text=config.lang.builtin_option_help),
        )
        self.name = f"{self.command or self.headers[0]}"
        self._hash = self._calc_hash()
        self._analyser = compile(self)

    @property
    def path(self) -> str:
        return f"{self.namespace}::{self.name}"

    @property
    def namespace_config(self) -> Namespace:
        return config.namespaces[self.namespace]

    def reset_namespace(self, namespace: Namespace | str, header: bool = True) -> Self:
        """重新设置命名空间"""
        if isinstance(namespace, str):
            namespace = config.namespaces.setdefault(namespace, Namespace(namespace))
        self.namespace = namespace.name
        if header:
            self.headers = namespace.headers.copy()
        self.options[-1] = Option(
            "|".join(namespace.builtin_option_name['help']), help_text=config.lang.builtin_option_help
        )
        self.meta.raise_exception = namespace.raise_exception or self.meta.raise_exception
        self._hash = self._calc_hash()
        self._analyser = compile(self)
        return self

    def get_help(self) -> str:
        """返回该命令的帮助信息"""
        return self.formatter.format_node()

    @classmethod
    def set_custom_types(cls, **types: type):
        """设置Alconna内的自定义类型"""
        cls.custom_types = types
    def __repr__(self):
        return f"{self.namespace}::{self.name}(args={self.args}, options={self.options})"

    def add(self, opt: Option | Subcommand) -> Self:
        self.options.insert(-1, opt)
        self._hash = self._calc_hash()
        self._analyser = compile(self)
        return self
    @overload
    def parse(self, message: TDataCollection) -> Arparma[TDataCollection]: ...
    @overload
    def parse(self, message, *, interrupt: Literal[True]) -> TAnalyser: ...
    def parse(self, message: TDataCollection, *, interrupt: bool = False) -> TAnalyser | Arparma[TDataCollection]:
        """命令分析功能, 传入字符串或消息链, 返回一个特定的数据集合类"""
        try:
            self._analyser.container.build(message)
            return self._analyser.process(interrupt=interrupt)
        except PauseTriggered:
            return self._analyser

    def __truediv__(self, other) -> Self:
        return self.reset_namespace(other)

    __rtruediv__ = __truediv__

    def __add__(self, other) -> Self:
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
        self._analyser = compile(self)
        return self
    def _calc_hash(self):
        return hash(
            (self.path + str(self.headers), self.meta, *self.options, *self.args.argument)
        )
