"""Alconna 参数相关"""
from __future__ import annotations

import enum
import sys
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

from nepattern import BasePattern, MatchFailed, MatchMode
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


class KWBool(BasePattern):
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
