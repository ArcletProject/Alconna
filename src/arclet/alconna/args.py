from __future__ import annotations

import re
from functools import partial
from copy import deepcopy
from enum import Enum
from contextlib import suppress
from typing import Union, Iterable, Callable, Any, Sequence, TypeVar, Generic
from typing_extensions import get_origin, Self
from dataclasses import dataclass, field as dc_field
from nepattern import BasePattern, Empty, AllParam, AnyOne, UnionPattern, type_parser, pattern_map
from .util import _safe_dcs_args
from .config import config
from .exceptions import InvalidParam, NullMessage
from .typing import MultiVar, KeyWordVar

_T = TypeVar("_T")
TAValue = Union[BasePattern, AllParam.__class__, type, str]


class ArgFlag(str, Enum):
    OPTIONAL = '?'
    HIDDEN = "/"
    ANTI = "!"


@dataclass(**_safe_dcs_args(slots=True))
class Field(Generic[_T]):
    """标识参数单元字段"""
    default: _T = dc_field(default=None)
    default_factory: Callable[[], _T] = dc_field(default=lambda: None)
    alias: str | None = dc_field(default=None)
    completion: Callable[[], str | list[str]] | None = dc_field(default=None)

    @property
    def display(self):
        return self.alias or self.default_gen

    @property
    def default_gen(self) -> _T:
        return self.default if self.default is not None else self.default_factory()


@dataclass(**_safe_dcs_args(init=False, eq=True, unsafe_hash=True, slots=True))
class Arg:
    name: str = dc_field(compare=True, hash=True)
    value: TAValue = dc_field(compare=False, hash=True)
    field: Field[_T] = dc_field(compare=False, hash=False)
    notice: str | None = dc_field(compare=False, hash=False)
    flag: set[ArgFlag] = dc_field(compare=False, hash=False)
    separators: tuple[str, ...] = dc_field(compare=False, hash=False)

    def __init__(
        self,
        name: str,
        value: TAValue | None = None,
        field: Field[_T] | _T | None = None,
        seps: str | Iterable[str] = " ",
        notice: str | None = None,
        flags: list[ArgFlag] | None = None,
    ):
        if not isinstance(name, str) or name.startswith('$'):
            raise InvalidParam(config.lang.args_name_error)
        if not name.strip():
            raise InvalidParam(config.lang.args_name_empty)
        self.name = name
        _value = type_parser(value or name)
        default = field if isinstance(field, Field) else Field(field)
        if isinstance(_value, UnionPattern) and _value.optional:
            default.default = Empty if default.default is None else default.default
        if default.default == "...":
            default.default = Empty
        if _value is Empty:
            raise InvalidParam(config.lang.args_value_error.format(target=name))
        self.value = _value
        self.field = default
        self.notice = notice
        self.separators = (seps,) if isinstance(seps, str) else tuple(seps)
        flags = flags or []
        if res := re.match(r"^.+?#(?P<notice>[^;?!/#]+)", name):
            self.notice = res["notice"]
            self.name = name.replace(f"#{res['notice']}", "")
        if res := re.match(r"^.+?;(?P<flag>[?!/]+)", self.name):
            flags.extend(ArgFlag(c) for c in res["flag"])
            self.name = self.name.replace(f";{res['flag']}", "")
        self.flag = set(flags)

    def __repr__(self):
        return (n if (n := f"'{self.name}'") == (v := str(self.value)) else f"{n}: {v}") + (
            f" = '{self.field.display}'" if self.field.display is not None else ""
        )

    @property
    def optional(self):
        return ArgFlag.OPTIONAL in self.flag

    @property
    def hidden(self):
        return ArgFlag.HIDDEN in self.flag


class ArgsMeta(type):
    """Args 类的元类"""

    def __getattr__(self, name):
        return type("_S", (), {"__getitem__": partial(self.__class__.__getitem__, self, key=name), "__call__": None})()

    def __getitem__(self, item, key: str | None = None):
        data = item if isinstance(item, tuple) else (item,)
        if isinstance(data[0], Arg):
            return self(*data)
        return self(Arg(key, *data)) if key else self(Arg(*data))


class Args(metaclass=ArgsMeta):  # type: ignore
    argument: list[Arg]
    var_positional: str | None
    var_keyword: str | None
    keyword_only: list[str]
    optional_count: int

    @classmethod
    def from_string_list(cls, args: list[list[str]], custom_types: dict[str, type]) -> Args:
        """
        从处理好的字符串列表中生成Args

        Examples:
            >>> Args.from_string_list([["foo", "str"], ["bar", "digit", "123"]], {"digit":int})
        """
        _args = cls()
        for arg in args:
            if (_le := len(arg)) == 0:
                raise NullMessage
            default = arg[2].strip(" ") if _le > 2 else None
            name = arg[0].strip(" ")
            value = AllParam if name.startswith("...") else (
                AnyOne if name.startswith("..") else (arg[1].strip(" ") if _le > 1 else name.lstrip(".-"))
            )
            name = name.replace("...", "").replace("..", "")
            _multi, _kw, _slice = "", False, -1
            if value not in (AllParam, AnyOne):
                if mat := re.match(r"^(?P<name>.+?)(?P<multi>[+*]+)(\[)?(?P<slice>\d*)(])?$", value):
                    value = mat["name"]
                    _multi = mat["multi"][0]
                    _kw = len(mat["multi"]) > 1
                    _slice = int(mat["slice"] or -1)
                with suppress(NameError, ValueError, TypeError):
                    value = pattern_map.get(value, None) or type_parser(eval(value, custom_types))  # type: ignore
                    default = (get_origin(value.origin) or value.origin)(default) if default else default
                if _multi:
                    value = MultiVar(KeyWordVar(value) if _kw else value, _slice if _slice > 1 else _multi)
            _args.add(name, value=value, default=default)
        return _args

    def __init__(
        self,
        *args: Arg,
        separators: str | Iterable[str] | None = None,
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
        self._visit = set()
        self.var_positional = None
        self.var_keyword = None
        self.keyword_only = []
        self.optional_count = 0
        self.argument = list(args)
        self.argument.extend(Arg(k, type_parser(v), Field()) for k, v in kwargs.items())
        self.__check_vars__()
        if separators is not None:
            self.separate(*((separators,) if isinstance(separators, str) else tuple(separators)))

    __slots__ = "var_positional", "var_keyword", "argument", "optional_count", "keyword_only", "_visit"

    def add(self, name: str, *, value: Any, default: Any = None, flags: list[ArgFlag] | None = None) -> Self:
        """添加一个参数"""
        if next(filter(lambda x: x.name == name, self.argument), False):
            return self
        self.argument.append(Arg(name, value, default, flags=flags))
        self.__check_vars__()
        return self

    def default(self, **kwargs) -> Self:
        """设置参数的默认值"""
        for arg in self.argument:
            if v := (kwargs.get(arg.name)):
                if isinstance(v, Field):
                    arg.field = v
                else:
                    arg.field.default = v
        return self

    def separate(self, *separator: str) -> Self:
        """设置参数的分隔符"""
        for arg in self.argument:
            arg.separators = separator
        return self

    def __check_vars__(self):
        _tmp = []
        _visit = set()
        for arg in self.argument:
            if arg.name in _visit:
                continue
            _tmp.append(arg)
            _visit.add(arg.name)
            if arg.name in self._visit:
                continue
            self._visit.add(arg.name)
            _limit = False
            if ArgFlag.ANTI in arg.flag and arg.value not in (AnyOne, AllParam):
                arg.value = deepcopy(arg.value).reverse()
            if isinstance(arg.value, MultiVar) and not _limit:
                if isinstance(arg.value.base, KeyWordVar):
                    if self.var_keyword:
                        raise InvalidParam(config.lang.args_duplicate_kwargs)
                    self.var_keyword = arg.name
                elif self.var_positional:
                    raise InvalidParam(config.lang.args_duplicate_varargs)
                else:
                    self.var_positional = arg.name
                _limit = True
            if isinstance(arg.value, KeyWordVar):
                if self.var_keyword or self.var_positional:
                    raise InvalidParam(config.lang.args_exclude_mutable_args)
                self.keyword_only.append(arg.name)
                if arg.value.sep in arg.separators:
                    _tmp.insert(-1, Arg(f"_key_{arg.name}", value=f"-*{arg.name}"))
                    _tmp[-1].value = arg.value.base
            if ArgFlag.OPTIONAL in arg.flag:
                if self.var_keyword or self.var_positional:
                    raise InvalidParam(config.lang.args_exclude_mutable_args)
                self.optional_count += 1
        self.argument.clear()
        self.argument.extend(_tmp)
        del _tmp
        del _visit

    def __len__(self):
        return len(self.argument)

    def __getitem__(self, item) -> Self | Arg:
        if isinstance(item, str) and (res := next(filter(lambda x: x.name == item, self.argument), None)):
            return res
        data = item if isinstance(item, tuple) else (item,)
        if isinstance(data[0], Arg):
            self.argument.extend(data)
        else:
            self.argument.append(Arg(*data))
        self.__check_vars__()
        return self

    def __merge__(self, other) -> Self:
        if isinstance(other, Args):
            self.argument.extend(other.argument)
            self.__check_vars__()
            del other
        elif isinstance(other, Arg):
            self.argument.append(other)
            self.__check_vars__()
        elif isinstance(other, Sequence):
            self.__getitem__(tuple(other))
        return self

    __add__ = __merge__
    __iadd__ = __merge__
    __lshift__ = __merge__

    def __truediv__(self, other) -> Self:
        self.separate(*other if isinstance(other, (list, tuple, set)) else other)
        return self

    def __eq__(self, other):
        return self.argument == other.argument

    def __repr__(self):
        return (
            f"Args({', '.join([f'{arg}' for arg in self.argument if not arg.name.startswith('_key_')])})"
            if self.argument else "Empty"
        )

    @property
    def empty(self) -> bool:
        return not self.argument
