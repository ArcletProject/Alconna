from __future__ import annotations

from dataclasses import is_dataclass, fields
from typing import (
    Any,
    Literal,
    TypeVar,
)
from typing_extensions import deprecated

from nepattern import Pattern, parser

from arclet.alconna.utils import TAValue
from arclet.alconna.utils import KWBool as KWBool

T = TypeVar("T")


@deprecated("KeyWordVar is deprecated, use `Field(kw_only=True)` instead", category=DeprecationWarning, stacklevel=1)
class KeyWordVar(Pattern[T]):
    """对具名参数的包装"""

    base: Pattern[T]

    def __init__(self, value: TAValue[T], sep: str = "="):
        """构建一个具名参数

        Args:
            value (type | BasePattern): 参数的值
            sep (str, optional): 参数的分隔符
        """
        self.base = value if isinstance(value, Pattern) else parser(value)  # type: ignore
        self.sep = sep
        assert isinstance(self.base, Pattern)
        super().__init__(origin=self.base.origin, alias=f"@{sep}{self.base}")

    def __repr__(self):
        return self.alias


class _Kw:
    __slots__ = ()

    def __getitem__(self, item: Pattern[T] | type[T] | Any):
        return KeyWordVar(item)

    __matmul__ = __getitem__
    __rmatmul__ = __getitem__


@deprecated("MultiVar is deprecated, use `Field(multiple=...)` instead", category=DeprecationWarning, stacklevel=1)
class MultiVar(Pattern[T]):
    """对可变参数的包装"""

    base: Pattern[T]
    flag: Literal["+", "*"]
    length: int

    def __init__(self, value: TAValue[T], flag: int | Literal["+", "*"] = "+"):
        """构建一个可变参数

        Args:
            value (type | BasePattern): 参数的值
            flag (int | Literal["+", "*"]): 参数的标记
        """
        self.base = value if isinstance(value, Pattern) else parser(value)  # type: ignore
        assert isinstance(self.base, Pattern)
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
        super().__init__(origin=self.base.origin, alias=alias)

    def __repr__(self):
        return self.alias


Nargs = MultiVar
Kw = _Kw()


@deprecated("UnpackVar is deprecated, use `ArgsBase` instead", category=DeprecationWarning, stacklevel=1)
class UnpackVar(Pattern):
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
        super().__init__(mode=MatchMode.KEEP, origin=dcls, alias=f"{dcls.__name__}")  # type: ignore


class _Up:
    __slots__ = ()

    def __mul__(self, other):
        return UnpackVar(other)


Up = _Up()


@deprecated("StrMulti is deprecated, use `Field(multiple=str)` instead", stacklevel=1)
class _StrMulti(MultiVar[str]):
    pass


StrMulti = _StrMulti(str)
"""特殊参数, 用于匹配多个字符串, 并将结果通过 `str.join` 合并"""

StrMulti.alias = "str+"
