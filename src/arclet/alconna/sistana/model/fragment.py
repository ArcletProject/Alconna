from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from arclet.alconna._dcls import safe_dcls_kw

from ..some import Some
from .capture import Capture, SimpleCapture
from .receiver import Rx


@dataclass(**safe_dcls_kw(slots=True))
class _Fragment:
    name: str
    variadic: bool = False
    default: Some[Any] = None
    export: bool = False

    separators: str | None = None
    hybrid_separators: bool = True

    capture: Capture = SimpleCapture()
    receiver: Rx[Any] = Rx()
    validator: Callable[[Any], bool] | None = None
    transformer: Callable[[Any], Any] | None = None


def assert_fragments_order(fragments: Iterable[_Fragment]):
    default_exists = False
    variadic_exists = False

    for frag in fragments:
        if variadic_exists:
            raise ValueError("Found fragment after a variadic fragment, which is not allowed.")

        if frag.default is not None:
            default_exists = True
        elif default_exists:
            raise ValueError("Found a required fragment after an optional fragment, which is not allowed.")

        if frag.variadic:
            if variadic_exists:
                raise ValueError("Multiple variadic fragments found, only one is allowed.")
            if frag.default is not None:
                raise ValueError("A variadic fragment cannot have a default value.")
    
            variadic_exists = True
