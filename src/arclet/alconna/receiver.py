from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

from .utils import Some

T = TypeVar("T")

RxFetch = Callable[[], T]
RxPrev = Callable[[], Some[T]]


class Rx(Generic[T]):
    def receive(self, fetch: RxFetch[T], prev: RxPrev) -> Any:
        return fetch()


class CountRx(Rx[int]):
    def receive(self, fetch: RxFetch[int], prev: RxPrev[int]) -> int:
        v = prev()

        if v is None:
            return 1
        else:
            return v.value + 1


class AccumRx(Rx[T]):
    def receive(self, fetch: RxFetch[T], prev: RxPrev[list[T]]):
        v = prev()

        if v is None:
            return [fetch()]
        else:
            return [*v.value, fetch()]


class ConstRx(Generic[T], Rx[T]):
    value: T

    def __init__(self, value: T):
        self.value = value

    def receive(self, fetch: RxFetch, prev: RxPrev[T]):
        return self.value


class AccumConstRx(Generic[T], Rx[T]):
    def __init__(self, value: T):
        self.value = value

    def receive(self, fetch: RxFetch[T], prev: RxPrev[list[T]]):
        v = prev()

        if v is None:
            return [self.value]
        else:
            return [*v.value, self.value]


append = AccumRx()
append_value = AccumConstRx
count = CountRx()
store_false = ConstRx(False)
store_true = ConstRx(True)
store_value = ConstRx
