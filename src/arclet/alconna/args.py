from __future__ import annotations

import dataclasses as dc
import inspect
import re
import sys
from enum import Enum
from functools import partial
from typing import Any, Callable, Generic, Iterable, List, Sequence, Type, TypeVar, Union, cast
from typing_extensions import Self, TypeAlias

from nepattern import ANY, NONE, AntiPattern, BasePattern, MatchMode, RawStr, UnionPattern, parser
from tarina import Empty, get_signature, lang

from .exceptions import InvalidArgs
from .typing import AllParam, KeyWordVar, KWBool, MultiKeyWordVar, MultiVar, UnpackVar


def safe_dcls_kw(**kwargs):
    if sys.version_info < (3, 10):  # pragma: no cover
        kwargs.pop("slots")
    return kwargs


_T = TypeVar("_T")
TAValue: TypeAlias = Union[BasePattern[_T, Any, Any], Type[_T], str]


class ArgFlag(str, Enum):
    """标识参数单元的特殊属性"""

    OPTIONAL = "?"
    HIDDEN = "/"
    ANTI = "!"


@dc.dataclass(**safe_dcls_kw(slots=True))
class Field(Generic[_T]):
    """标识参数单元字段"""

    default: _T | type[Empty] = dc.field(default=Empty)
    """参数单元的默认值"""
    alias: str | None = dc.field(default=None)
    """参数单元默认值的别名"""
    completion: Callable[[], str | list[str] | None] | None = dc.field(default=None)
    """参数单元的补全"""
    unmatch_tips: Callable[[Any], str] | None = dc.field(default=None)
    """参数单元的错误提示"""
    missing_tips: Callable[[], str] | None = dc.field(default=None)
    """参数单元的缺失提示"""

    @property
    def display(self):
        """返回参数单元的显示值"""
        return self.alias or self.default

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


@dc.dataclass(**safe_dcls_kw(init=False, eq=True, unsafe_hash=True, slots=True))
class Arg(Generic[_T]):
    """参数单元"""

    name: str = dc.field(compare=True, hash=True)
    """参数单元的名称"""
    value: BasePattern[_T, Any, Any] = dc.field(compare=False, hash=True)
    """参数单元的值"""
    field: Field[_T] = dc.field(compare=False, hash=False)
    """参数单元的字段"""
    notice: str | None = dc.field(compare=False, hash=False)
    """参数单元的注释"""
    flag: set[ArgFlag] = dc.field(compare=False, hash=False)
    """参数单元的标识"""
    separators: tuple[str, ...] = dc.field(compare=False, hash=False)
    """参数单元使用的分隔符"""
    optional: bool = dc.field(compare=False, hash=False)
    hidden: bool = dc.field(compare=False, hash=False)

    def __init__(
        self,
        name: str,
        value: TAValue[_T] | None = None,
        field: Field[_T] | _T | type[Empty] = Empty,
        seps: str | Iterable[str] = " ",
        notice: str | None = None,
        flags: list[ArgFlag] | None = None,
    ):
        """构造参数单元

        Args:
            name (str): 参数单元的名称
            value (TAValue[_T], optional): 参数单元的值. Defaults to None.
            field (Field[_T], optional): 参数单元的字段. Defaults to Empty.
            seps (str | Iterable[str], optional): 参数单元使用的分隔符. Defaults to " ".
            notice (str, optional): 参数单元的注释. Defaults to None.
            flags (list[ArgFlag], optional): 参数单元的标识. Defaults to None.
        """
        if not isinstance(name, str) or name.startswith("$"):
            raise InvalidArgs(lang.require("args", "name_error"))
        if not name.strip():
            raise InvalidArgs(lang.require("args", "name_empty"))
        self.name = name
        _value = parser(value or RawStr(name))
        default = field if isinstance(field, Field) else Field(field)
        if isinstance(_value, UnionPattern) and _value.optional:
            default.default = None if default.default is Empty else default.default  # type: ignore
        if _value == NONE:
            raise InvalidArgs(lang.require("args", "value_error").format(target=name))
        self.value = _value  # type: ignore
        self.field = default
        self.notice = notice
        self.separators = (seps,) if isinstance(seps, str) else tuple(seps)
        flags = flags or []
        if res := re.match(r"^(?P<name>.+?)#(?P<notice>[^;?!/#]+)", name):
            self.notice = res["notice"]
            self.name = res["name"]
        if res := re.match(r"^(?P<name>.+?)(;)?(?P<flag>[?!/]+)", self.name):
            flags.extend(ArgFlag(c) for c in res["flag"])
            self.name = res["name"]
        self.flag = set(flags)
        self.optional = ArgFlag.OPTIONAL in self.flag
        self.hidden = ArgFlag.HIDDEN in self.flag
        if ArgFlag.ANTI in self.flag and self.value not in (ANY, AllParam):
            self.value = AntiPattern(self.value)  # type: ignore

    def __repr__(self):
        n, v = f"'{self.name}'", str(self.value)
        return (n if n == v else f"{n}: {v}") + (f" = '{self.field.display}'" if self.field.display is not Empty else "")

    def __add__(self, other) -> "Args":
        if isinstance(other, Arg):
            return Args(self, other)
        raise TypeError(f"unsupported operand type(s) for +: 'Arg' and '{other.__class__.__name__}'")


class ArgsMeta(type):
    """`Args` 类的元类"""

    def __getattr__(self, name: str):
        return type("_S", (), {"__getitem__": partial(self.__class__.__getitem__, self, key=name), "__call__": None})()

    def __getitem__(self, item: Union[Arg, tuple[Arg, ...], str, tuple[Any, ...]], key: str | None = None):
        """构造参数集合

        Args:
            item (Union[Arg, tuple[Arg, ...], str, Any]): 参数单元或参数单元组或构建参数单元的值
            key (str, optional): 参数单元的名称. Defaults to None.

        Returns:
            Args: 参数集合
        """
        data: tuple[Arg, ...] | tuple[Any, ...] = item if isinstance(item, tuple) else (item,)
        if isinstance(data[0], Arg):
            return self(*data)
        return self(Arg(key, *data)) if key else self(Arg(*data))  # type: ignore


NULL = {Empty: None, None: Empty}


class _argument(List[Arg[Any]]):
    __slots__ = ("unpack", "vars_positional", "vars_keyword", "keyword_only", "normal")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.normal: list[Arg[Any]] = []
        self.keyword_only: dict[str, Arg[Any]] = {}
        self.vars_positional: list[tuple[MultiVar, Arg[Any]]] = []
        self.vars_keyword: list[tuple[MultiKeyWordVar, Arg[Any]]] = []
        self.unpack: tuple[Arg, Args] | None = None


def gen_unpack(var: UnpackVar):
    unpack = Args()
    for field in var.fields:
        if field.default != dc.MISSING:
            _de = field.default
        elif field.default_factory != dc.MISSING:
            _de = field.default_factory()
        else:
            _de = Empty
        _type = field.type
        if getattr(field, "kw_only", None) or var.kw_only:
            _type = KeyWordVar(_type, sep=var.kw_sep)
        unpack.add(field.name, value=_type, default=_de)
    var.alias = f"{var.alias}{'()' if unpack.empty else f'{unpack}'[4:]}"
    return unpack


class Args(metaclass=ArgsMeta):
    """参数集合

    用于代表命令节点需求的一系列参数

    一般而言, 使用特殊方法 `__getitem__` 来构造参数集合, 例如:

        >>> Args["name", str]["age", int]
        Args('name': str, 'age': int)

    也可以使用特殊方法 `__getattr__` 来构造参数集合, 例如:

        >>> Args.name[str]
        Args('name': str)
    """

    argument: _argument

    @classmethod
    def from_callable(cls, target: Callable, kw_sep: str = "=") -> tuple[Args, bool]:
        """从可调用函数中构造Args

        Args:
            target (Callable): 目标函数
            kw_sep (str, optional): 关键字参数的分隔符. Defaults to "=".

        Returns:
            tuple[Args, bool]: 参数集合, 是否为方法
        """
        _args = cls()
        method = False
        for param in get_signature(target):
            name = param.name
            if name in ["self", "cls"]:
                method = True
                continue
            anno = param.annotation
            de = param.default
            if anno == inspect.Signature.empty:
                anno = type(de) if de not in {Empty, None} else ANY
            if param.kind == param.KEYWORD_ONLY:
                if anno == bool:
                    anno = KWBool(f"(?:-*no)?-*{name}", MatchMode.REGEX_CONVERT, bool, lambda _, x: not x[0].lstrip("-").startswith('no'))  # noqa: E501
                anno = KeyWordVar(anno, sep=kw_sep)
            if param.kind == param.VAR_POSITIONAL:
                anno = MultiVar(anno, "*")
            if param.kind == param.VAR_KEYWORD:
                anno = MultiKeyWordVar(KeyWordVar(anno), "*")
            _args.add(name, value=anno, default=de)
        return _args, method

    def __init__(self, *args: Arg[Any], separators: str | Iterable[str] | None = None):
        """
        构造一个 `Args`

        Args:
            *args (Arg): 参数单元
            separators (str | Iterable[str] | None, optional): 可选的为所有参数单元指定分隔符
        """
        self._visit = set()
        self.optional_count = 0
        self.argument = _argument(args)
        self.__check_vars__()
        if separators is not None:
            self.separate(*((separators,) if isinstance(separators, str) else tuple(separators)))

    __slots__ = "argument", "optional_count", "_visit"

    def add(self, name: str, *, value: TAValue[Any], default: Any = Empty, flags: list[ArgFlag] | None = None) -> Self:
        """添加一个参数

        Args:
            name (str): 参数名称
            value (TAValue): 参数值
            default (Any, optional): 参数默认值.
            flags (list[ArgFlag] | None, optional): 参数标记.

        Returns:
            Self: 参数集合自身
        """
        if next(filter(lambda x: x.name == name, self.argument), False):
            return self
        self.argument.append(Arg(name, value, default, flags=flags))
        self.__check_vars__()
        return self

    def separate(self, *separator: str) -> Self:
        """设置参数的分隔符

        Args:
            *separator (str): 分隔符

        Returns:
            Self: 参数集合自身
        """
        for arg in self.argument:
            arg.separators = separator
        return self

    def __check_vars__(self):
        """检查当前所有参数单元

        Raises:
            InvalidParam: 当检查到参数单元不符合要求时
        """
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
            if isinstance(arg.value, UnpackVar):
                if len(self._visit) > 1:
                    raise InvalidArgs("Unpack var can only put in the first position")
                if len(self.argument) > 1:
                    raise InvalidArgs("Args can only contain one arg if using Unpack var")
                _gen_unpack = getattr(arg.value, "unpack", gen_unpack)
                self.argument.unpack = (arg, _gen_unpack(arg.value))
                break
            if isinstance(arg.value, MultiVar):
                if isinstance(arg.value.base, KeyWordVar):
                    for slot in self.argument.vars_positional:
                        _, a = slot
                        if arg.value.base.sep in a.separators:
                            raise InvalidArgs("varkey cannot use the same sep as varpos's Arg")
                    self.argument.vars_keyword.append((cast(MultiKeyWordVar, arg.value), arg))
                elif self.argument.keyword_only:
                    raise InvalidArgs(lang.require("args", "exclude_mutable_args"))
                else:
                    self.argument.vars_positional.append((arg.value, arg))
            elif isinstance(arg.value, KeyWordVar):
                if self.argument.vars_keyword:
                    raise InvalidArgs(lang.require("args", "exclude_mutable_args"))
                self.argument.keyword_only[arg.name] = arg
            else:
                self.argument.normal.append(arg)
                if arg.optional:
                    if self.argument.vars_keyword or self.argument.vars_positional:
                        raise InvalidArgs(lang.require("args", "exclude_mutable_args"))
                    self.optional_count += 1
                elif arg.field.default is not Empty:
                    self.optional_count += 1
        self.argument.clear()
        self.argument.extend(_tmp)
        del _tmp
        del _visit

    def __len__(self):
        return len(self.argument)

    def __getitem__(self, item: Union[Arg, tuple[Arg, ...], str, tuple[Any, ...]]) -> Self | Arg:
        """获取或添加一个参数单元

        Args:
            item (Union[Arg, tuple[Arg, ...], str, Any]): 参数单元或参数单元名称或参数单元值

        Returns:
            Self | Arg: 参数集合自身或需要的参数单元
        """
        if res := next((x for x in self.argument if x.name == item), None):
            return res
        data: tuple[Arg, ...] | tuple[Any, ...] = item if isinstance(item, tuple) else (item,)
        if isinstance(data[0], Arg):
            self.argument.extend(data)  # type: ignore
        else:
            self.argument.append(Arg(*data))  # type: ignore
        self.__check_vars__()
        return self

    def __merge__(self, other: Args | Arg | Sequence | None) -> Self:
        """合并另一个参数集合

        Args:
            other (Args | Arg | Sequence): 另一个参数集合

        Returns:
            Self: 参数集合自身
        """
        if isinstance(other, Args):
            self.argument.extend(other.argument)
            self.__check_vars__()
            self.argument.keyword_only.update(other.argument.keyword_only)
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

    def __iter__(self):
        return iter(self.argument)

    def __truediv__(self, other) -> Self:
        self.separate(*other if isinstance(other, (list, tuple, set)) else other)
        return self

    def __eq__(self, other):
        return self.argument == other.argument

    def __repr__(self):
        return f"Args({', '.join([f'{arg}' for arg in self.argument])})" if self.argument else "Empty"

    @property
    def empty(self) -> bool:
        """判断当前参数集合是否为空"""
        return not self.argument
