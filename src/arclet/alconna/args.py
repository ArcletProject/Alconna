from __future__ import annotations

import dataclasses as dc
import inspect
import re
from enum import Enum
from functools import partial
from typing import Any, Callable, Generic, Iterable, List, Sequence, TypeVar, Union, cast, overload
from typing_extensions import Self, dataclass_transform, ParamSpec, Concatenate

from nepattern import ANY, NONE, AntiPattern, BasePattern, MatchMode, RawStr, UnionPattern, parser
from tarina import Empty, get_signature, lang

from ._dcls import safe_dcls_kw
from .exceptions import InvalidArgs
from .typing import AllParam, KeyWordVar, KWBool, MultiKeyWordVar, MultiVar, TAValue

_T = TypeVar("_T")


@dc.dataclass(**safe_dcls_kw(slots=True))
class Field(Generic[_T]):
    """标识参数单元字段"""

    default: _T | type[Empty] = dc.field(default=Empty)
    """参数单元的默认值"""
    default_factory: Callable[[], _T] | type[Empty] = dc.field(default=Empty)
    """参数单元的默认值工厂"""
    alias: str | None = dc.field(default=None)
    """参数单元默认值的别名"""
    completion: Callable[[], str | list[str] | None] | None = dc.field(default=None, repr=False)
    """参数单元的补全"""
    unmatch_tips: Callable[[Any], str] | None = dc.field(default=None, repr=False)
    """参数单元的错误提示"""
    missing_tips: Callable[[], str] | None = dc.field(default=None, repr=False)
    """参数单元的缺失提示"""
    notice: str | None = dc.field(default=None, compare=False, hash=False)
    """参数单元的注释"""
    seps: str = dc.field(default=" ", compare=False, hash=False)
    """参数单元使用的分隔符"""
    optional: bool = dc.field(default=False, compare=False, hash=False)
    hidden: bool = dc.field(default=False, compare=False, hash=False)
    kw_only: bool = dc.field(default=False, compare=False, hash=False)

    @property
    def display(self):
        """返回参数单元的显示值"""
        return self.alias or self.get_default()

    def get_default(self):
        """返回参数单元的默认值"""
        return self.default_factory() if self.default_factory is not Empty else self.default

    def get_completion(self):
        """返回参数单元的补全"""
        return self.completion() if self.completion else None

    def get_unmatch_tips(self, value: Any, fallback: str):
        """返回参数单元的错误提示"""
        if not self.unmatch_tips:
            return fallback
        gen = self.unmatch_tips(value)
        return gen or fallback

    def get_missing_tips(self, fallback: str):
        """返回参数单元的缺失提示"""
        if not self.missing_tips:
            return fallback
        gen = self.missing_tips()
        return gen or fallback


def arg_field(
    default: Any | type[Empty] = Empty,
    *,
    default_factory: Any | type[Empty] = Empty,
    init: bool = True,
    alias: str | None = None,
    completion: Callable[[], str | list[str] | None] | None = None,
    unmatch_tips: Callable[[Any], str] | None = None,
    missing_tips: Callable[[], str] | None = None,
    notice: str | None = None,
    seps: str = " ",
    kw_only: bool = False,
    optional: bool = False,
    hidden: bool = False,
) -> "Any":
    return Field(default, default_factory, alias, completion, unmatch_tips, missing_tips, notice, seps, optional, hidden, kw_only)


@dc.dataclass(**safe_dcls_kw(init=False, eq=True, unsafe_hash=True, slots=True))
class Arg(Generic[_T]):
    """参数单元"""

    name: str = dc.field(compare=True, hash=True)
    """参数单元的名称"""
    type_: BasePattern[_T, Any, Any] = dc.field(compare=False, hash=True)
    """参数单元的类型"""
    field: Field[_T] = dc.field(compare=False, hash=False)
    """参数单元的字段"""

    def __init__(
        self,
        name: str,
        type_: TAValue[_T] | None = None,
        field: Field[_T] | _T | type[Empty] = Empty,
    ):
        if not isinstance(name, str) or name.startswith("$"):
            raise InvalidArgs(lang.require("args", "name_error"))
        if not name.strip():
            raise InvalidArgs(lang.require("args", "name_empty"))
        self.name = name
        _value = parser(type_ or RawStr(name))
        default = field if isinstance(field, Field) else Field(field)
        if isinstance(_value, UnionPattern) and _value.optional:
            default.default = None if default.default is Empty else default.default  # type: ignore
        if _value == NONE:
            raise InvalidArgs(lang.require("args", "value_error").format(target=name))
        self.value = _value  # type: ignore
        self.field = default

        if res := re.match(r"^(?P<name>.+?)#(?P<notice>[^;?/#]+)", name):
            self.field.notice = res["notice"]
            self.name = res["name"]
        if res := re.match(r"^(?P<name>.+?)(;)?(?P<flag>[?/]+)", self.name):
            if "?" in res["flag"]:
                self.field.optional = True
            if "/" in res["flag"]:
                self.field.hidden = True
            self.name = res["name"]

    def __str__(self):
        n, v = f"'{self.name}'", str(self.value)
        return (n if n == v else f"{n}: {v}") + (f" = '{self.field.display}'" if self.field.display is not Empty else "")

    def __add__(self, other) -> "ArgsBuilder":
        if isinstance(other, Arg):
            return ArgsBuilder() << self << other
        raise TypeError(f"unsupported operand type(s) for +: 'Arg' and '{other.__class__.__name__}'")


class _Args:
    __slots__ = ("unpack", "vars_positional", "vars_keyword", "keyword_only", "normal", "data", "_visit", "optional_count")

    def __init__(self, args: list[Arg[Any]]):
        self.data = args
        self.normal: list[Arg[Any]] = []
        self.keyword_only: dict[str, Arg[Any]] = {}
        self.vars_positional: list[tuple[MultiVar, Arg[Any]]] = []
        self.vars_keyword: list[tuple[MultiKeyWordVar, Arg[Any]]] = []
        self._visit = set()
        self.optional_count = 0
        self.__check_vars__()

    def __check_vars__(self):
        """检查当前所有参数单元

        Raises:
            InvalidParam: 当检查到参数单元不符合要求时
        """
        _tmp = []
        _visit = set()
        for arg in self.data:
            if arg.name in _visit:
                continue
            _tmp.append(arg)
            _visit.add(arg.name)
            if arg.name in self._visit:
                continue
            self._visit.add(arg.name)
            if isinstance(arg.value, MultiVar):
                if isinstance(arg.value.base, KeyWordVar):
                    for slot in self.vars_positional:
                        _, a = slot
                        if arg.value.base.sep in a.field.seps:
                            raise InvalidArgs("varkey cannot use the same sep as varpos's Arg")
                    self.vars_keyword.append((cast(MultiKeyWordVar, arg.value), arg))
                elif self.keyword_only:
                    raise InvalidArgs(lang.require("args", "exclude_mutable_args"))
                else:
                    self.vars_positional.append((arg.value, arg))
            elif isinstance(arg.value, KeyWordVar):
                if self.vars_keyword:
                    raise InvalidArgs(lang.require("args", "exclude_mutable_args"))
                self.keyword_only[arg.name] = arg
            else:
                self.normal.append(arg)
            if arg.field.optional:
                self.optional_count += 1
            elif arg.field.default is not Empty:
                self.optional_count += 1
        self.data.clear()
        self.data.extend(_tmp)
        del _tmp
        del _visit


_P = ParamSpec("_P")


def _arg_init_wrapper(func: Callable[Concatenate[str, _P], Arg[Any]]) -> Callable[[str, ArgsBuilder], Callable[_P, ArgsBuilder]]:
    return lambda name, builder: lambda *args, **kwargs: builder.__lshift__(func(name, *args, **kwargs))


class ArgsBuilder:
    def __init__(self):
        self._args = []

    def __lshift__(self, arg: Arg):
        self._args.append(arg)
        return self

    def __getattr__(self, item: str):
        return _arg_init_wrapper(Arg)(item, self)

    def build(self):
        return _Args(self._args)


@dataclass_transform(kw_only_default=True, field_specifiers=(arg_field,))
class ArgsMeta(type):
    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        *,
        merge: bool = False,
        **kwargs,
    ):
        return super().__new__(cls, name, bases, namespace, **kwargs)

    def __getattr__(self, item: str):
        return ArgsBuilder().__getattr__(item)


class ArgsBase(metaclass=ArgsMeta):
    def __init__(self, **kwargs):
        ...


class Foo(ArgsBase):
    foo: str = arg_field()
    bar: int
