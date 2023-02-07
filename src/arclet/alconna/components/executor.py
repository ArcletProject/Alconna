from __future__ import annotations

from typing import Callable, TypeVar, Generic, TYPE_CHECKING
from dataclasses import dataclass, field

from ..exceptions import ExecuteFailed
if TYPE_CHECKING:
    from ..arparma import Arparma

T = TypeVar("T")


@dataclass(init=True, unsafe_hash=True)
class ArparmaExecutor(Generic[T]):
    target: Callable[..., T]
    binding: Callable[..., list[Arparma]] = field(default=lambda: [], repr=False)

    @property
    def result(self) -> T:
        if not self.binding:
            raise ExecuteFailed(None)
        arps = self.binding()
        if not arps or not arps[-1].matched:
            raise ExecuteFailed('Unmatched')
        try:
            return arps[-1].call(self.target)
        except Exception as e:
            raise ExecuteFailed(e) from e
