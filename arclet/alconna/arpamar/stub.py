from inspect import isclass
from typing import Dict, Any, List, TypeVar, Union, Type
from abc import ABCMeta, abstractmethod

from ..base import Args, ArgPattern, _AnyParam
from ..component import Option, Subcommand

T = TypeVar('T')


class BaseStub(metaclass=ABCMeta):
    available: bool
    value: Any

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
    _args_result: Dict[str, Any]

    def __init__(self, args: Args):
        self._args = args
        for key, value in args.argument.items():
            if isinstance(value['value'], _AnyParam):
                self.__annotations__[key] = Any
            elif isinstance(value['value'], ArgPattern):
                self.__annotations__[key] = value['value'].origin_type
            else:
                self.__annotations__[key] = value['value']
            setattr(self, key, value['default'])
        self._args_result = {}
        self.available = False

    def set_result(self, result: Dict[str, Any]):
        self._args_result = result
        self.available = True

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

    def __getattr__(self, item):
        return self._args_result[item]

    def __getitem__(self, item):
        if isinstance(item, str):
            return self._args_result[item]
        elif isinstance(item, int):
            return list(self._args_result.values())[item]
        else:
            raise TypeError(f'{item} is not supported')


class OptionStub(BaseStub):
    args: ArgsStub
    alias: str
    name: str

    def __init__(self, option: Option):
        self.args = ArgsStub(option.args)
        self.alias = option.alias.lstrip('-')
        self.name = option.name.lstrip('-')
        self._option = option
        self.available = False
        self.value = None

    def set_result(self, result: Any):
        if isinstance(result, Dict):
            self.args.set_result(result)
        else:
            self.value = result
        self.available = True


class SubcommandStub(BaseStub):
    args: ArgsStub
    options: List[OptionStub]
    name: str

    def __init__(self, subcommand: Subcommand):
        self.args = ArgsStub(subcommand.args)
        self.options = [OptionStub(option) for option in subcommand.options]
        self.name = subcommand.name.lstrip('-')
        self.available = False
        self.value = None

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
