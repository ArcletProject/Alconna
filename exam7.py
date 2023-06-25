from arclet.alconna import Args
from arclet.alconna.action import Action, store_true, store
from typing import Literal, Union, overload, Optional
from typing_extensions import Self
from dataclasses import dataclass, field

@dataclass
class Node:
    name: str
    args: Args = field(default_factory=Args)
    action: Action = field(default=store)
    help_text: str = field(default="unknown")
    dest: str = field(default="")

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
    def assign(self, path: Literal[":args"], args: Args) -> Self:
        ...

    @overload
    def assign(self, path: Literal[":action"], action: Action) -> Self:
        ...

    @overload
    def assign(self, path: Literal[":help"], help_text: str) -> Self:
        ...

    @overload
    def assign(self, path: Literal[":dest"], dest: str) -> Self:
        ...

    @overload
    def assign(
        self,
        path: str,
        args: Optional[Args] = None,
        action: Optional[Action] = None,
        help_text: Optional[str] = None,
        dest: Optional[str] = None
    ) -> "Node":
        ...

    def assign(
        self,
        path: str,
        args: Optional[Args] = None,
        action: Optional[Action] = None,
        help_text: Optional[str] = None,
        dest: Optional[str] = None
    ) -> Union[Self, "Node"]:
        if path in self.__mapping__:
            setattr(self, self.__mapping__[path], locals()[self.__mapping__[path]])
            return self
        if path.startswith(":"):
            raise AttributeError(f"Unknown attribute {path[1:]}")
        return Node(path, args, action, help_text, dest)


node = Node("root")
foo = node.assign("foo").assign(":args", Args["foo", int]["bar", str]).assign(":action", store_true)
bar = foo.assign("[-B|--bar]", help_text="bar")
print(node)
print(foo)
print(bar)