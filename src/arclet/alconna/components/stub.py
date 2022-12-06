from __future__ import annotations

from inspect import isclass
from typing import Any, TypeVar, Generic
from abc import ABCMeta, abstractmethod
from nepattern import BasePattern, AllParam

from ..args import Args
from ..base import Option, Subcommand, OptionResult, SubcommandResult  # type: ignore
from ..config import config

T = TypeVar('T')
T_Origin = TypeVar('T_Origin')


class BaseStub(Generic[T_Origin], metaclass=ABCMeta):
    """
    基础的命令组件存根
    """

    available: bool
    _value: Any
    _origin: T_Origin

    __ignore__ = ['available', '_value', '_origin', 'origin', '__ignore__']

    @property
    def origin(self) -> T_Origin:
        return self._origin

    @abstractmethod
    def set_result(self, result: Any) -> None:
        """
        设置解析结果与可用性
        """

    def __repr__(self):
        return f"{{{', '.join(f'{k}={v}' for k, v in vars(self).items() if v and not k.startswith('_'))}}}"


class ArgsStub(BaseStub[Args]):
    """
    参数存根
    """
    _value: dict[str, Any]

    def __init__(self, args: Args):
        self._origin = args
        self._value = {}
        for arg in args.argument:
            key = arg.name
            if arg.value is AllParam:
                self.__annotations__[key] = Any
            elif isinstance(arg.value, BasePattern):
                self.__annotations__[key] = arg.value.origin
            else:
                self.__annotations__[key] = arg.value
            setattr(self, key, arg.field.default_gen)
        self.available = False

    def set_result(self, result: dict[str, Any]):
        if result:
            self._value = result
            self.available = True

    @property
    def first_arg(self) -> Any:
        return self.__getitem__(0)

    def get(self, item: str | type[T], default=None) -> T | Any:
        if isinstance(item, str):
            return self._value.get(item, default)
        for k, v in self.__annotations__.items():
            if isclass(item):
                if v == item:
                    return self._value.get(k, default)
            elif isinstance(item, v):
                return self._value.get(k, default)
        return default

    def __contains__(self, item):
        return item in self._value

    def __iter__(self):
        return iter(self._value)

    def __len__(self):
        return len(self._value)

    def __getattribute__(self, item):
        if item in super(ArgsStub, self).__getattribute__('__ignore__'):
            return super().__getattribute__(item)
        if item in super().__getattribute__('_value'):
            return super().__getattribute__('_value').get(item, None)
        return super().__getattribute__(item)

    def __getitem__(self, item):
        if isinstance(item, str):
            return self._value[item]
        elif isinstance(item, int):
            return list(self._value.values())[item]
        else:
            raise TypeError(config.lang.stub_key_error.format(target=item))


class OptionStub(BaseStub[Option]):
    """
    选项存根
    """
    args: ArgsStub
    dest: str
    aliases: list[str]
    name: str

    def __init__(self, option: Option):
        self.args = ArgsStub(option.args)
        self.aliases = [alias.lstrip('-') for alias in option.aliases]
        self.name = option.name.lstrip('-')
        self.dest = option.dest
        self._origin = option
        self.available = False
        self._value = None

    def set_result(self, result: OptionResult | None):
        if result:
            self._value = result['value']
            self.args.set_result(result['args'])
            self.available = True


class SubcommandStub(BaseStub[Subcommand]):
    """
    子命令存根
    """
    args: ArgsStub
    dest: str
    options: list[OptionStub]
    name: str

    def __init__(self, subcommand: Subcommand):
        self.args = ArgsStub(subcommand.args)
        self.options = [OptionStub(option) for option in subcommand.options]
        self.name = subcommand.name.lstrip('-')
        self.available = False
        self._value = None
        self.dest = subcommand.dest
        self._origin = subcommand

    def set_result(self, result: SubcommandResult):
        self._value = result['value']
        self.args.set_result(result['args'])
        for option in self.options:
            option.set_result(result['options'].get(option.dest, None))
        self.available = True

    def option(self, name: str) -> OptionStub:
        return next(opt for opt in self.options if opt.name == name)
