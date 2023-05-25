from __future__ import annotations

import dataclasses as dc
import inspect
import re
import sys
from copy import deepcopy
from enum import Enum
from functools import partial
from typing import Any, Callable, Generic, Iterable, Sequence, TypeVar, Union

from nepattern import AllParam, AnyOne, BasePattern, RawStr, UnionPattern, all_patterns, type_parser
from tarina import Empty, get_signature, lang
from typing_extensions import Self

from .exceptions import InvalidParam
from .typing import KeyWordVar, MultiVar


def safe_dcls_kw(**kwargs):
    if sys.version_info < (3, 10):  # pragma: no cover
        kwargs.pop('slots')
    return kwargs


_T = TypeVar("_T")
TAValue = Union[BasePattern, AllParam.__class__, type, str]
STRING = all_patterns()[str]


class ArgFlag(str, Enum):
    """标识参数单元的特殊属性"""
    OPTIONAL = '?'
    HIDDEN = "/"
    ANTI = "!"


@dc.dataclass(**safe_dcls_kw(slots=True))
class Field(Generic[_T]):
    """标识参数单元字段"""

    default: _T | None = dc.field(default=None)
    """参数单元的默认值"""
    alias: str | None = dc.field(default=None)
    """参数单元默认值的别名"""
    completion: Callable[[], str | list[str]] | None = dc.field(default=None)
    """参数单元的补全"""

    @property
    def display(self):
        """返回参数单元的显示值"""
        return self.alias or self.default


@dc.dataclass(**safe_dcls_kw(init=False, eq=True, unsafe_hash=True, slots=True))
class Arg:
    """参数单元"""

    name: str = dc.field(compare=True, hash=True)
    """参数单元的名称"""
    value: BasePattern = dc.field(compare=False, hash=True)
    """参数单元的值"""
    field: Field[Any] = dc.field(compare=False, hash=False)
    """参数单元的字段"""
    notice: str | None = dc.field(compare=False, hash=False)
    """参数单元的注释"""
    flag: set[ArgFlag] = dc.field(compare=False, hash=False)
    """参数单元的标识"""
    separators: tuple[str, ...] = dc.field(compare=False, hash=False)
    """参数单元使用的分隔符"""
    optional: bool = dc.field(compare=False, hash=False)
    hidden: bool = dc.field(compare=False, hash=False)
    anonymous: bool = dc.field(compare=False, hash=False)

    def __init__(
        self,
        name: str,
        value: TAValue | None = None,
        field: Field[_T] | _T | None = None,
        seps: str | Iterable[str] = " ",
        notice: str | None = None,
        flags: list[ArgFlag] | None = None,
    ):
        """构造参数单元

        Args:
            name (str): 参数单元的名称
            value (TAValue, optional): 参数单元的值. Defaults to None.
            field (Field[_T], optional): 参数单元的字段. Defaults to None.
            seps (str | Iterable[str], optional): 参数单元使用的分隔符. Defaults to " ".
            notice (str, optional): 参数单元的注释. Defaults to None.
            flags (list[ArgFlag], optional): 参数单元的标识. Defaults to None.
        """
        if not isinstance(name, str) or name.startswith('$'):
            raise InvalidParam(lang.require("args", "name_error"))
        if not name.strip():
            raise InvalidParam(lang.require("args", "name_empty"))
        self.name = name
        _value = type_parser(value or RawStr(name))
        default = field if isinstance(field, Field) else Field(field)
        if isinstance(_value, UnionPattern) and _value.optional:
            default.default = Empty if default.default is None else default.default
        if default.default == "...":
            default.default = Empty
        if _value is Empty:
            raise InvalidParam(lang.require("args", "value_error").format(target=name))
        self.value = _value
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
        self.anonymous = self.name.startswith("_key_")
        if ArgFlag.ANTI in self.flag and self.value not in (AnyOne, AllParam):
            self.value = deepcopy(self.value).reverse()

    def __repr__(self):
        n, v = f"'{self.name}'", str(self.value)
        return (n if n == v else f"{n}: {v}") + (f" = '{self.field.display}'" if self.field.display is not None else "")


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
    argument: list[Arg]
    """参数单元组"""
    var_positional: MultiVar | None
    """可变参数"""
    var_keyword: MultiVar | None
    """可变关键字参数"""
    keyword_only: list[str]
    """仅关键字参数的名称"""
    optional_count: int
    """可选参数的数量"""

    @classmethod
    def from_callable(cls, target: Callable) -> tuple[Args, bool]:
        """从可调用函数中构造Args

        Args:
            target (Callable): 目标函数

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
            NULL = {Empty: None, None: Empty}
            if anno == inspect.Signature.empty:
                anno = type(de) if de not in NULL else AnyOne
            de = NULL.get(de, de)
            if param.kind == param.KEYWORD_ONLY:
                if anno == bool:
                    anno = BasePattern(f"(?:-*no)?-*{name}", 3, bool, lambda _, x: not x.lstrip("-").startswith('no'))
                    _args.keyword_only.append(name)
                else:
                    anno = KeyWordVar(anno, sep=' ')
            if param.kind == param.VAR_POSITIONAL:
                anno = MultiVar(anno, "*")
            if param.kind == param.VAR_KEYWORD:
                anno = MultiVar(KeyWordVar(anno), "*")
            _args.add(name, value=anno, default=de)
        return _args, method

    def __init__(self, *args: Arg, separators: str | Iterable[str] | None = None, **kwargs: TAValue):
        """
        构造一个 `Args`

        Args:
            *args (Arg): 参数单元
            separators (str | Iterable[str] | None, optional): 可选的为所有参数单元指定分隔符
            **kwargs (TAValue): 剩余的参数单元值
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

    def add(self, name: str, *, value: TAValue, default: Any = None, flags: list[ArgFlag] | None = None) -> Self:
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

    def default(self, **kwargs) -> Self:
        """设置参数的默认值

        Args:
            **kwargs: 参数名称与默认值的映射

        Returns:
            Self: 参数集合自身
        """
        for arg in self.argument:
            if v := (kwargs.get(arg.name)):
                if isinstance(v, Field):
                    arg.field = v
                else:
                    arg.field.default = v
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
            if isinstance(arg.value, MultiVar):
                if isinstance(arg.value.base, KeyWordVar):
                    if self.var_keyword:
                        raise InvalidParam(lang.require("args", "duplicate_kwargs"))
                    self.var_keyword = arg.value
                elif self.var_positional:
                    raise InvalidParam(lang.require("args", "duplicate_varargs"))
                else:
                    self.var_positional = arg.value
            if isinstance(arg.value, KeyWordVar):
                if self.var_keyword or self.var_positional:
                    raise InvalidParam(lang.require("args", "exclude_mutable_args"))
                self.keyword_only.append(arg.name)
                if arg.value.sep in arg.separators:
                    _tmp.insert(-1, Arg(f"_key_{arg.name}", value=f"-*{arg.name}"))
                    _tmp[-1].value = arg.value.base
            if arg.optional:
                if self.var_keyword or self.var_positional:
                    raise InvalidParam(lang.require("args", "exclude_mutable_args"))
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
        if isinstance(item, str) and (res := next(filter(lambda x: x.name == item, self.argument), None)):
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
            self.keyword_only = list(set(self.keyword_only + other.keyword_only))
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
    __iter__ = lambda self: iter(self.argument)

    def __truediv__(self, other) -> Self:
        self.separate(*other if isinstance(other, (list, tuple, set)) else other)
        return self

    def __eq__(self, other):
        return self.argument == other.argument

    def __repr__(self):
        return (
            f"Args({', '.join([f'{arg}' for arg in self.argument if not arg.anonymous])})"
            if self.argument else "Empty"
        )

    @property
    def empty(self) -> bool:
        """判断当前参数集合是否为空"""
        return not self.argument
