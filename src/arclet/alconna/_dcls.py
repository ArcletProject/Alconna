from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:

    def safe_dcls_kw(
        match_args=True,
        kw_only=False,
        slots=False,
        weakref_slot=False,
        **kwargs,
    ) -> dict[str, bool]: ...

    def safe_field_kw(
        kw_only=False,
    ) -> dict[str, Any]: ...
else:
    from inspect import Signature

    _available_dc_attrs = set(Signature.from_callable(dataclass).parameters.keys())

    def safe_dcls_kw(**kwargs):
        return {k: v for k, v in kwargs.items() if k in _available_dc_attrs}

    _available_field_attrs = set(Signature.from_callable(field).parameters.keys())

    def safe_field_kw(kw_only=False):
        return {"kw_only": kw_only} if "kw_only" in _available_field_attrs else {}
