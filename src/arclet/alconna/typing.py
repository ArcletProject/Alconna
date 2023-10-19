"""Alconna 参数相关"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Dict, Iterator, List, Literal, Protocol, Tuple, TypeVar, Union, runtime_checkable

from nepattern import BasePattern, MatchMode, type_parser

TPrefixes = Union[List[Union[str, object]], List[Tuple[object, str]]]
DataUnit = TypeVar("DataUnit", covariant=True)


@runtime_checkable
class DataCollection(Protocol[DataUnit]):
    """数据集合协议"""
    def __repr__(self) -> str: ...
    def __iter__(self) -> Iterator[DataUnit]: ...
    def __len__(self) -> int: ...


@dataclass(unsafe_hash=True)
class CommandMeta:
    """命令元数据"""

    description: str = field(default="Unknown")
    "命令的描述"
    usage: str | None = field(default=None)
    "命令的用法"
    example: str | None = field(default=None)
    "命令的使用样例"
    author: str | None = field(default=None)
    "命令的作者"
    fuzzy_match: bool = field(default=False)
    "命令是否开启模糊匹配"
    raise_exception: bool = field(default=False)
    "命令是否抛出异常"
    hide: bool = field(default=False)
    "命令是否对manager隐藏"
    keep_crlf: bool = field(default=False)
    "命令是否保留换行字符"
    compact: bool = field(default=False)
    "命令是否允许第一个参数紧随头部"
    extra: Dict[str, Any] = field(default_factory=dict, hash=False)
    "命令的自定义额外信息"


TDC = TypeVar("TDC", bound=DataCollection[Any])


class KeyWordVar(BasePattern):
    """对具名参数的包装"""

    base: BasePattern

    def __init__(self, value: BasePattern | Any, sep: str = "="):
        """构建一个具名参数

        Args:
            value (type | BasePattern): 参数的值
            sep (str, optional): 参数的分隔符
        """
        self.base = value if isinstance(value, BasePattern) else type_parser(value)
        self.sep = sep
        assert isinstance(self.base, BasePattern)
        super().__init__(model=MatchMode.KEEP, origin=self.base.origin, alias=f"@{sep}{self.base}")

    def __repr__(self):
        return self.alias


class _Kw:
    __slots__ = ()

    def __getitem__(self, item):
        return KeyWordVar(item)

    __matmul__ = __getitem__
    __rmatmul__ = __getitem__


class MultiVar(BasePattern):
    """对可变参数的包装"""

    base: BasePattern
    flag: Literal["+", "*"]
    length: int

    def __init__(self, value: BasePattern | Any, flag: int | Literal["+", "*"] = "+"):
        """构建一个可变参数

        Args:
            value (type | BasePattern): 参数的值
            flag (int | Literal["+", "*"]): 参数的标记
        """
        self.base = value if isinstance(value, BasePattern) else type_parser(value)
        assert isinstance(self.base, BasePattern)
        if not isinstance(flag, int):
            alias = f"({self.base}{flag})"
            self.flag = flag
            self.length = -1
        elif flag > 1:
            alias = f"({self.base}+)[:{flag}]"
            self.flag = "+"
            self.length = flag
        else:  # pragma: no cover
            alias = str(self.base)
            self.flag = "+"
            self.length = 1
        origin = Dict[str, self.base.origin] if isinstance(self.base, KeyWordVar) else Tuple[self.base.origin, ...]
        super().__init__(model=MatchMode.KEEP, origin=origin, alias=alias)

    def __repr__(self):
        return self.alias


Nargs = MultiVar
Kw = _Kw()


class KWBool(BasePattern):
    """对布尔参数的包装"""

    ...


class UnpackVar(BasePattern):
    """特殊参数，利用dataclass 的 field 生成 arg 信息，并返回dcls"""

    def __init__(self, dcls: Any, kw_only: bool = False, kw_sep: str = "="):
        """构建一个可变参数

        Args:
            dcls: dataclass 类
        """
        if not is_dataclass(dcls):
            raise TypeError(dcls)
        self.kw_only = kw_only
        self.kw_sep = kw_sep
        self.fields = fields(dcls)  # can override if other use Pydantic?
        super().__init__(model=MatchMode.KEEP, origin=dcls, alias=f"{dcls.__name__}")  # type: ignore


class _Up:
    __slots__ = ()

    def __mul__(self, other):
        return UnpackVar(other)


Up = _Up()
