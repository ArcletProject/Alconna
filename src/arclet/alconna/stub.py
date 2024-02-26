from __future__ import annotations

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from inspect import isclass
from typing import Any, Generic, TypeVar
from typing_extensions import Self

from nepattern import ANY, BasePattern

from .args import Args
from .base import Option, Subcommand
from .model import OptionResult, SubcommandResult
from .typing import AllParam

T = TypeVar("T")
T_Origin = TypeVar("T_Origin")


@dataclass(init=True, eq=True)
class BaseStub(Generic[T_Origin], metaclass=ABCMeta):
    """基础的命令组件存根"""

    _origin: T_Origin
    """原始的命令组件"""
    _value: Any = field(default=None)
    """解析结果"""
    available: bool = field(default=False, init=False)
    """是否可用"""

    @property
    def origin(self) -> T_Origin:
        """原始的命令组件"""
        return self._origin

    @abstractmethod
    def set_result(self, result: Any) -> Self:
        """设置解析结果与可用性"""

    def __repr__(self):
        return f"{{{', '.join([f'{k}={v}' for k, v in vars(self).items() if v and not k.startswith('_')])}}}"


@dataclass(init=True)
class ArgsStub(BaseStub[Args]):
    """参数存根"""

    _value: dict[str, Any] = field(default_factory=dict)
    """解析结果"""

    def __post_init__(self):
        for arg in self._origin.argument:
            key = arg.name
            if arg.value in (AllParam, ANY):
                self.__annotations__[key] = Any
            elif isinstance(arg.value, BasePattern):
                self.__annotations__[key] = arg.value.origin
            else:
                self.__annotations__[key] = arg.value
            setattr(self, key, arg.field.default)

    def set_result(self, result: dict[str, Any]):
        if result:
            self._value = result.copy()
            self.available = True
        return self

    @property
    def first(self) -> Any:
        """第一个参数"""
        return self.__getitem__(0)

    def get(self, item: str | type[T], default=None) -> T | Any:
        """获取参数结果

        Args:
            item (str | type[T]): 参数名或参数类型
            default (Any, optional): 默认值. Defaults to None.
        """
        if isinstance(item, str):
            return self._value.get(item, default)
        for k, v in self.__annotations__.items():
            if isclass(v) and (item == v or issubclass(v, item)):
                return self._value.get(k, default)
        return default

    def __contains__(self, item):
        return item in self._value

    def __iter__(self):
        return iter(self._value)

    def __len__(self):
        return len(self._value)

    def __getattribute__(self, item):
        if item not in (_cache := super().__getattribute__("_value")):
            return super().__getattribute__(item)
        return _cache.get(item, None)

    def __getitem__(self, item: int | str) -> Any:
        if isinstance(item, int):
            return list(self._value.values())[item]
        return self._value[item]


@dataclass(init=True)
class OptionStub(BaseStub[Option]):
    """选项存根"""

    args: ArgsStub = field(init=False)
    """选项的参数存根"""
    dest: str = field(init=False)
    """选项的目标名称"""
    aliases: list[str] = field(init=False)
    """选项的别名"""
    name: str = field(init=False)
    """选项的名称"""

    def __post_init__(self):
        self.dest = self._origin.dest
        self.aliases = [alias.lstrip("-") for alias in self._origin.aliases]
        self.name = self._origin.name.lstrip("-")
        self.args = ArgsStub(self._origin.args)

    def set_result(self, result: OptionResult | None):
        if result:
            self._value = result.value
            self.args.set_result(result.args)
            self.available = True
        return self


@dataclass(init=True)
class SubcommandStub(BaseStub[Subcommand]):
    """子命令存根"""

    args: ArgsStub = field(init=False)
    """子命令的参数存根"""
    dest: str = field(init=False)
    """子命令的目标名称"""
    options: list[OptionStub] = field(init=False)
    """子命令的子选项存根"""
    subcommands: list[SubcommandStub] = field(init=False)
    """子命令的子子命令存根"""
    name: str = field(init=False)
    """子命令的名称"""

    def __post_init__(self):
        self.dest = self._origin.dest
        self.name = self._origin.name.lstrip("-")
        self.args = ArgsStub(self._origin.args)
        self.options = [OptionStub(opt) for opt in self._origin.options if isinstance(opt, Option)]
        self.subcommands = [SubcommandStub(sub) for sub in self._origin.options if isinstance(sub, Subcommand)]

    def set_result(self, result: SubcommandResult | None):
        if result:
            self._value = result.value
            self.args.set_result(result.args)
            for option in self.options:
                option.set_result(result.options.get(option.dest, None))
            for subcommand in self.subcommands:
                subcommand.set_result(result.subcommands.get(subcommand.dest, None))
            self.available = True
        return self

    def option(self, name: str) -> OptionStub:
        """获取子选项存根

        Args:
            name (str): 子选项名称
        """
        return next(opt for opt in self.options if opt.name == name)

    def subcommand(self, name: str) -> SubcommandStub:
        """获取子子命令存根

        Args:
            name (str): 子子命令名称
        """
        return next(sub for sub in self.subcommands if sub.name == name)
