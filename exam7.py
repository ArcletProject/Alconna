from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, overload
from typing_extensions import Self

from arclet.alconna import Args
from arclet.alconna.action import Action, store, store_true


@dataclass
class Scope:
    refer: "Node"
    substance: dict[str, "Node"] = field(default_factory=dict)


NodeMap: dict[str, Scope] = {}


@dataclass(eq=True, unsafe_hash=True)
class Node:
    name: str
    args: Args = field(default_factory=Args)
    action: Action = field(default=store)
    help_text: str = field(default="unknown")
    dest: str = field(default="")
    scope: str = field(default="$")

    def __post_init__(self):
        if not self.dest:
            self.dest = self.name.replace("-", "")
        NodeMap.setdefault(self.path, Scope(self))

    __mapping__ = {
        ":args": "args",
        ":action": "action",
        ":help": "help_text",
        ":dest": "dest"
    }

    @property
    def path(self):
        return f"{self.scope}.{self.name}" if self.scope != "$" else self.name

    @overload
    def assign(self, path: Literal[":args"], *, args: Args) -> Self:
        ...

    @overload
    def assign(self, path: Literal[":action"], *, action: Action) -> Self:
        ...

    @overload
    def assign(self, path: Literal[":help"], *, help_text: str) -> Self:
        ...

    @overload
    def assign(self, path: Literal[":dest"], *, dest: str) -> Self:
        ...

    @overload
    def assign(self, path: str, spec: Literal[":args"], *, args: Args) -> Self:
        ...

    @overload
    def assign(self, path: str, spec: Literal[":action"], *, action: Action) -> Self:
        ...

    @overload
    def assign(self, path: str, spec: Literal[":help"], *, help_text: str) -> Self:
        ...

    @overload
    def assign(self, path: str, spec: Literal[":dest"], *, dest: str) -> Self:
        ...

    @overload
    def assign(
        self,
        path: str,
        *,
        args: Optional[Args] = None,
        action: Optional[Action] = None,
        help_text: Optional[str] = None,
        dest: Optional[str] = None
    ) -> Self:
        ...

    def assign(
        self,
        path: str,
        spec: Optional[str] = None,
        args: Optional[Args] = None,
        action: Optional[Action] = None,
        help_text: Optional[str] = None,
        dest: Optional[str] = None
    ) -> Self:
        if path in self.__mapping__:
            setattr(self, self.__mapping__[path], locals()[self.__mapping__[path]])
            return self
        if path.startswith(":"):
            raise AttributeError(f"Unknown attribute {path[1:]}")
        if spec:
            query_path = f"{self.path}.{path}"
            if query_path not in NodeMap:
                raise ValueError(f"Unknown node {query_path}")
            setattr(NodeMap[query_path].refer, self.__mapping__[spec], locals()[self.__mapping__[spec]])
            return self
        parts = path.split(".")
        prev = self
        for part in parts[:-1]:
            if part not in NodeMap[prev.path].substance:
                raise ValueError(f"Unknown node {part}")
            prev = NodeMap[prev.path].substance[part]
        new = Node(parts[-1], args, action, help_text, dest, prev.path)
        NodeMap[prev.path].substance[new.name] = new
        return self

    def select(self, path: str) -> "Node":
        if path in {"", ".", "#", "$"}:
            return self
        if path.startswith(":"):
            raise ValueError(f"Invalid path {path}")
        prev = self
        for part in path.split("."):
            if part not in NodeMap[prev.path].substance:
                raise ValueError(f"Unknown node {path}")
            prev = NodeMap[prev.path].substance[part]
        return prev


node = Node("root")
node.assign("foo")
node.assign("foo", ":args", args=Args["foo", int]["bar", str])
foo = node.select("foo")
foo.assign(":action", action=store_true)
bar = foo.assign("bar", help_text="bar").select("bar")
print(node)
print(foo)
print(bar)
print(NodeMap)
assert node.select("foo.bar") == foo.select("bar")