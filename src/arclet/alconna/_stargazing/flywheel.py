from __future__ import annotations
from typing import Sequence, TypeVar

from elaina_segment import Runes, build_runes as _build_runes
from flywheel import wrap_anycast

T = TypeVar("T")

@wrap_anycast
def build_runes(input: Sequence[T]) -> Runes[T]:
    return _build_runes(input)

