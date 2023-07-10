from __future__ import annotations

from arclet.alconna import Args
from arclet.alconna.action import Action, store_true, store
from typing import Literal, overload, Iterable, Any, Sequence
from typing_extensions import Self
from dataclasses import dataclass, field
from pprint import pprint

@dataclass
class Scope:
    refer: Node
    substance: dict[str, Node] = field(default_factory=dict)

NodeMap: dict[str, Scope] = {}


@dataclass(init=False, eq=True, unsafe_hash=True)
class Node:
    name: str
    aliases: frozenset[str]
    args: Args
    action: Action
    help_text: str
    default: Any
    dest: str
    scope: str
    separators: tuple[str, ...]

    def __init__(
        self,
        name: str,
        aliases: Iterable[str] | None = None,
        args: Args | None = None,
        default: Any = None,
        action: Action = store,
        separators: str | Sequence[str] | set[str] | None = None,
        help_text: str = "unknown",
        dest: str | None = None,
        scope: str | None = None
    ):
        self.name = name.replace(" ", "_")
        self.aliases = frozenset(aliases or [])
        self.args = args or Args()
        self.default = default
        self.action = action
        self.scope = scope or "$"
        self.separators = (' ',) if separators is None else (
            (separators,) if isinstance(separators, str) else tuple(separators)
        )
        self.help_text = help_text
        self.dest = (dest or self.name).lstrip().lstrip("-").lstrip()
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
        args: Args | None = None,
        action: Action | None = None,
        help_text: str | None = None,
        dest: str | None = None,
        upper_make: bool = False
    ) -> Self:
        ...

    def assign(
        self,
        path: str,
        spec: str | None = None,
        args: Args | None = None,
        action: Action | None = None,
        help_text: str | None = None,
        dest: str | None = None,
        upper_make: bool = False
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
                if not upper_make:
                    raise ValueError(f"Unknown node {part}")
                NodeMap[prev.path].substance[part] = Node(part, scope=prev.path)
            prev = NodeMap[prev.path].substance[part]
        new = Node(parts[-1], None, args, action, help_text=help_text, dest=dest, scope=prev.path)
        NodeMap[prev.path].substance[new.name] = new
        return self

    def select(self, path: str) -> Node:
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
c = node.assign("a.b.c", upper_make=True)
print(node)
print(foo)
print(bar)
pprint(NodeMap)
assert node.select("foo.bar") == foo.select("bar")