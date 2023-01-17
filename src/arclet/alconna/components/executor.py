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
    binding: Callable[..., Arparma | None] = field(default=lambda: None, repr=False)

    @property
    def result(self) -> T:
        if not self.binding:
            raise ExecuteFailed(None)
        arp = self.binding()
        if not arp or not arp.matched:
            raise ExecuteFailed('Unmatched')
        try:
            return arp.call(self.target)
        except Exception as e:
            raise ExecuteFailed(e) from e
