"""Alconna 的组件相关"""
from typing import Union, Dict, List, Any, Optional, Callable, Iterable
from .base import CommandNode, Args, ArgAction


class Option(CommandNode):
    """命令选项, 可以使用别名"""
    aliases: List[str]

    def __init__(
            self,
            name: str,
            args: Union[Args, str, None] = None,
            alias: Optional[List[str]] = None,
            action: Optional[Union[ArgAction, Callable]] = None,
            separator: Optional[str] = None,
            help_text: Optional[str] = None,

    ):
        self.aliases = alias if alias else []
        if "|" in name:
            aliases = name.replace(' ', '').split('|')
            aliases.sort(key=len, reverse=True)
            name = aliases[0]
            self.aliases.extend(aliases[1:])
        self.aliases.insert(0, name)
        super().__init__(name, args, action, separator, help_text)

    def to_dict(self) -> Dict[str, Any]:
        return {**super().to_dict(), "aliases": self.aliases}

    def __getstate__(self):
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Option":
        name = data['name']
        aliases = data['aliases']
        args = Args.from_dict(data['args'])
        opt = cls(name, args, alias=aliases, separator=data['separator'], help_text=data['help_text'])
        return opt

    def __setstate__(self, state):
        self.__init__(
            state['name'],
            Args.from_dict(state['args']),
            alias=state['aliases'],
            separator=state['separator'],
            help_text=state['help_text']
        )


class Subcommand(CommandNode):
    """子命令, 次于主命令, 可解析 SubOption"""
    options: List[Option]
    sub_params: Dict[str, Option]
    sub_part_len: range

    def __init__(
            self,
            name: str,
            options: Optional[Iterable[Option]] = None,
            args: Union[Args, str, None] = None,
            action: Optional[Union[ArgAction, Callable]] = None,
            separator: Optional[str] = None,
            help_text: Optional[str] = None,
    ):
        self.options = list(options or [])
        super().__init__(name, args, action, separator, help_text)
        self.sub_params = {}
        self.sub_part_len = range(self.nargs)

    def to_dict(self) -> Dict[str, Any]:
        return {**super().to_dict(), "options": [option.to_dict() for option in self.options]}

    def __getstate__(self):
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subcommand":
        name = data['name']
        options = [Option.from_dict(option) for option in data['options']]
        args = Args.from_dict(data['args'])
        sub = cls(name, options, args, separator=data['separator'], help_text=data['help_text'])
        return sub

    def __setstate__(self, state):
        self.__init__(
            state['name'],
            [Option.from_dict(option) for option in state['options']],
            args=Args.from_dict(state['args']),
            separator=state['separator'],
            help_text=state['help_text']
        )
