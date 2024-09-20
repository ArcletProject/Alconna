from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from .snapshot import AnalyzeSnapshot

T = TypeVar("T")


@dataclass
class Rx(Generic[T]):
    name: str

    def receive(self, snapshot: AnalyzeSnapshot, data: T) -> None:
        snapshot.cache[self.name] = data

    def load(self, snapshot: AnalyzeSnapshot):
        return snapshot.cache[self.name]


@dataclass
class CountRx(Rx[Any]):
    def receive(self, snapshot: AnalyzeSnapshot, data: Any) -> None:
        snapshot.cache[self.name] = snapshot.cache.get(self.name, 0) + 1

    def load(self, snapshot: AnalyzeSnapshot):
        return snapshot.cache.get(self.name, 0)


@dataclass
class AccumRx(Rx[T]):
    def receive(self, snapshot: AnalyzeSnapshot, data: str) -> None:
        if self.name in snapshot.cache:
            target = snapshot.cache[self.name]
        else:
            target = snapshot.cache[self.name] = []

        target.append(data)

    def load(self, snapshot: AnalyzeSnapshot):
        return snapshot.cache.get(self.name) or []
