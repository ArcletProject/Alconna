from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from elaina_segment import SEPARATORS, Runes, Segment, build_runes, segment

from .err import OutOfData

T = TypeVar("T")


@dataclass
class SegmentToken(Generic[T]):
    buffer: Buffer[T]
    val: Segment[T]
    tail: Callable[[], Runes[T]] | None = None

    def apply(self):
        if self.tail is not None:
            self.buffer.runes = self.tail()
        else:
            self.buffer.runes = []


@dataclass
class AheadToken(Generic[T]):
    buffer: Buffer[T]
    val: Segment[T]

    def apply(self):
        self.buffer.ahead.popleft()


class Buffer(Generic[T]):
    runes: Runes[T]
    ahead: deque[Segment[T]]

    def __init__(self, data: list[str | T]):
        self.runes = build_runes(data)
        self.ahead = deque()

    @classmethod
    def from_runes(cls, runes: Runes[T]):
        ins = super().__new__(cls)
        ins.runes = runes
        ins.ahead = deque()
        return ins

    def __repr__(self) -> str:
        return f"Buffer({self.runes})"

    def next(self, until: str = SEPARATORS) -> SegmentToken[T] | AheadToken[T]:
        if self.ahead:
            # NOTE: 在这一层其实上报 source = ahead。
            val = self.ahead[0]
            return AheadToken(self, val)

        res = segment(self.runes, until)
        if res is None:
            raise OutOfData

        val, tail = res
        return SegmentToken(self, val, tail)
