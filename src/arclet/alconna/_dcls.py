from __future__ import annotations
from typing import TYPE_CHECKING

from dataclasses import dataclass


if TYPE_CHECKING:

    def safe_dcls_kw(
        match_args=True,
        kw_only=False,
        slots=False,
        weakref_slot=False,
        **kwargs,
    ) -> dict[str, bool]: ...
else:
    from inspect import Signature

    _available_dc_attrs = set(Signature.from_callable(dataclass).parameters.keys())

    def safe_dcls_kw(**kwargs):
        return {k: v for k, v in kwargs.items() if k in _available_dc_attrs}
