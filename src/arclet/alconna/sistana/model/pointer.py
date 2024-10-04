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


class Pointer:
    __slots__ = ("data",)

    data: PointerData

    def __init__(self, data: PointerData = ()) -> None:
        self.data = data

    def subcommand(self, name: str):
        return Pointer(self.data + ((PointerRole.SUBCOMMAND, name), ))

    def option(self, name: str):
        return Pointer(self.data + ((PointerRole.OPTION, name), ))

    def header(self):
        return Pointer(self.data + ((PointerRole.HEADER, HEADER_STR), ))

    def prefix(self):
        return Pointer(self.data + ((PointerRole.PREFIX, PREFIX_STR),))

    @property
    def parent(self):
        return Pointer(self.data[:-1])

    @property
    def last(self):
        return self.data[-1]

    @property
    def last_role(self):
        return self.last[0]

    @property
    def last_value(self):
        return self.last[1]

    def __repr__(self):
        content = []
        for ty, val in self.data:
            content.append(f"{ty.name}({val})")

        return f'Pointer({".".join(content)})'

    def __iter__(self):
        yield from self.data

    def __hash__(self):
        return hash(self.data)

    def __eq__(self, other):
        return isinstance(other, Pointer) and self.data == other.data
