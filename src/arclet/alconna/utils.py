"""Alconna 参数相关"""
from __future__ import annotations

import enum
import sys
from typing import (
    Any,
    Callable,
    Dict,
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

from nepattern import Pattern, MatchFailed
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
TAValue: TypeAlias = Union[Pattern[T], Type[T], T, Callable[..., T], Dict[Any, T], List[T]]


class KWBool(Pattern):
    """对布尔参数的包装"""


def parent_frame_namespace(*, parent_depth: int = 2, force: bool = False) -> dict[str, Any] | None:
    """We allow use of items in parent namespace to get around the issue with `get_type_hints` only looking in the
    global module namespace. See https://github.com/pydantic/pydantic/issues/2678#issuecomment-1008139014 -> Scope
    and suggestion at the end of the next comment by @gvanrossum.

    WARNING 1: it matters exactly where this is called. By default, this function will build a namespace from the
    parent of where it is called.

    WARNING 2: this only looks in the parent namespace, not other parents since (AFAIK) there's no way to collect a
    dict of exactly what's in scope. Using `f_back` would work sometimes but would be very wrong and confusing in many
    other cases. See https://discuss.python.org/t/is-there-a-way-to-access-parent-nested-namespaces/20659.

    There are some cases where we want to force fetching the parent namespace, ex: during a `model_rebuild` call.
    In this case, we want both the namespace of the class' module, if applicable, and the parent namespace of the
    module where the rebuild is called.

    In other cases, like during initial schema build, if a class is defined at the top module level, we don't need to
    fetch that module's namespace, because the class' __module__ attribute can be used to access the parent namespace.
    This is done in `_typing_extra.get_module_ns_of`. Thus, there's no need to cache the parent frame namespace in this case.
    """
    frame = sys._getframe(parent_depth)

    # note, we don't copy frame.f_locals here (or during the last return call), because we don't expect the namespace to be modified down the line
    # if this becomes a problem, we could implement some sort of frozen mapping structure to enforce this
    if force:
        return frame.f_locals

    # if either of the following conditions are true, the class is defined at the top module level
    # to better understand why we need both of these checks, see
    # https://github.com/pydantic/pydantic/pull/10113#discussion_r1714981531
    if frame.f_back is None or frame.f_code.co_name == '<module>':
        return None

    return frame.f_locals


def get_module_ns_of(obj: Any) -> dict[str, Any]:
    """Get the namespace of the module where the object is defined.

    Caution: this function does not return a copy of the module namespace, so it should not be mutated.
    The burden of enforcing this is on the caller.
    """
    module_name = getattr(obj, '__module__', None)
    if module_name:
        try:
            return sys.modules[module_name].__dict__
        except KeyError:
            return {}
    return {}


def merge_cls_and_parent_ns(cls: type[Any], parent_namespace: dict[str, Any] | None = None) -> dict[str, Any]:
    ns = get_module_ns_of(cls).copy()
    if parent_namespace is not None:
        ns.update(parent_namespace)
    ns[cls.__name__] = cls
    return ns


def levenshtein(source: str, target: str) -> float:
    """`编辑距离算法`_, 计算源字符串与目标字符串的相似度, 取值范围[0, 1], 值越大越相似

    Args:
        source (str): 源字符串
        target (str): 目标字符串

    .. _编辑距离算法:
        https://en.wikipedia.org/wiki/Levenshtein_distance

    """
    l_s, l_t = len(source), len(target)
    s_range, t_range = range(l_s + 1), range(l_t + 1)
    matrix = [[(i if j == 0 else j) for j in t_range] for i in s_range]

    for i in s_range[1:]:
        for j in t_range[1:]:
            sub_distance = matrix[i - 1][j - 1] + (0 if source[i - 1] == target[j - 1] else 1)
            matrix[i][j] = min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1, sub_distance)

    return 1 - float(matrix[l_s][l_t]) / max(l_s, l_t)
