"""Alconna 的基础内容相关"""

import re
from dataclasses import dataclass, field
from typing import Union, Dict, Callable, Any, Optional, Sequence, List, TypedDict, Set, overload, Tuple
from .args import Args, Arg
from .exceptions import InvalidParam
from .config import config
from .components.action import ArgAction


class CommandNode:
    """
    命令体基类, 规定基础命令的参数
    """
    name: str
    dest: str
    args: Args
    separators: Tuple[str, ...]
    action: Optional[ArgAction]
    help_text: str
    requires: List[str]

    def __init__(
        self, name: str, args: Union[Args, str, None] = None,
        dest: Optional[str] = None,
        action: Optional[Union[ArgAction, Callable]] = None,
        separators: Optional[Union[str, Sequence[str], Set[str]]] = None,
        help_text: Optional[str] = None,
        requires: Optional[Union[str, List[str], Tuple[str, ...], Set[str]]] = None
    ):
        """
        初始化命令节点

        Args:
            name(str): 命令节点名称
            args(Args): 命令节点参数
            action(ArgAction): 命令节点响应动作
            separators(str | Sequence[str] | Set[str]): 命令分隔符
            help_text(str): 命令帮助信息
        """
        if not name:
            raise InvalidParam(config.lang.node_name_empty)
        if re.match(r"^[`~?/.,<>;\':\"|!@#$%^&*()_+=\[\]}{]+.*$", name):
            raise InvalidParam(config.lang.node_name_error)
        _parts = name.split(" ")
        self.name = _parts[-1]
        self.requires = (list(requires) if isinstance(requires, (list, tuple, set)) else [requires]) \
            if requires else _parts[:-1]
        self.args = (args if isinstance(args, Args) else Args.from_string_list(
            [re.split("[:=]", p) for p in re.split(r"\s*,\s*", args)], {}
        )) if args else Args()
        self.action = ArgAction.__validator__(action, self.args)
        self.separators = (' ', ) if separators is None else (
            (separators, ) if isinstance(separators, str) else tuple(separators)
        )
        self.nargs = len(self.args.argument)
        self.is_compact = self.separators == ('', )
        self.dest = (dest or (("_".join(self.requires) + "_") if self.requires else "") + self.name).lstrip('-')
        self.help_text = help_text or self.dest
        self._hash = self._calc_hash()

    is_compact: bool
    nargs: int
    _hash: int

    def separate(self, *separator: str):
        self.separators = separator
        self._hash = self._calc_hash()
        return self

    def __repr__(self):
        return self.dest + ("" if self.args.empty else f"(args={self.args})")

    def _calc_hash(self):
        data = vars(self)
        data.pop('_hash', None)
        return hash(str(data))

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.__hash__() == other.__hash__()


class Option(CommandNode):
    """命令选项, 可以使用别名"""
    priority: int

    def __init__(
        self,
        name: str, args: Union[Args, str, None] = None,
        alias: Optional[List[str]] = None,
        dest: Optional[str] = None,
        action: Optional[Union[ArgAction, Callable]] = None,
        separators: Optional[Union[str, Sequence[str], Set[str]]] = None,
        help_text: Optional[str] = None,
        requires: Optional[Union[str, List[str], Tuple[str, ...], Set[str]]] = None,
        priority: int = 0
    ):
        self.aliases = alias or []
        parts = name.split(" ")
        name, rest = parts[-1], parts[:-1]
        if "|" in name:
            _aliases = name.split('|')
            _aliases.sort(key=len, reverse=True)
            name = _aliases[0]
            self.aliases.extend(_aliases[1:])
        self.aliases.insert(0, name)
        self.priority = priority
        super().__init__(
            " ".join(rest) + (" " if rest else "") + name, args, dest, action, separators, help_text, requires
        )

    @overload
    def __add__(self, other: "Option") -> "Subcommand":
        ...

    @overload
    def __add__(self, other: Union[Args, Arg]) -> "Option":
        ...

    def __add__(self, other):
        if isinstance(other, Option):
            return Subcommand(
                self.name, [other], self.args, self.dest, self.action,
                self.separators, self.help_text, self.requires
            )
        if isinstance(other, (Arg, Args)):
            self.args += other
            self.nargs = len(self.args)
            self._hash = self._calc_hash()
            return self
        raise TypeError(f"unsupported operand type(s) for +: 'Option' and '{other.__class__.__name__}'")

    def __radd__(self, other):
        if isinstance(other, str):
            from .core import Alconna
            return Alconna(other, self)
        raise TypeError(f"unsupported operand type(s) for +: '{other.__class__.__name__}' and 'Option'")


class Subcommand(CommandNode):
    """子命令, 次于主命令, 可解析 SubOption"""
    options: List[Option]
    sub_params: Dict[str, Union[List[Option], 'Sentence']]
    sub_part_len: range

    def __init__(
        self,
        name: str, options: Optional[List[Option]] = None, args: Union[Args, str, None] = None,
        dest: Optional[str] = None,
        action: Optional[Union[ArgAction, Callable]] = None,
        separators: Optional[Union[str, Sequence[str], Set[str]]] = None,
        help_text: Optional[str] = None,
        requires: Optional[Union[str, List[str], Tuple[str, ...], Set[str]]] = None,
    ):
        self.options = options or []
        super().__init__(name, args, dest, action, separators, help_text, requires)
        self.sub_params = {}
        self.sub_part_len = range(self.nargs)

    def __add__(self, other):
        if isinstance(other, (Option, str)):
            self.options.append(Option(other) if isinstance(other, str) else other)
            self._hash = self._calc_hash()
            return self
        if isinstance(other, (Arg, Args)):
            self.args += other
            self.nargs = len(self.args)
            self._hash = self._calc_hash()
            return self
        raise TypeError(f"unsupported operand type(s) for +: 'Subcommand' and '{other.__class__.__name__}'")

    def __radd__(self, other):
        if isinstance(other, str):
            from .core import Alconna
            return Alconna(other, self)
        raise TypeError(f"unsupported operand type(s) for +: '{other.__class__.__name__}' and 'Subcommand'")


@dataclass
class Sentence:
    name: str
    separators: Tuple[str, ...] = field(default=(' ',))


class OptionResult(TypedDict):
    value: Any
    args: Dict[str, Any]


class SubcommandResult(TypedDict):
    value: Any
    args: Dict[str, Any]
    options: Dict[str, OptionResult]


class StrMounter(List[str]):
    pass


__all__ = [
    "CommandNode", "Option", "Subcommand", "OptionResult", "SubcommandResult", "Sentence",
    "StrMounter"
]
