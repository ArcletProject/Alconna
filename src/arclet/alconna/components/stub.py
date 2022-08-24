from inspect import isclass
from typing import Dict, Any, List, TypeVar, Union, Type, Generic
from abc import ABCMeta, abstractmethod
from nepattern import BasePattern, AllParam

from ..args import Args
from ..base import Option, Subcommand, OptionResult, SubcommandResult
from ..config import config

T = TypeVar('T')
T_Origin = TypeVar('T_Origin')


class BaseStub(Generic[T_Origin], metaclass=ABCMeta):
    """
    基础的命令组件存根
    """

    available: bool
    value: Any
    _origin: T_Origin

    __ignore__ = ['available', 'value', '_origin', 'origin', '__ignore__']

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
    value: Dict[str, Any]

    def __init__(self, args: Args):
        self._origin = args
        self.value = {}
        for key, value in args.argument.items():
            if value['value'] is AllParam:
                self.__annotations__[key] = Any
            elif isinstance(value['value'], BasePattern):
                self.__annotations__[key] = value['value'].origin
            else:
                self.__annotations__[key] = value['value']
            setattr(self, key, value['default'])
        self.available = False

    def set_result(self, result: Dict[str, Any]):
        if result:
            self.value = result
            self.available = True

    @property
    def first_arg(self) -> Any:
        return self.__getitem__(0)

    def get(self, item: Union[str, Type[T]], default=None) -> Union[T, Any]:
        if isinstance(item, str):
            return self.value.get(item, default)
        for k, v in self.__annotations__.items():
            if isclass(item):
                if v == item:
                    return self.value.get(k, default)
            elif isinstance(item, v):
                return self.value.get(k, default)
        return default

    def __contains__(self, item):
        return item in self.value

    def __iter__(self):
        return iter(self.value)

    def __len__(self):
        return len(self.value)

    def __getattribute__(self, item):
        if item in super(ArgsStub, self).__getattribute__('__ignore__'):
            return super().__getattribute__(item)
        if item in super().__getattribute__('value'):
            return super().__getattribute__('value').get(item, None)
        return super().__getattribute__(item)

    def __getitem__(self, item):
        if isinstance(item, str):
            return self.value[item]
        elif isinstance(item, int):
            return list(self.value.values())[item]
        else:
            raise TypeError(config.lang.stub_key_error.format(target=item))


class OptionStub(BaseStub[Option]):
    """
    选项存根
    """
    args: ArgsStub
    dest: str
    aliases: List[str]
    name: str

    def __init__(self, option: Option):
        self.args = ArgsStub(option.args)
        self.aliases = [alias.lstrip('-') for alias in option.aliases]
        self.name = option.name.lstrip('-')
        self.dest = option.dest
        self._origin = option
        self.available = False
        self.value = None

    def set_result(self, result: Union[OptionResult, None]):
        if result:
            self.value = result['value']
            self.args.set_result(result['args'])
            self.available = True


class SubcommandStub(BaseStub[Subcommand]):
    """
    子命令存根
    """
    args: ArgsStub
    dest: str
    options: List[OptionStub]
    name: str

    def __init__(self, subcommand: Subcommand):
        self.args = ArgsStub(subcommand.args)
        self.options = [OptionStub(option) for option in subcommand.options]
        self.name = subcommand.name.lstrip('-')
        self.available = False
        self.value = None
        self.dest = subcommand.dest
        self._origin = subcommand

    def set_result(self, result: SubcommandResult):
        self.value = result['value']
        self.args.set_result(result['args'])
        for option in self.options:
            option.set_result(result['options'].get(option.dest, None))
        self.available = True

    def option(self, name: str) -> OptionStub:
        return next(opt for opt in self.options if opt.name == name)
