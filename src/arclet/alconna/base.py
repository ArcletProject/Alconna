"""Alconna 的基础内容相关"""
from __future__ import annotations

from dataclasses import replace
from functools import reduce
from typing import Any, Iterable, Sequence, overload
from typing_extensions import Self

from tarina import Empty, lang

from .action import Action, store
from .args import Arg, Args
from .exceptions import InvalidArgs
from .model import OptionResult, SubcommandResult


def _handle_default(node: CommandNode):
    if node.default is Empty:
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
            if act.value[0] is ...:  # type: ignore
                node.action = Action(act.type, node.default.value[:])
        if act.type == 2 and not isinstance(node.default.value, int):
            node.default.value = 1
    else:
        if act.type == 0 and act.value is ...:
            node.action = Action(act.type, node.default)
        if act.type == 1:
            if not isinstance(node.default, list):
                node.default = [node.default]
            if act.value[0] is ...:  # type: ignore
                node.action = Action(act.type, node.default[:])
        if act.type == 2 and not isinstance(node.default, int):
            node.default = 1


class CommandNode:
    """命令节点基类, 规定基础组件所含属性"""

    name: str
    """命令节点名称"""
    aliases: frozenset[str]
    """命令节点别名"""
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
    requires: list[str]
    """命令节点需求前缀"""

    def __init__(
        self,
        name: str,
        args: Arg | Args | None = None,
        alias: Iterable[str] | None = None,
        dest: str | None = None,
        default: Any = Empty,
        action: Action | None = None,
        separators: str | Sequence[str] | set[str] | None = None,
        help_text: str | None = None,
        requires: str | list[str] | tuple[str, ...] | set[str] | None = None,
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
            requires (str | list[str] | tuple[str, ...] | set[str] | None, optional): 命令节点需求前缀
        """
        aliases = list(alias or [])
        parts = name.split(" ")
        _name = parts[-1]
        if "|" in _name:
            _aliases = _name.split("|")
            _aliases.sort(key=len, reverse=True)
            _name = _aliases[0]
            aliases.extend(_aliases[1:])
        if not _name:
            raise InvalidArgs(lang.require("common", "name_empty"))
        aliases.insert(0, _name)
        self.name = _name
        self.aliases = frozenset(aliases)
        self.requires = ([requires] if isinstance(requires, str) else list(requires)) if requires else []
        self.requires.extend(parts[:-1])
        self.args = Args() + args
        self.default = default
        self.action = action or store
        _handle_default(self)
        self.separators = (" ",) if separators is None else ((separators,) if isinstance(separators, str) else tuple(separators))  # noqa: E501
        self.nargs = len(self.args.argument)
        self.dest = (dest or (("_".join(self.requires) + "_") if self.requires else "") + self.name.lstrip("-")).lstrip("-")  # noqa: E501
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
        if self.default is not Empty:
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

    default: OptionResult
    """命令选项默认值"""
    aliases: frozenset[str]
    """命令选项别名"""
    compact: bool
    "是否允许名称与后随参数之间无分隔符"

    def __init__(
        self,
        name: str,
        args: Arg | Args | None = None,
        alias: Iterable[str] | None = None,
        dest: str | None = None,
        default: Any = Empty,
        action: Action | None = None,
        separators: str | Sequence[str] | set[str] | None = None,
        help_text: str | None = None,
        requires: str | list[str] | tuple[str, ...] | set[str] | None = None,
        compact: bool = False,
        priority: int = 0,
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
            requires (str | list[str] | tuple[str, ...] | set[str] | None, optional): 命令选项需求前缀
            compact (bool, optional): 是否允许名称与后随参数之间无分隔符
            priority (int, optional): 命令选项优先级
        """

        self.priority = priority
        self.compact = compact
        if default is not Empty:
            default = default if isinstance(default, OptionResult) else OptionResult(default)
        super().__init__(name, args, alias, dest, default, action, separators, help_text, requires)
        if self.separators == ("",):
            self.compact = True
            self.separators = (" ",)

    @overload
    def __add__(self, other: Option) -> Subcommand:
        ...

    @overload
    def __add__(self, other: Args | Arg) -> Option:
        ...

    def __add__(self, other: Option | Args | Arg) -> Subcommand | Option:
        """连接命令选项与命令节点或命令选项, 生成子命令

        Args:
            other (Option | Args | Arg): 命令节点或命令选项

        Returns:
            Option | Subcommand: 如果other为命令选项, 则返回生成的子命令, 否则返回自己

        Raises:
            TypeError: 如果other不是命令选项或命令节点, 则抛出此异常
        """
        if isinstance(other, Option):
            return Subcommand(self.name, other, self.args, dest=self.dest, separators=self.separators, help_text=self.help_text, requires=self.requires)  # noqa: E501
        if isinstance(other, (Arg, Args)):
            self.args += other
            self.nargs = len(self.args)
            self._hash = self._calc_hash()
            return self
        raise TypeError(f"unsupported operand type(s) for +: 'Option' and '{other.__class__.__name__}'")

    def __radd__(self, other: str):
        """与字符串连接, 生成 `Alconna` 对象

        Args:
            other (str): 字符串

        Returns:
            Alconna: Alconna 对象

        Raises:
            TypeError: 如果other不是字符串, 则抛出此异常
        """
        if isinstance(other, str):
            from .core import Alconna

            return Alconna(other, self)
        raise TypeError(f"unsupported operand type(s) for +: '{other.__class__.__name__}' and 'Option'")


class Subcommand(CommandNode):
    """子命令, 次于主命令

    与命令节点不同, 子命令可以包含多个命令选项与相对于自己的子命令
    """

    default: SubcommandResult
    """子命令默认值"""
    options: list[Option | Subcommand]
    """子命令包含的选项与子命令"""

    def __init__(
        self,
        name: str,
        *args: Args | Arg | Option | Subcommand | list[Option | Subcommand],
        alias: Iterable[str] | None = None,
        dest: str | None = None,
        default: Any = Empty,
        separators: str | Sequence[str] | set[str] | None = None,
        help_text: str | None = None,
        requires: str | list[str] | tuple[str, ...] | set[str] | None = None,
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
            requires (str | list[str] | tuple[str, ...] | set[str] | None, optional): 子命令选项需求前缀
        """
        self.options = [i for i in args if isinstance(i, (Option, Subcommand))]
        for li in args:
            if isinstance(li, list):
                self.options.extend(li)
        if default is not Empty:
            default = default if isinstance(default, SubcommandResult) else SubcommandResult(default)
        super().__init__(
            name,
            reduce(lambda x, y: x + y, [Args()] + [i for i in args if isinstance(i, (Arg, Args))]),  # type: ignore
            alias, dest, default, None, separators, help_text, requires,
        )

    def __add__(self, other: Option | Args | Arg | str) -> Self:
        """连接子命令与命令选项或命令节点

        Args:
            other (Option | Args | Arg | str): 命令选项或命令节点

        Returns:
            Self: 返回子命令自身

        Raises:
            TypeError: 如果other不是命令选项或命令节点, 则抛出此异常
        """
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

    def __radd__(self, other: str):
        """与字符串连接, 生成 `Alconna` 对象

        Args:
            other (str): 字符串

        Returns:
            Alconna: Alconna 对象

        Raises:
            TypeError: 如果other不是字符串, 则抛出此异常
        """
        if isinstance(other, str):
            from .core import Alconna

            return Alconna(other, self)
        raise TypeError(f"unsupported operand type(s) for +: '{other.__class__.__name__}' and 'Subcommand'")

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


class Help(Option):
    def _calc_hash(self):
        return hash("$ALCONNA_BUILTIN_OPTION_HELP")


class Shortcut(Option):
    def _calc_hash(self):
        return hash("$ALCONNA_BUILTIN_OPTION_SHORTCUT")


class Completion(Option):
    def _calc_hash(self):
        return hash("$ALCONNA_BUILTIN_OPTION_COMPLETION")
