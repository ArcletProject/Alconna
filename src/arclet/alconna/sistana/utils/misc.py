from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar, Union

if TYPE_CHECKING:

    def safe_extra_kw(
        match_args=True,
        kw_only=False,
        slots=False,
        weakref_slot=False,
    ) -> dict[str, bool]: ...
else:
    from inspect import Signature

    _available_dc_attrs = set(Signature.from_callable(dataclass).parameters.keys())

    def safe_extra_kw(**kwargs):
        return {k: v for k, v in kwargs.items() if k in _available_dc_attrs}


T = TypeVar("T")
E = TypeVar("E", bound=BaseException)


@contextmanager
def cvar(var: ContextVar[T], val: T):
    token = var.set(val)
    try:
        yield val
    finally:
        var.reset(token)


@dataclass
class Value(Generic[T]):
    value: T


Some = Union[Value[T], None]
