from typing import List, Tuple, Any, Dict

from arclet.alconna.main import Alconna
from arclet.alconna.base import CommandNode, Args
from arclet.alconna.component import Subcommand, Option


class _AlconnaHelpNode:
    target: CommandNode
    name: str
    parameters: Dict[str, Tuple[Any, Any]]
    description: str
    sub_nodes: List["_AlconnaHelpNode"]

    def __init__(self, target: CommandNode):
        self.target = target
        self.name = target.name
        self.description = target.help_text
        self.parameters = {}
        for key, arg in target.args.argument.items():
            self.parameters[key] = (arg['value'], arg['default'])
        self.sub_nodes = []
        if isinstance(target, (Subcommand, Alconna)):
            for sub_node in target.options:
                self.sub_nodes.append(_AlconnaHelpNode(sub_node))

    def __repr__(self):
        res = f'{self.name} + {self.description} + {self.parameters} + {self.sub_nodes}'
        return res


b = _AlconnaHelpNode(
    Alconna(command="test", help_text="test_help", options=[Option(name="test", help_text="test_help")]))
print(b)
