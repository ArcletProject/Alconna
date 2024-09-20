from __future__ import annotations

from typing import Literal, Union, Tuple

PointerRole = Literal["subcommand", "option"]
PointerPair = Tuple[PointerRole, str]
HeaderFragment = Tuple[Literal["header"], Literal["::"]]
PrefixFragment = Tuple[Literal["prefix"], Literal["^"]]
PointerAtom = Union[HeaderFragment, PrefixFragment]
PointerContent = Union[PointerPair, PointerAtom]


class Pointer:
    data: tuple[PointerContent, ...]

    def __init__(self, data: tuple[PointerContent, ...] = ()) -> None:
        self.data = data

    def subcommand(self, name: str):
        return Pointer((*self.data, ("subcommand", name)))

    def option(self, name: str):
        return Pointer((*self.data, ("option", name)))

    def header(self):
        return Pointer((*self.data, ("header", "::")))

    def prefix(self):
        return Pointer((*self.data, ("prefix", "^")))

    @property
    def parent(self):
        return Pointer(self.data[:-1])

    def __repr__(self):
        content = []
        for ty, val in self.data:
            if ty == "header":
                content.append("[::]")
            elif ty == "prefix":
                content.append("[^]")
            elif ty == "subcommand":
                content.append(val)
            else:
                content.append(f"#[{val}]")

        return f'Pointer({".".join(content)})'

    def __iter__(self):
        yield from self.data
