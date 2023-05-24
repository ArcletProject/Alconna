"""Alconna 的基础内容相关"""
from __future__ import annotations

from functools import reduce
from dataclasses import replace
from typing import Any, Iterable, Sequence

from tarina import lang
from typing_extensions import Self

from .action import Action, store
from .args import Arg, Args
from .exceptions import InvalidParam
from .model import OptionResult, SubcommandResult


def _handle_default(node: CommandNode):
    if node.default is None:
        return
    act = node.action
    if act.type == 1 and not isinstance(act.value, list):
        act = node.action = replace(act, value=[act.value])
    elif act.type == 2 and not isinstance(act.value, int):
        act = node.action = replace(act, value=1)
    if isinstance(node.default, (OptionResult, SubcommandResult)):
        if act.type == 0 and act.value is ...:
            node.action = Action(act.type, node.default.value)
        if act.type == 1:
            if not isinstance(node.default.value, list):
                node.default.value = [node.default.value]
            if act.value[0] is ...:
                node.action = Action(act.type, node.default.value[:])
        if act.type == 2 and not isinstance(node.default.value, int):
            node.default.value = 1
    else:
        if act.type == 0 and act.value is ...:
            node.action = Action(act.type, node.default)
        if act.type == 1:
            if not isinstance(node.default, list):
                node.default = [node.default]
            if act.value[0] is ...:
                node.action = Action(act.type, node.default[:])
        if act.type == 2 and not isinstance(node.default, int):
            node.default = 1


class CommandNode:
    """命令节点基类, 规定基础组件所含属性"""

    name: str
    """命令节点名称"""
    dest: str
    """命令节点目标名称"""
    default: Any
    """命令节点默认值"""
    args: Args
    """命令节点参数"""
    separators: tuple[str, ...]
    """命令节点分隔符"""
    action: Action
    """命令节点响应动作"""
    help_text: str
    """命令节点帮助信息"""

    def __init__(
        self, name: str, args: Arg | Args | None = None,
        dest: str | None = None, default: Any = None, action: Action | None = None,
        separators: str | Sequence[str] | set[str] | None = None,
        help_text: str | None = None,
    ):
        """
        初始化命令节点

        Args:
            name (str): 命令节点名称
            args (Arg | Args | None, optional): 命令节点参数
            dest (str | None, optional): 命令节点目标名称
            default (Any, optional): 命令节点默认值
            action (Action | None, optional): 命令节点响应动作
            separators (str | Sequence[str] | Set[str] | None, optional): 命令分隔符
            help_text (str | None, optional): 命令帮助信息
        """
        if not name:
            raise InvalidParam(lang.require("common", "name_empty"))
        self.name = name
        self.args = Args() + args
        self.default = default
        self.action = action or store
        _handle_default(self)
        self.separators = (' ',) if separators is None else (
            (separators,) if isinstance(separators, str) else tuple(separators)
        )
        self.nargs = len(self.args.argument)
        self.dest = (dest or self.name).lstrip('-')
        self.help_text = help_text or self.dest
        self._hash = self._calc_hash()

    nargs: int
    _hash: int

    def separate(self, *separator: str) -> Self:
        """设置命令分隔符

        Args:
            *separator(str): 命令分隔符

        Returns:
            Self: 命令节点本身
        """
        self.separators = separator
        self._hash = self._calc_hash()
        return self

    def __repr__(self):
        data = {}
        if not self.args.empty:
            data["args"] = self.args
        if self.default is not None:
            data["default"] = self.default
        return f"{self.__class__.__name__}({self.dest!r}, {', '.join(f'{k}={v!r}' for k, v in data.items())})"

    def _calc_hash(self):
        data = vars(self)
        data.pop("_hash", None)
        return hash(repr(data))

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.__hash__() == other.__hash__()


class Option(CommandNode):
    """命令选项

    相比命令节点, 命令选项可以设置别名, 优先级, 允许名称与后随参数之间无分隔符
    """

    default: OptionResult | None
    """命令选项默认值"""
    aliases: frozenset[str]
    """命令选项别名"""
    priority: int
    """命令选项优先级"""
    compact: bool
    "是否允许名称与后随参数之间无分隔符"

    def __init__(
        self,
        name: str, args: Arg | Args | None = None, alias: Iterable[str] | None = None,
        dest: str | None = None, default: Any = None, action: Action | None = None,
        separators: str | Sequence[str] | set[str] | None = None,
        help_text: str | None = None,
        compact: bool = False, priority: int = 0,
    ):
        """初始化命令选项

        Args:
            name (str): 命令选项名称
            args (Arg | Args | None, optional): 命令选项参数
            alias (Iterable[str] | None, optional): 命令选项别名
            dest (str | None, optional): 命令选项目标名称
            default (Any, optional): 命令选项默认值
            action (Action | None, optional): 命令选项响应动作
            separators (str | Sequence[str] | Set[str] | None, optional): 命令分隔符
            help_text (str | None, optional): 命令选项帮助信息
            compact (bool, optional): 是否允许名称与后随参数之间无分隔符
            priority (int, optional): 命令选项优先级
        """
        aliases = list(alias or [])
        _name = name.split(" ")[-1]
        if "|" in _name:
            _aliases = _name.split("|")
            _aliases.sort(key=len, reverse=True)
            name = name.replace(_name, _aliases[0])
            _name = _aliases[0]
            aliases.extend(_aliases[1:])
        aliases.insert(0, _name)
        self.aliases = frozenset(aliases)
        self.priority = priority
        self.compact = compact
        default = (
            None if default is None else
            default if isinstance(default, OptionResult) else OptionResult(default)
        )
        super().__init__(name, args, dest, default, action, separators, help_text)
        if self.separators == ("",):
            self.compact = True
            self.separators = (" ",)


class Subcommand(CommandNode):
    """子命令, 次于主命令

    与命令节点不同, 子命令可以包含多个命令选项与相对于自己的子命令
    """
    default: SubcommandResult | None
    """子命令默认值"""
    options: list[Option | Subcommand]
    """子命令包含的选项与子命令"""

    def __init__(
        self,
        name: str,
        *args: Args | Arg | Option | Subcommand | list[Option | Subcommand],
        dest: str | None = None, default: Any = None,
        separators: str | Sequence[str] | set[str] | None = None,
        help_text: str | None = None,
    ):
        """初始化子命令

        Args:
            name (str): 子命令名称
            *args (Args | Arg | Option | Subcommand | list[Option | Subcommand]): 参数, 选项或子命令
            dest (str | None, optional): 子命令选项目标名称
            default (Any, optional): 子命令默认值
            action (Action | None, optional): 子命令选项响应动作
            separators (str | Sequence[str] | Set[str] | None, optional): 子命令分隔符
            help_text (str | None, optional): 子命令选项帮助信息
        """
        self.options = [i for i in args if isinstance(i, (Option, Subcommand))]
        for li in filter(lambda x: isinstance(x, list), args):
            self.options.extend(li)
        default = (
            None if default is None else
            default if isinstance(default, SubcommandResult) else SubcommandResult(default)
        )
        super().__init__(
            name,
            reduce(lambda x, y: x + y, [Args()] + [i for i in args if isinstance(i, (Arg, Args))]),  # type: ignore
            dest, default, None, separators, help_text
        )

    def add(self, opt: Option | Subcommand) -> Self:
        """添加选项或子命令

        Args:
            opt (Option | Subcommand): 选项或子命令

        Returns:
            Self: 返回子命令自身
        """
        self.options.append(opt)
        self._hash = self._calc_hash()
        return self


__all__ = ["CommandNode", "Option", "Subcommand"]
