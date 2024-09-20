from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Iterable

from ..utils.misc import Some
from .capture import Capture, SimpleCapture

if TYPE_CHECKING:
    from .receiver import Rx


@dataclass
class _Fragment:
    name: str
    type: Some[Any] = None
    variadic: bool = False
    cast: bool = False
    default: Some[Any] = None

    capture: Capture = SimpleCapture()
    receiver: Rx[Any] | None = None
    validator: Callable[[Any], bool] | None = None
    transformer: Callable[[Any], Any] | None = None


def assert_fragments_order(fragments: Iterable[_Fragment]):
    default_exists = False
    variadic_exists = False

    for frag in fragments:
        if variadic_exists:
            raise ValueError  # after variadic

        if frag.default is not None:
            default_exists = True
        elif default_exists:
            raise ValueError  # required after optional

        if frag.variadic:
            if variadic_exists:
                raise ValueError  # multiple variadic

            if frag.default is not None:
                raise ValueError  # variadic with default
