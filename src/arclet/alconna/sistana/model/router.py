from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from .pointer import Pointer


T = TypeVar("T")


@dataclass
class Router(Generic[T]):
    endpoint_handlers: dict[Pointer, Any] = field(default_factory=dict)
