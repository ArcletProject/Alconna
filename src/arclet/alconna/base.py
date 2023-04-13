"""Alconna 的基础内容相关"""
from __future__ import annotations

from functools import reduce
from typing import Callable, Iterable, Sequence, overload
from typing_extensions import Self

from .action import ArgAction
from .args import Arg, Args
from .lang import lang
from .exceptions import InvalidParam


class CommandNode:
    """命令体基类, 规定基础命令的参数"""
    name: str
    dest: str
    args: Args
    separators: tuple[str, ...]
    action: ArgAction | None
    help_text: str
    requires: list[str]

    def __init__(
        self, name: str, args: Arg | Args | None = None,
        dest: str | None = None, action: ArgAction | Callable | None = None,
        separators: str | Sequence[str] | set[str] | None = None,
        help_text: str | None = None,
        requires: str | list[str] | tuple[str, ...] | set[str] | None = None
    ):
        """
        初始化命令节点

        Args:
            name(str): 命令节点名称
            args(Arg | Args): 命令节点参数
            action(ArgAction): 命令节点响应动作
            separators(str | Sequence[str] | Set[str]): 命令分隔符
            help_text(str): 命令帮助信息
        """
        if not name:
            raise InvalidParam(lang.node.name_empty)
        _parts = name.split(" ")
        self.name = _parts[-1]
        self.requires = ([requires] if isinstance(requires, str) else list(requires)) if requires else []
        self.requires.extend(_parts[:-1])
        self.args = Args() + args
        self.action = ArgAction.__validator__(action, self.args)
        self.separators = (' ',) if separators is None else (
            (separators,) if isinstance(separators, str) else tuple(separators)
        )
        self.nargs = len(self.args.argument)
        self.is_compact = self.separators == ('',)
        self.dest = (dest or (("_".join(self.requires) + "_") if self.requires else "") + self.name).lstrip('-')
        self.help_text = help_text or self.dest
        self._hash = self._calc_hash()

    is_compact: bool
    nargs: int
    _hash: int

    def separate(self, *separator: str) -> Self:
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
    aliases: list[str]
    priority: int

    def __init__(
        self,
        name: str, args: Arg | Args | None = None, alias: Iterable[str] | None = None,
        dest: str | None = None, action: ArgAction | Callable | None = None,
        separators: str | Sequence[str] | set[str] | None = None,
        help_text: str | None = None,
        requires: str | list[str] | tuple[str, ...] | set[str] | None = None,
        priority: int = 0
    ):
        self.aliases = list(alias or [])
        _name = name.split(" ")[-1]
        if "|" in _name:
            _aliases = _name.split('|')
            _aliases.sort(key=len, reverse=True)
            name = name.replace(_name, _aliases[0])
            _name = _aliases[0]
            self.aliases.extend(_aliases[1:])
        self.aliases.insert(0, _name)
        self.priority = priority
        super().__init__(
            name, args, dest, action, separators, help_text, requires
        )

    @overload
    def __add__(self, other: Option) -> Subcommand: ...
    @overload
    def __add__(self, other: Args | Arg) -> Option: ...
    def __add__(self, other) -> Self | Subcommand:
        if isinstance(other, Option):
            return Subcommand(
                self.name, other, self.args, dest=self.dest, action=self.action,
                separators=self.separators, help_text=self.help_text, requires=self.requires
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
    options: list[Option | Subcommand]

    def __init__(
        self,
        name: str,
        *args: Args | Arg | Option | Subcommand | list[Option | Subcommand],
        dest: str | None = None, action: ArgAction | Callable | None = None,
        separators: str | Sequence[str] | set[str] | None = None,
        help_text: str | None = None,
        requires: str | list[str] | tuple[str, ...] | set[str] | None = None,
    ):
        self.options = [i for i in args if isinstance(i, (Option, Subcommand))]
        for li in filter(lambda x: isinstance(x, list), args):
            self.options.extend(li)
        super().__init__(
            name,
            reduce(lambda x, y: x + y, [Args()] + [i for i in args if isinstance(i, (Arg, Args))]),  # type: ignore
            dest, action, separators, help_text, requires
        )

    def __add__(self, other) -> Self:
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

    def add(self, opt: Option | Subcommand) -> Self:
        self.options.append(opt)
        self._hash = self._calc_hash()
        return self


__all__ = ["CommandNode", "Option", "Subcommand"]
