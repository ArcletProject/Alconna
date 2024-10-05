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


def koption(name: str):
    return PointerRole.OPTION, name

def ccoption(name: str):
    return ((PointerRole.OPTION, name),)

def ksubcommand(name: str):
    return PointerRole.SUBCOMMAND, name

def ccsubcommand(name: str):
    return ((PointerRole.SUBCOMMAND, name),)

kheader = PointerRole.HEADER, HEADER_STR
kprefix = PointerRole.PREFIX, PREFIX_STR
ccprefix = ((PointerRole.PREFIX, PREFIX_STR),)
ccheader = ((PointerRole.HEADER, HEADER_STR),)
