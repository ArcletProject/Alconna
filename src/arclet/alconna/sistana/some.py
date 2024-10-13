from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar, Union

T = TypeVar("T")
E = TypeVar("E", bound=BaseException)


@dataclass
class Value(Generic[T]):
    value: T


Some = Union[Value[T], None]
