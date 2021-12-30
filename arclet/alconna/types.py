"""Alconna 参数相关"""


import inspect
from typing import TypeVar, Union, Type, Dict, overload, Iterable, Generator, Tuple, Any, Optional
from .exceptions import InvalidName


class Pattern:
    """对 Args 里参数类型的简单封装"""
    ip = r"(\d+)\.(\d+)\.(\d+)\.(\d+)"
    digit = r"(\d+)"
    string = r"(.+)"
    url = r"(http[s]?://.+)"
    boolean = r"(True|False|true|false)"
    empty = inspect.Signature.empty

    def __init__(self, *args):
        raise NotImplementedError("Pattern dose not support to init")

    def __new__(cls, *args):
        return cls.compile(args[0])

    def __class_getitem__(cls, item):
        return cls.compile(item)

    @classmethod
    def compile(cls, item: Optional[Any] = None) -> Union[str, empty]:
        """将一般数据类型转为 Args 使用的类型"""
        if item is str:
            return cls.string
        if item is int:
            return cls.digit
        if item is bool:
            return cls.boolean
        if item is None or item is Ellipsis:
            return cls.empty
        if isinstance(item, str):
            if item.lower() == "url":
                return cls.url
            if item.lower() == "ip":
                return cls.ip
            return item
        return item


AnyStr = Pattern.string
AnyDigit = Pattern.digit
AnyIP = Pattern.ip
AnyUrl = Pattern.url
Bool = Pattern.boolean
Empty = Pattern.empty

NonTextElement = TypeVar("NonTextElement")
MessageChain = TypeVar("MessageChain")
TAValue = Union[str, Type[NonTextElement]]
TADefault = Union[str, NonTextElement, Empty]
TArgs = Dict[str, Union[TAValue, TADefault]]


class Args:
    """对命令参数的封装"""
    argument: Dict[str, TArgs]

    @overload
    def __init__(self, *args: slice, **kwargs: ...):
        ...

    def __init__(self, *args: ..., **kwargs: TAValue):
        self.argument = {
            k: {"value": Pattern(v), "default": None}
            for k, v in kwargs.items()
            if k not in ("name", "args", "alias")
        }
        self._check(args)

    def default(self, **kwargs: TADefault):
        """设置参数的默认值"""
        for k, v in kwargs.items():
            if self.argument.get(k):
                self.argument[k]['default'] = v
        return self

    def _check(self, args: Iterable[slice]):
        for sl in args:
            if isinstance(sl, slice):
                name, value, default = sl.start, sl.stop, sl.step
                if not isinstance(name, str):
                    raise InvalidName
                if name in ("name", "args", "alias"):
                    raise InvalidName
                if value is Empty:
                    raise InvalidName
                if value in (str, bool, int) or isinstance(value, str):
                    value = Pattern(value)
                if isinstance(default, (bool, int)):
                    default = str(default)
                default = Pattern(default)
                self.argument.setdefault(name, {"value": value, "default": default})

    def params(self, sep: str = " "):
        """预处理参数的 help doc"""
        argument_string = ""
        i = 0
        length = len(self.argument)
        for k, v in self.argument.items():
            arg = f"<{k}"
            if not isinstance(v['value'], str):
                arg += f": Type_{v['value'].__name__}"
            if v['default'] is Empty:
                arg += " default: Empty"
            elif v['default'] is not None:
                arg += f" default: {v['default']}"
            argument_string += arg + ">"
            i += 1
            if i != length:
                argument_string += sep
        return argument_string

    def __iter__(self) -> Generator[Tuple[str, TAValue, TADefault], Any, None]:
        for k, a in self.argument.items():
            yield k, a.get('value'), a.get('default')

    def __len__(self):
        return len(self.argument)

    def __setitem__(self, key, value):
        if isinstance(value, Iterable):
            values = list(value)
            self.argument[key] = {"value": values[0], "default": values[1]}
        else:
            self.argument[key] = {"value": value, "default": None}
        return self

    def __class_getitem__(cls, item) -> "Args":
        slices = list(item) if not isinstance(item, slice) else [item]
        return cls(*slices)

    def __getitem__(self, item) -> Union["Args", Tuple[TAValue, TADefault]]:
        if isinstance(item, str):
            return self.argument[item].get('value'), self.argument[item].get('default')
        self._check(item if not isinstance(item, slice) else [item])
        return self

    def __merge__(self, other) -> "Args":
        if isinstance(other, Args):
            self.argument.update(other.argument)
            del other
        elif isinstance(other, Iterable):
            values = list(other)
            if not isinstance(values[0], str):
                raise InvalidName
            self.argument[values[0]] = {"value": values[1], "default": values[2]} if len(values) > 2 \
                else {"value": values[1], "default": None}
        return self

    def __add__(self, other) -> "Args":
        return self.__merge__(other)

    def __lshift__(self, other) -> "Args":
        return self.__merge__(other)

    def __repr__(self):
        if not self.argument:
            return "Empty"
        repr_string = "Args({0})"
        repr_args = ", ".join(
            [
                f"'{name}': '{arg['value']}'" + (f" = '{arg['default']}'" if arg['default'] is not None else "")
                for name, arg in self.argument.items()
            ]
        )
        return repr_string.format(repr_args)
