"""Alconna 参数相关"""
from __future__ import annotations

import enum
from dataclasses import fields, is_dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Literal,
    Protocol,
    Type,
    TypeVar,
    Union,
    final,
    overload,
    runtime_checkable,
)
from typing_extensions import TypeAlias

from nepattern import BasePattern, MatchFailed, MatchMode, parser
from tarina import generic_isinstance, lang


@final
class _UNSET_TYPE(enum.Enum):
    _UNSET = "<UNSET>"

    def __repr__(self) -> str:
        return "<UNSET>"

    def __str__(self) -> str:
        return self.__repr__()

    def __bool__(self) -> Literal[False]:
        return False

    def __copy__(self):
        return self._UNSET

    def __deepcopy__(self, memo: dict[int, Any]):
        return self._UNSET


UNSET = _UNSET_TYPE._UNSET

_T = TypeVar("_T")

Unset: TypeAlias = Union[_T, Literal[_UNSET_TYPE._UNSET]]


DataUnit = TypeVar("DataUnit", covariant=True)


@runtime_checkable
class DataCollection(Protocol[DataUnit]):
    """数据集合协议"""
    def __repr__(self) -> str: ...
    def __iter__(self) -> Iterator[DataUnit]: ...
    def __len__(self) -> int: ...


TDC = TypeVar("TDC", bound=DataCollection[Any])
T = TypeVar("T")
T1 = TypeVar("T1")
TAValue: TypeAlias = Union[BasePattern[T, Any, Any], Type[T], T, Callable[..., T], Dict[Any, T], List[T]]


@final
class _AllParamPattern(BasePattern[T, T, Literal[MatchMode.KEEP]], Generic[T]):
    def __init__(self, types: tuple[type[T1], ...] = (), ignore: bool = True):
        self.types = types
        self.ignore = ignore
        super().__init__(mode=MatchMode.KEEP, origin=Any, alias="*")

    def match(self, input_: Any) -> Any:  # pragma: no cover
        if not self.types:
            return input_
        if generic_isinstance(input_, self.types):  # type: ignore
            return input_
        raise MatchFailed(
            lang.require("nepattern", "type_error").format(
                type=input_.__class__.__name__, target=input_, expected=" | ".join(map(lambda t: t.__name__, self.types))
            )
        )

    @overload
    def __call__(self, *, ignore: bool = True) -> _AllParamPattern[Any]: ...

    @overload
    def __call__(self, *types: type[T1], ignore: bool = True) -> _AllParamPattern[T1]: ...

    def __call__(self, *types: type[T1], ignore: bool = True) -> _AllParamPattern[T1]:
        return _AllParamPattern(types, ignore)

    def __calc_eq__(self, other):  # pragma: no cover
        return other.__class__ is _AllParamPattern


AllParam: _AllParamPattern[Any] = _AllParamPattern()


class KeyWordVar(BasePattern[T, Any, Literal[MatchMode.KEEP]]):
    """对具名参数的包装"""

    base: BasePattern

    def __init__(self, value: TAValue[T], sep: str = "="):
        """构建一个具名参数

        Args:
            value (type | BasePattern): 参数的值
            sep (str, optional): 参数的分隔符
        """
        self.base = value if isinstance(value, BasePattern) else parser(value)  # type: ignore
        self.sep = sep
        assert isinstance(self.base, BasePattern)
        super().__init__(mode=MatchMode.KEEP, origin=self.base.origin, alias=f"@{sep}{self.base}")

    def __repr__(self):
        return self.alias


class _Kw:
    __slots__ = ()

    def __getitem__(self, item: BasePattern[T, Any, Any] | type[T] | Any):
        return KeyWordVar(item)

    __matmul__ = __getitem__
    __rmatmul__ = __getitem__


class MultiVar(BasePattern[T, Any, Literal[MatchMode.KEEP]]):
    """对可变参数的包装"""

    base: BasePattern[T, Any, Any]
    flag: Literal["+", "*"]
    length: int

    def __init__(self, value: TAValue[T], flag: int | Literal["+", "*"] = "+"):
        """构建一个可变参数

        Args:
            value (type | BasePattern): 参数的值
            flag (int | Literal["+", "*"]): 参数的标记
        """
        self.base = value if isinstance(value, BasePattern) else parser(value)  # type: ignore
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
        super().__init__(mode=MatchMode.KEEP, origin=self.base.origin, alias=alias)

    def __repr__(self):
        return self.alias


class MultiKeyWordVar(MultiVar):
    base: KeyWordVar


Nargs = MultiVar
Kw = _Kw()


class KWBool(BasePattern):
    """对布尔参数的包装"""


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
        super().__init__(mode=MatchMode.KEEP, origin=dcls, alias=f"{dcls.__name__}")  # type: ignore


class _Up:
    __slots__ = ()

    def __mul__(self, other):
        return UnpackVar(other)


Up = _Up()


class _StrMulti(MultiVar[str]):
    pass


StrMulti = _StrMulti(str)
"""特殊参数, 用于匹配多个字符串, 并将结果通过 `str.join` 合并"""

StrMulti.alias = "str+"
StrMulti.refresh()
