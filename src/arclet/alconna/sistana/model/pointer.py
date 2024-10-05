from __future__ import annotations

from enum import Enum
from typing import Tuple


class PointerRole(int, Enum):
    SUBCOMMAND = 0
    OPTION = 1
    HEADER = 2
    PREFIX = 3

PointerContent = Tuple[PointerRole, str]
PointerData = Tuple[PointerContent, ...]

HEADER_STR = "::"
PREFIX_STR = "^"

kheader = PointerRole.HEADER, HEADER_STR
kprefix = PointerRole.PREFIX, PREFIX_STR
ccprefix = kprefix,
ccheader = kheader,
