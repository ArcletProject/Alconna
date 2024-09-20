from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

from ..utils.misc import Some


T = TypeVar("T")

RxGet = Callable[[], Some[T]]
RxPut = Callable[[T], None]


class Rx(Generic[T]):
    def receive(self, get: RxGet[Any], put: RxPut[Any], data: T) -> None:
        if get() is None:
            put(data)


class CountRx(Rx[Any]):
    def receive(self, get: RxGet[int], put: RxPut[int], data: Any) -> None:
        v = get()

        if v is None:
            put(1)
        else:
            put(v.value + 1)


class AccumRx(Rx[T]):
    def receive(self, get: RxGet[list[T]], put: RxPut[list[T]], data: T) -> None:
        v = get()

        if v is None:
            put([data])
        else:
            put([*v.value, data])
