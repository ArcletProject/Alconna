from arclet.alconna import Args
from arclet.alconna.action import Action, store_true, store
from typing import Literal, overload, Optional
from typing_extensions import Self
from dataclasses import dataclass, field

NodeMap = {}


@dataclass
class Node:
    name: str
    args: Args = field(default_factory=Args)
    action: Action = field(default=store)
    help_text: str = field(default="unknown")
    dest: str = field(default="")
    scope: str = field(init=False, default="$")

    def __post_init__(self):
        if not self.dest:
            self.dest = self.name.replace("-", "")

    __mapping__ = {
        ":args": "args",
        ":action": "action",
        ":help": "help_text",
        ":dest": "dest"
    }

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
            query_path = f"{self.scope}.{self.name}.{path}" if self.scope != "$" else f"{self.name}.{path}"
            if query_path not in NodeMap:
                raise ValueError(f"Unknown node {query_path}")
            setattr(NodeMap[query_path], self.__mapping__[spec], locals()[self.__mapping__[spec]])
            return self
        parts = path.split(".")
        prev = self
        for part in parts[:-1]:
            query_path = f"{prev.scope}.{prev.name}.{part}" if prev.scope != "$" else f"{prev.name}.{part}"
            if query_path not in NodeMap:
                raise ValueError(f"Unknown node {part}")
            prev = NodeMap[query_path]
        new = Node(parts[-1], args, action, help_text, dest)
        new.scope = f"{prev.scope}.{prev.name}" if prev.scope != "$" else prev.name
        NodeMap[f"{new.scope}.{parts[-1]}"] = new
        return self

    def select(self, path: str) -> "Node":
        if path in {"", ".", "#", "$"}:
            return self
        if path.startswith(":"):
            raise ValueError(f"Invalid path {path}")
        prev = self
        for part in path.split("."):
            query_path = f"{prev.scope}.{prev.name}.{part}" if prev.scope != "$" else f"{prev.name}.{part}"
            if query_path not in NodeMap:
                raise ValueError(f"Unknown node {part}")
            prev = NodeMap[query_path]
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