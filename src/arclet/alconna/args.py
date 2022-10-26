import re
import inspect
from functools import partial
from copy import deepcopy
from enum import Enum
from contextlib import suppress
from typing import Union, Tuple, Dict, Iterable, Callable, Any, Optional, Sequence, List, Literal, TypedDict
from dataclasses import dataclass, field
from nepattern import BasePattern, Empty, AllParam, AnyOne, UnionArg, type_parser, pattern_map

from .config import config
from .exceptions import InvalidParam, NullMessage
from .typing import MultiArg

TAValue = Union[BasePattern, AllParam.__class__, type]


class ArgFlag(str, Enum):
    """参数标记"""
    VAR_POSITIONAL_MORE = "+"
    VAR_KEYWORD_MORE = "++"
    VAR_POSITIONAL = "*"
    VAR_KEYWORD = "**"
    OPTIONAL = 'O'
    KWONLY = '@'
    HIDDEN = "H"
    FORCE = "F"
    ANTI = "!"


@dataclass
class ArgField:
    """标识参数单元字段"""
    default: Any = field(default=None)
    default_factory: Callable[[], Any] = field(default=lambda: None)
    alias: Optional[str] = field(default=None)
    completion: Optional[Callable[[], Union[str, List[str]]]] = field(default=None)

    @property
    def display(self):
        return self.alias or self.default

    @property
    def default_gen(self):
        return self.default if self.default is not None else self.default_factory()


class ArgUnit(TypedDict):
    """参数单元 """
    value: TAValue
    """参数值"""
    field: ArgField
    """默认值"""
    notice: Optional[str]
    """参数提示"""
    optional: bool
    """是否可选"""
    kwonly: bool
    """是否键值对参数"""
    hidden: bool
    """是否隐藏类型参数"""


class ArgsMeta(type):
    """Args 类的元类"""

    def __getattr__(self, name):
        class _Seminal:
            __class_getitem__ = partial(self.__class__.__getitem__, self, key=name)

        return _Seminal

    def __getitem__(self, item, key: Optional[str] = None):
        if isinstance(item, slice) or isinstance(item, tuple) and list(filter(lambda x: isinstance(x, slice), item)):
            raise InvalidParam(f"{self.__name__} 现在不支持切片; 应从 Args[a:b:c, x:y:z] 变为 Args[a,b,c][x,y,z]")
        if not isinstance(item, tuple):
            return self(args=[(key, item)]) if key else self(args=[(str(item), item)])
        arg = list(filter(lambda x: not isinstance(x, slice), item))
        if key:
            return self(args=[(key, *arg[:2])])
        return self(args=[arg[:3]])


class Args(metaclass=ArgsMeta):  # type: ignore
    """
    对命令参数的封装

    Attributes:
        argument: 存放参数内容的容器
    """
    extra: Literal["allow", "ignore", "reject"]
    argument: Dict[str, ArgUnit]
    var_positional: Optional[str]
    var_keyword: Optional[str]
    keyword_only: List[str]
    optional_count: int
    separators: Tuple[str, ...]

    @classmethod
    def from_string_list(cls, args: List[List[str]], custom_types: Dict) -> "Args":
        """
        从处理好的字符串列表中生成Args

        Args:
            args: 字符串列表
            custom_types: 自定义的类型

        Examples:
            >>> Args.from_string_list([["foo", "str"], ["bar", "digit", "123"]], {"digit":int})
        """
        _args = cls()
        for arg in args:
            if (_le := len(arg)) == 0:
                raise NullMessage

            default = arg[2].strip(" ") if _le > 2 else None
            value = AllParam if arg[0].startswith("...") else (
                AnyOne if arg[0].startswith("..") else (arg[1].strip(" ") if _le > 1 else arg[0].lstrip(".-"))
            )
            name = arg[0].replace("...", "").replace("..", "")

            if value not in (AllParam, AnyOne):
                if custom_types and custom_types.get(value) and not inspect.isclass(custom_types[value]):
                    raise InvalidParam(config.lang.common_custom_type_error.format(target=custom_types[value]))
                with suppress(NameError, ValueError, TypeError):
                    if pattern_map.get(value, None):
                        value = pattern_map[value]
                        if default:
                            default = value.origin(default)
                    else:
                        value = eval(value, custom_types)  # type: ignore
                        if default:
                            default = value(default)
            _args.add_argument(name, value=value, default=default)
        return _args

    @classmethod
    def from_callable(cls, target: Callable, extra: Literal["allow", "ignore", "reject"] = "allow"):
        """
        从可调用函数中构造Args

        Args:
            target: 可调用函数
            extra: 额外类型检查的策略

        Examples:
            >>> def test(a: str, b: int, c: float = 0.0, *, d: str, e: int = 0, f: float = 0.0):
            ...     pass
            >>> Args.from_callable(test)

        """
        sig = inspect.signature(target)
        _args = cls(extra=extra)
        method = False
        for param in sig.parameters.values():
            name = param.name
            if name in ["self", "cls"]:
                method = True
                continue
            anno = param.annotation
            de = param.default
            if anno == inspect.Signature.empty:
                anno = type(de) if de not in (inspect.Signature.empty, None) else AnyOne
            if de is inspect.Signature.empty:
                de = None
            elif de is None:
                de = inspect.Signature.empty
            if param.kind == param.KEYWORD_ONLY:
                if anno == bool:
                    anno = BasePattern(f"(?:-*no)?-*{name}", 3, bool, lambda _, x: not x.lstrip("-").startswith('no'))
                else:
                    _args.add_argument(f"${name}_key", value=f"-*{name}")
                _args.keyword_only.append(name)
            if param.kind == param.VAR_POSITIONAL:
                name += ";S"
            if param.kind == param.VAR_KEYWORD:
                name += ";W"
            _args.add_argument(name, value=anno, default=de)
        return _args, method

    def __init__(
            self,
            args: Optional[Iterable[Sequence]] = None,
            extra: Literal["allow", "ignore", "reject"] = "allow",
            separators: Union[str, Iterable[str]] = " ",
            **kwargs: TAValue
    ):
        """
        构造一个Args

        Args:
            args: 应传入 slice|tuple, 代表key、value、default
            extra: 额外类型检查的策略
            separator: 参数分隔符
            kwargs: 其他参数
        """
        self.extra = extra
        self.var_positional = None
        self.var_keyword = None
        self.keyword_only = []
        self.optional_count = 0
        self.separators = (separators, ) if isinstance(separators, str) else tuple(separators)
        self.argument = {}
        for arg in (args or []):
            self.__check_var__(arg)
        self.argument.update({  # type: ignore
            k: {"value": type_parser(v), "field": ArgField(), 'notice': None,
                'optional': False, 'hidden': False, 'kwonly': False}
            for k, v in kwargs.items()
        })

    __slots__ = "extra", "var_positional", "var_keyword", "argument", "optional_count", "separators", "keyword_only"

    def add_argument(self, name: str, *, value: Any, default: Any = None, flags: Optional[Iterable[ArgFlag]] = None):
        """
        添加一个参数
        """
        if name in self.argument:
            return self
        if flags:
            name += ";" + "".join(flags)
        self.__check_var__([name, value, default])
        return self

    def default(self, **kwargs):
        """设置参数的默认值"""
        for k, v in kwargs.items():
            if self.argument.get(k):
                self.argument[k]['field'] = v if isinstance(v, ArgField) else ArgField(v)
        return self

    def separate(self, *separator: str):
        """设置参数的分隔符"""
        self.separators = separator
        return self

    def __check_var__(self, val: Sequence):
        if not val:
            raise InvalidParam(config.lang.args_name_empty)
        if len(val) > 2:
            name, value, default = val[0], val[1], val[2] if isinstance(val[2], ArgField) else ArgField(val[2])
        elif len(val) > 1:
            name, value, default = (
                val[0], val[0], val[1]
            ) if isinstance(val[1], ArgField) else (
                val[0], val[1], ArgField()
            )
        else:
            name, value, default = val[0], val[0], ArgField()
        if not isinstance(name, str):
            raise InvalidParam(config.lang.args_name_error)
        name: str
        default: ArgField
        if not name.strip():
            raise InvalidParam(config.lang.args_name_empty)
        _value = type_parser(value, self.extra)
        if isinstance(_value, UnionArg) and _value.optional:
            default.default = Empty if default.default is None else default.default
        if default.default in ("...", Ellipsis):
            default.default = Empty
        if _value is Empty:
            raise InvalidParam(config.lang.args_value_error.format(target=name))
        slot: ArgUnit = {
            'value': _value, 'field': default, 'notice': None,
            'optional': False, 'hidden': False, 'kwonly': False
        }
        if res := re.match(r"^.+?#(?P<notice>[^;#|]+)", name):
            slot['notice'] = res["notice"]
            name = name.replace(f"#{res['notice']}", "")
        if res := re.match(r"^.+?;(?P<flag>[^;#]+)", name):
            flags = res["flag"]
            name = name.replace(f";{res['flag']}", "")
            _limit = False
            for flag in flags.split('|'):
                if flag == ArgFlag.FORCE and not _limit:
                    self.__handle_force__(slot, value)
                    _limit = True
                if flag == ArgFlag.ANTI and not _limit:
                    if slot['value'] not in (AnyOne, AllParam):
                        slot['value'] = deepcopy(_value).reverse()  # type: ignore
                    _limit = True
                if flag == ArgFlag.VAR_KEYWORD and not _limit:
                    if self.var_keyword:
                        raise InvalidParam(config.lang.args_duplicate_kwargs)
                    if _value is not AllParam:
                        slot['value'] = MultiArg(_value, flag='kwargs')  # type: ignore
                        self.var_keyword = name
                    _limit = True
                if flag == ArgFlag.VAR_POSITIONAL and not _limit:
                    if self.var_positional:
                        raise InvalidParam(config.lang.args_duplicate_varargs)
                    if _value is not AllParam:
                        slot['value'] = MultiArg(_value)  # type: ignore
                        self.var_positional = name
                if flag.isdigit() and not _limit:
                    if self.var_positional:
                        raise InvalidParam(config.lang.args_duplicate_varargs)
                    if _value is not AllParam:
                        slot['value'] = MultiArg(_value, length=int(flag))  # type: ignore
                        self.var_positional = name
                if flag == ArgFlag.OPTIONAL:
                    if self.var_keyword or self.var_positional:
                        raise InvalidParam(config.lang.args_exclude_mutable_args)
                    slot['optional'] = True
                    self.optional_count += 1
                if flag == ArgFlag.HIDDEN:
                    slot['hidden'] = True
                if flag == ArgFlag.KWONLY:
                    if self.var_keyword or self.var_positional:
                        raise InvalidParam(config.lang.args_exclude_mutable_args)
                    slot['kwonly'] = True
        self.argument[name] = slot

    @staticmethod
    def __handle_force__(slot: ArgUnit, value):
        slot['value'] = (BasePattern(value, alias=f"\'{value}\'") if isinstance(value, str) else BasePattern.of(value))

    def __len__(self):
        return len(self.argument)

    def __setitem__(self, key, value):
        return self.__setattr__(key, value)

    def __setattr__(self, key, value):
        if key in self.__slots__:
            super().__setattr__(key, value)
        elif isinstance(value, Sequence):
            values = list(value)
            self.__check_var__([key, values[0], values[1]])
        else:
            self.__check_var__([key, value])
        return self

    def __getitem__(self, item) -> Union["Args", Tuple[TAValue, ArgField]]:
        if isinstance(item, str) and self.argument.get(item):
            return self.argument[item]['value'], self.argument[item]['field']
        if isinstance(item, slice) or isinstance(item, tuple) and list(filter(lambda x: isinstance(x, slice), item)):
            raise InvalidParam(f"{self.__class__.__name__} 现在不支持切片; 应从 Args[a:b:c, x:y:z] 变为 Args[a,b,c][x,y,z]")
        if not isinstance(item, tuple):
            self.__check_var__([str(item), item])
        else:
            arg = list(filter(lambda x: not isinstance(x, slice), item))
            self.__check_var__(arg[:3])
        return self

    def __merge__(self, other) -> "Args":
        if isinstance(other, Args):
            self.argument.update(other.argument)
            del other
        elif isinstance(other, Sequence):
            self.__check_var__(other)
        return self

    def __add__(self, other) -> "Args":
        return self.__merge__(other)

    def __iadd__(self, other) -> "Args":
        return self.__merge__(other)

    def __lshift__(self, other) -> "Args":
        return self.__merge__(other)

    def __truediv__(self, other):
        self.separate(*other if isinstance(other, (list, tuple, set)) else other)
        return self

    def __eq__(self, other):
        return self.argument == other.argument

    def __repr__(self):
        if not self.argument:
            return "Empty"
        repr_string = "Args({0})"
        repr_args = ", ".join(
            (n if (n := f"'{name}'") == (v := str(arg['value'])) else f"{n}: {v}") + (
                f" = '{arg['field'].display}'" if arg['field'].display is not None else ""
            )
            for name, arg in self.argument.items()
        )
        return repr_string.format(repr_args)

    @property
    def empty(self) -> bool:
        return not self.argument
