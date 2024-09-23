from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

from ..utils.misc import Some

T = TypeVar("T")

RxFetch = Callable[[], Any]
RxPrev = Callable[[], Some[T]]
RxPut = Callable[[T], None]


class Rx(Generic[T]):
    def receive(self, fetch: RxFetch, prev: RxPrev, put: RxPut) -> None:
        put(fetch())


class CountRx(Rx[int]):
    def receive(self, fetch: RxFetch, prev: RxPrev[int], put: RxPut[int]) -> None:
        v = prev()

        if v is None:
            put(1)
        else:
            put(v.value + 1)


class AccumRx(Rx[T]):
    def receive(self, fetch: RxFetch, prev: RxPrev[list[T]], put: RxPut[list[T]]) -> None:
        v = prev()

        if v is None:
            put([fetch()])
        else:
            put(v.value + [fetch()])


class ConstraintRx(Generic[T], Rx[T]):
    value: T

    def __init__(self, value: T):
        self.value = value

    def receive(self, fetch: RxFetch, prev: RxPrev[T], put: RxPut[T]) -> None:
        put(self.value)
