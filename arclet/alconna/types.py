"""Alconna 参数相关"""

import inspect
from typing import TypeVar, Union, Type, Dict, overload, Iterable, Generator, Tuple, Any
from .exceptions import InvalidParam


class _AnyParam:
    """单个参数的泛匹配"""
    def __repr__(self):
        return "AnyParam"


class _AnyAllParam(_AnyParam):
    """复数参数的泛匹配"""
    def __repr__(self):
        return "AllParam"


AnyParam = _AnyParam()
AllParam = _AnyAllParam()


class _ArgCheck:
    """对 Args 里参数类型的检查"""
    ip = r"(\d+)\.(\d+)\.(\d+)\.(\d+):?(\d*)"
    digit = r"(\-?\d+)"
    floating = r"(\-?\d+\.?\d*)"
    string = r"(.+)"
    url = r"(http[s]?://.+)"
    boolean = r"(True|False|true|false)"
    empty = inspect.Signature.empty

    check_list = {
        str: string,
        int: digit,
        float: floating,
        bool: boolean,
        Ellipsis: empty,
        "url": url,
        "ip": ip,
        "": AnyParam,
        "...": empty
    }

    def __init__(self, *args):
        raise NotImplementedError("_ArgCheck dose not support to init")

    def __new__(cls, *args):
        return cls.__arg_check__(args[0])

    @classmethod
    def __arg_check__(cls, item: Any) -> Union[str, empty]:
        """将一般数据类型转为 Args 使用的类型"""
        if cls.check_list.get(item):
            return cls.check_list.get(item)
        if item is None:
            return cls.empty
        return item


AnyStr = _ArgCheck.string
AnyDigit = _ArgCheck.digit
AnyIP = _ArgCheck.ip
AnyUrl = _ArgCheck.url
AnyFloat = _ArgCheck.floating
Bool = _ArgCheck.boolean
Empty = _ArgCheck.empty


NonTextElement = TypeVar("NonTextElement")
MessageChain = TypeVar("MessageChain")
TAValue = Union[str, Type[NonTextElement], _AnyParam]
TADefault = Union[str, NonTextElement, Empty]
TArgs = Dict[str, Union[TAValue, TADefault]]


class Args:
    """对命令参数的封装"""
    argument: Dict[str, TArgs]

    @overload
    def __init__(self, *args: Union[slice, tuple], **kwargs: ...):
        ...

    def __init__(self, *args: ..., **kwargs: TAValue):
        self.argument = {
            k: {"value": _ArgCheck(v), "default": None}
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

    def _check(self, args: Iterable[Union[slice, tuple]]):
        for sl in args:
            if isinstance(sl, slice):
                name, value, default = sl.start, sl.stop, sl.step
            else:
                name, value = sl[0], sl[1] if len(sl) > 1 else None
                default = sl[2] if len(sl) > 2 else None
            if not isinstance(name, str):
                raise InvalidParam("参数的名字只能是字符串")
            if name in ("name", "args", "alias"):
                raise InvalidParam("非法的参数名字")

            value = _ArgCheck(value)
            if value is Empty:
                raise InvalidParam("参数值不能为Empty")

            if isinstance(default, (bool, int)):
                default = str(default)
            default = _ArgCheck(default) if default else None
            self.argument.setdefault(name, {"value": value, "default": default})

    def params(self, sep: str = " "):
        """预处理参数的 help doc"""
        argument_string = ""
        i = 0
        length = len(self.argument)
        for k, v in self.argument.items():
            arg = f"<{k}"
            if isinstance(v['value'], _AnyParam):
                arg += ": WildMatch"
            elif not isinstance(v['value'], str):
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
            self.argument[key] = {"value": _ArgCheck(values[0]), "default": _ArgCheck(values[1])}
        else:
            self.argument[key] = {"value": _ArgCheck(value), "default": None}
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
                raise InvalidParam("参数的名字只能是字符串")
            self.argument[values[0]] = {"value": _ArgCheck(values[1]), "default": _ArgCheck(values[2])} if len(
                values) > 2 \
                else {"value": _ArgCheck(values[1]), "default": None}
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
