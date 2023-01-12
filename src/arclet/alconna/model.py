from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from .util import _safe_dcs_args


@dataclass(**_safe_dcs_args(frozen=True, eq=True, slots=True, repr=True))
class Sentence:
    name: str
    separators: tuple[str, ...] = field(default=(' ',))


@dataclass(**_safe_dcs_args(eq=True, slots=True, repr=True))
class OptionResult:
    value: Any = field(default=Ellipsis)
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(**_safe_dcs_args(eq=True, slots=True, repr=True))
class SubcommandResult:
    value: Any = field(default=Ellipsis)
    args: dict[str, Any] = field(default_factory=dict)
    options: dict[str, OptionResult] = field(default_factory=dict)


@dataclass(**_safe_dcs_args(eq=True, slots=True, repr=True))
class HeadResult:
    origin: Any = field(default=None)
    result: Any = field(default=None)
    matched: bool = field(default=False)
    groups: dict[str, str] = field(default_factory=dict)