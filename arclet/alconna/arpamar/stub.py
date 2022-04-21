from inspect import isclass
from typing import Dict, Any, List, TypeVar, Union, Type
from abc import ABCMeta, abstractmethod

from ..base import Args, ArgPattern, _AnyParam, Option, Subcommand
from ..lang_config import lang_config

T = TypeVar('T')


class BaseStub(metaclass=ABCMeta):
    """
    基础的命令组件存根
    """

    available: bool
    value: Any
    _origin: Any

    __ignore__ = ['available', 'value', '_origin', 'origin', '__ignore__']

    @abstractmethod
    def set_result(self, result: Any) -> None:
        """
        设置解析结果与可用性
        """

    def __repr__(self):
        return "{" + ", ".join(
            [
                "{}={}".format(k, v)
                for k, v in vars(self).items()
                if v and not k.startswith("_")
            ]
        ) + "}"


class ArgsStub(BaseStub):
    """
    参数存根
    """
    _args_result: Dict[str, Any]
    _origin: Args

    def __init__(self, args: Args):
        self._origin = args
        self._args_result = {}
        for key, value in args.argument.items():
            if isinstance(value['value'], _AnyParam):
                self.__annotations__[key] = Any
            elif isinstance(value['value'], ArgPattern):
                self.__annotations__[key] = value['value'].origin_type
            else:
                self.__annotations__[key] = value['value']
            setattr(self, key, value['default'])
        self.available = False

    def set_result(self, result: Dict[str, Any]):
        if result:
            self._args_result = result
            self.available = True

    @property
    def origin(self) -> Args:
        return self._origin

    @property
    def first_arg(self) -> Any:
        return self.__getitem__(0)

    def get(self, item: Union[str, Type[T]], default=None) -> Union[T, Any]:
        if isinstance(item, str):
            return self._args_result.get(item, default)
        else:
            for k, v in self.__annotations__.items():
                if isclass(item):
                    if v == Any:
                        return self._args_result.get(k, default)
                    elif v == item:
                        return self._args_result.get(k, default)
                elif isinstance(item, v):
                    return self._args_result.get(k, default)
            return default

    def __contains__(self, item):
        return item in self._args_result

    def __iter__(self):
        return iter(self._args_result)

    def __len__(self):
        return len(self._args_result)

    def __getattribute__(self, item):
        if item in super(ArgsStub, self).__getattribute__('__ignore__'):
            return super().__getattribute__(item)
        if item in super().__getattribute__('_args_result'):
            return self._args_result.get(item, None)
        return super().__getattribute__(item)

    def __getitem__(self, item):
        if isinstance(item, str):
            return self._args_result[item]
        elif isinstance(item, int):
            return list(self._args_result.values())[item]
        else:
            raise TypeError(lang_config.stub_key_error(target=item))


class OptionStub(BaseStub):
    """
    选项存根
    """
    args: ArgsStub
    aliases: List[str]
    name: str
    _origin: Option

    def __init__(self, option: Option):
        self.args = ArgsStub(option.args)
        self.aliases = [alias.lstrip('-') for alias in option.aliases]
        self.name = option.name.lstrip('-')
        self._origin = option
        self.available = False
        self.value = None

    def set_result(self, result: Any):
        if isinstance(result, Dict):
            self.args.set_result(result)
        else:
            self.value = result
        self.available = True

    @property
    def origin(self) -> Option:
        return self._origin


class SubcommandStub(BaseStub):
    """
    子命令存根
    """
    args: ArgsStub
    options: List[OptionStub]
    name: str
    _origin: Subcommand

    def __init__(self, subcommand: Subcommand):
        self.args = ArgsStub(subcommand.args)
        self.options = [OptionStub(option) for option in subcommand.options]
        self.name = subcommand.name.lstrip('-')
        self.available = False
        self.value = None
        self._origin = subcommand

    def set_result(self, result: Any):
        result = result.copy()
        if isinstance(result, Dict):
            keys = list(result.keys())
            for key in keys:
                for opt in self.options:
                    if opt.name == key:
                        opt.set_result(result.pop(key))
                        break
            self.args.set_result(result)
        else:
            self.value = result
        self.available = True

    def option(self, name: str) -> OptionStub:
        return next(opt for opt in self.options if opt.name == name)

    @property
    def origin(self) -> Subcommand:
        return self._origin
