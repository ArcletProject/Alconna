from typing import Callable, TypeVar, Generic, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

from ..exceptions import ExecuteFailed
if TYPE_CHECKING:
    from ..arpamar import Arpamar

T = TypeVar("T")


@dataclass(unsafe_hash=True)
class ArpamarExecutor(Generic[T]):
    target: Callable[..., T]
    binding: Callable[..., Optional['Arpamar']] = field(default=lambda: None, repr=False)

    @property
    def result(self) -> T:
        if not self.binding:
            raise ExecuteFailed(None)
        arp = self.binding()
        if not arp or not arp.matched:
            raise ExecuteFailed('Unmatched')
        try:
            return self.target(**arp.all_matched_args)
        except Exception as e:
            raise ExecuteFailed(e) from e
