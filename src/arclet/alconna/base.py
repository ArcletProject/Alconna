"""Alconna 的基础内容相关"""
from __future__ import annotations

import re
from dataclasses import replace, dataclass, field, asdict, fields
from typing import Any, Iterable, Sequence, overload, Literal, TypedDict

from nepattern import TPattern
from typing_extensions import Self

from tarina import Empty, lang

from .action import Action, store
from .args import ARGS_PARAM, Arg, ArgsBase, ArgsMeta, ArgsBuilder, _Args, handle_args
from .exceptions import InvalidArgs
from .typing import Unset, UNSET

_repr_ = lambda self: "(" + " ".join([f"{k}={getattr(self, k, ...)!r}" for k in self.__slots__]) + ")"


@dataclass(init=False, eq=True)
class OptionResult:
    """选项解析结果

    Attributes:
        value (Any): 选项值
        args (dict[str, Any]): 选项参数解析结果
    """

    __slots__ = ("value", "args")
    __repr__ = _repr_

    value: Any
    args: dict[str, Any]

    def __init__(self, value: Any = Ellipsis, args: dict[str, Any] | None = None) -> None:
        self.value = value
        self.args = args or {}


@dataclass(init=False, eq=True)
class SubcommandResult:
    """子命令解析结果

    Attributes:
        value (Any): 子命令值
        args (dict[str, Any]): 子命令参数解析结果
        options (dict[str, OptionResult]): 子命令的子选项解析结果
        subcommands (dict[str, SubcommandResult]): 子命令的子子命令解析结果
    """

    __slots__ = ("value", "args", "options", "subcommands")
    __repr__ = _repr_

    value: Any
    args: dict[str, Any]
    options: dict[str, OptionResult]
    subcommands: dict[str, SubcommandResult]

    def __init__(
        self,
        value: Any = Ellipsis,
        args: dict[str, Any] | None = None,
        options: dict[str, OptionResult] | None = None,
        subcommands: dict[str, SubcommandResult] | None = None
    ) -> None:
        self.value = value
        self.args = args or {}
        self.options = options or {}
        self.subcommands = subcommands or {}


@dataclass(init=False, eq=True)
class HeadResult:
    """命令头解析结果

    Attributes:
        origin (Any): 命令头原始值
        result (Any): 命令头解析结果
        matched (bool): 命令头是否匹配
    """

    __slots__ = ("origin", "result", "matched")
    __repr__ = _repr_

    origin: Any
    result: Any
    matched: bool

    def __init__(
        self,
        origin: Any = None,
        result: Any = None,
        matched: bool = False,
    ) -> None:
        self.origin = origin
        self.result = result
        self.matched = matched


class Header:
    """命令头部的匹配表达式"""

    __slots__ = ("origin", "content", "mapping", "compact", "compact_pattern")

    def __init__(
        self,
        origin: tuple[str, list[str]],
        content: set[str],
        compact: bool,
        compact_pattern: TPattern,
    ):
        self.origin = origin  # type: ignore
        self.content = content  # type: ignore
        self.compact = compact
        self.compact_pattern = compact_pattern  # type: ignore

    def __repr__(self):
        if not self.origin[1]:
            return self.origin[0]
        if self.origin[0]:
            return f"[{'│'.join(self.origin[1])}]{self.origin[0]}" if len(
                self.content) > 1 else f"{next(iter(self.content))}"  # noqa: E501
        return '│'.join(self.origin[1])

    def is_intersect(self, header: Header) -> bool:
        """判断是否与另一个头部有交集

        Args:
            header (Header): 另一个头部

        Returns:
            bool: 是否有交集
        """
        return bool(self.content & header.content)

    @classmethod
    def generate(
        cls,
        command: str,
        prefixes: list[str],
        compact: bool,
    ):
        if not prefixes:
            return cls((command, prefixes), {command}, compact, re.compile(f"^{command}"))
        prf = "|".join(re.escape(h) for h in prefixes)
        compp = re.compile(f"^(?:{prf}){command}")
        return cls((command, prefixes), {f"{h}{command}" for h in prefixes}, compact, compp)


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
    args: _Args
    """命令节点参数"""
    separators: str
    """命令节点分隔符"""
    action: Action
    """命令节点响应动作"""
    help_text: str
    """命令节点帮助信息"""
    soft_keyword: bool
    "是否为软关键字"

    def __init__(
        self,
        name: str,
        args: ARGS_PARAM | None = None,
        alias: Iterable[str] | None = None,
        dest: str | None = None,
        default: Any = Empty,
        action: Action | None = None,
        separators: str | Sequence[str] | set[str] | None = None,
        help_text: str | None = None,
        soft_keyword: bool = False
    ):
        """
        初始化命令节点

        Args:
            name (str): 命令节点名称
            args (Arg | list[Arg] | ArgsBuilder | type[ArgsBase] | None, optional): 命令节点参数
            dest (str | None, optional): 命令节点目标名称
            default (Any, optional): 命令节点默认值
            action (Action | None, optional): 命令节点响应动作
            separators (str | Sequence[str] | Set[str] | None, optional): 命令分隔符
            help_text (str | None, optional): 命令帮助信息
            soft_keyword (bool, optional): 是否为软关键字
        """
        self.separators = " " if separators is None else "".join(separators)
        aliases = list(alias or [])
        name = re.sub(f"[{self.separators}]", "", name)
        if "|" in name:
            _aliases = name.split("|")
            _aliases.sort(key=len, reverse=True)
            name = _aliases[0]
            aliases.extend(_aliases[1:])
        if not name:
            raise InvalidArgs(lang.require("common", "name_empty"))
        aliases.insert(0, name)
        self.name = name
        self.aliases = frozenset(aliases)
        self.args = handle_args(args)
        self.default = default
        self.action = action or store
        _handle_default(self)

        self.nargs = len(self.args.data)
        self.dest = dest or self.name
        self.dest = self.dest.lstrip("-") or self.dest
        self.help_text = help_text or self.dest
        self.soft_keyword = soft_keyword
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
        self.separators = "".join(separator)
        self._hash = self._calc_hash()
        return self

    def __repr__(self):
        data = {}
        if self.args.data:
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
        args: ARGS_PARAM | None = None,
        alias: Iterable[str] | None = None,
        dest: str | None = None,
        default: Any = Empty,
        action: Action | None = None,
        separators: str | Sequence[str] | set[str] | None = None,
        help_text: str | None = None,
        soft_keyword: bool = False,
        compact: bool = False
    ):
        """初始化命令选项

        Args:
            name (str): 命令选项名称
            args (Arg | list[Arg] | ArgsBuilder | type[ArgsBase] | None, optional): 命令选项参数
            alias (Iterable[str] | None, optional): 命令选项别名
            dest (str | None, optional): 命令选项目标名称
            default (Any, optional): 命令选项默认值
            action (Action | None, optional): 命令选项响应动作
            separators (str | Sequence[str] | Set[str] | None, optional): 命令分隔符
            help_text (str | None, optional): 命令选项帮助信息
            compact (bool, optional): 是否允许名称与后随参数之间无分隔符
            soft_keyword (bool, optional): 是否为软关键字
        """

        self.compact = compact
        if default is not Empty and not isinstance(default, (OptionResult, SubcommandResult)):
            default = OptionResult(default)
        super().__init__(name, args, alias, dest, default, action, separators, help_text, soft_keyword)
        if self.args.data:
            if default is not Empty and not self.default.args:
                self.default.args = {self.args.data[0].name: self.default.value} if not isinstance(self.default.value, dict) else self.default.value
                self.default.value = ...
            if self.default is Empty and (defaults := {arg.name: arg.field.default for arg in self.args.data if arg.field.default is not Empty}):
                self.default = OptionResult(args=defaults)
        if not self.separators:
            self.compact = True
            self.separators = " "
        self._hash = self._calc_hash()

    @overload
    def __add__(self, other: Option) -> Subcommand:
        ...

    @overload
    def __add__(self, other: ARGS_PARAM) -> Option:
        ...

    def __add__(self, other: Option | ARGS_PARAM) -> Subcommand | Option:
        """连接命令选项与命令节点或命令选项, 生成子命令

        Args:
            other (Option | ARGS_PARAM): 命令节点或命令选项

        Returns:
            Option | Subcommand: 如果other为命令选项, 则返回生成的子命令, 否则返回自己

        Raises:
            TypeError: 如果other不是命令选项或命令节点, 则抛出此异常
        """
        if isinstance(other, Option):
            return Subcommand(self.name, *self.args.data, other, dest=self.dest, separators=self.separators, help_text=self.help_text, soft_keyword=self.soft_keyword)  # noqa: E501
        try:
            _args = handle_args(other)
            self.args = _Args([*self.args.data, *_args.data])
            self.nargs = len(self.args.data)
            self._hash = self._calc_hash()
            return self
        except TypeError:
            raise TypeError(f"unsupported operand type(s) for +: 'Option' and '{other.__class__.__name__}'") from None

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
        *args: Arg | ArgsBuilder | type[ArgsBase] | Option | Subcommand | list[Option | Subcommand],
        alias: Iterable[str] | None = None,
        dest: str | None = None,
        default: Any = Empty,
        separators: str | Sequence[str] | set[str] | None = None,
        help_text: str | None = None,
        soft_keyword: bool = False
    ):
        """初始化子命令

        Args:
            name (str): 子命令名称
            *args (Arg | ArgsBuilder | type[ArgsBase] | Option | Subcommand | list[Option | Subcommand]): 参数, 选项或子命令
            dest (str | None, optional): 子命令选项目标名称
            default (Any, optional): 子命令默认值
            action (Action | None, optional): 子命令选项响应动作
            separators (str | Sequence[str] | Set[str] | None, optional): 子命令分隔符
            help_text (str | None, optional): 子命令选项帮助信息
            soft_keyword (bool, optional): 是否为软关键字
        """
        self.options = [i for i in args if isinstance(i, (Option, Subcommand))]
        for li in args:
            if isinstance(li, list) :
                self.options.extend(li)
        if default is not Empty and not isinstance(default, (OptionResult, SubcommandResult)):
            default = SubcommandResult(default)
        _args = next((i for i in args if isinstance(i, type) and issubclass(i, ArgsBase)), None)
        if _args is None:
            _args = []
            for i in args:
                if isinstance(i, Arg):
                    _args.append(i)
                elif isinstance(i, ArgsBuilder):
                    _args.extend(i)
        super().__init__(
            name,
            _args,
            alias, dest, default, None, separators, help_text, soft_keyword
        )
        if self.args.data and default is not Empty and not self.default.args:
            self.default.args = {self.args.data[0].name: self.default.value} if not isinstance(self.default.value, dict) else self.default.value
            self.default.value = ...
        if self.default is Empty and (defaults := {arg.name: arg.field.default for arg in self.args.data if arg.field.default is not Empty}):
            self.default = SubcommandResult(args=defaults)
        self._hash = self._calc_hash()

    def __add__(self, other: Option | ARGS_PARAM | str) -> Self:
        """连接子命令与命令选项或命令节点

        Args:
            other (Option | Arg | list[Arg] | ArgsBuilder | type[ArgsBase] | str): 命令选项或命令节点

        Returns:
            Self: 返回子命令自身

        Raises:
            TypeError: 如果other不是命令选项或命令节点, 则抛出此异常
        """
        if isinstance(other, (Option, str)):
            self.options.append(Option(other) if isinstance(other, str) else other)
            self._hash = self._calc_hash()
            return self
        try:
            _args = handle_args(other)
            self.args = _Args([*self.args.data, *_args.data])
            self.nargs = len(self.args.data)
            self._hash = self._calc_hash()
            return self
        except TypeError:
            raise TypeError(f"unsupported operand type(s) for +: 'Subcommand' and '{other.__class__.__name__}'") from None

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


SPECIAL_OPTIONS = (Help, Shortcut, Completion)
"""内置选项"""


@dataclass(unsafe_hash=True)
class Metadata:
    """命令元数据"""

    description: str = field(default="Unknown")
    "命令的描述"
    usage: str | None = field(default=None)
    "命令的用法"
    example: str | None = field(default=None)
    "命令的使用样例"
    author: str | None = field(default=None)
    "命令的作者"
    version: str | None = field(default=None)
    "命令的版本"
    extra: dict[str, Any] = field(default_factory=dict, hash=False)
    "命令的自定义额外信息"


class OptionNames(TypedDict):
    help: set[str]
    """帮助选项的名称"""
    shortcut: set[str]
    """快捷选项的名称"""
    completion: set[str]
    """补全选项的名称"""


@dataclass(unsafe_hash=True)
class Config:
    """命令配置"""
    disable_builtin_options: set[str] = field(default_factory=lambda : {"shortcut"})
    """禁用的内置选项"""
    builtin_option_name: OptionNames = field(
        default_factory=lambda: {
            "help": {"--help", "-h"},
            "shortcut": {"--shortcut", "-sct"},
            "completion": {"--comp", "-cp", "?"},
        }
    )
    """内置选项的名称"""
    enable_message_cache: Unset[bool] = field(default=UNSET, metadata={"default": True})
    """默认是否启用消息缓存"""
    fuzzy_match: Unset[bool] = field(default=UNSET, metadata={"default": False})
    "命令是否开启模糊匹配"
    fuzzy_threshold: Unset[float] = field(default=UNSET, metadata={"default": 0.6})
    """模糊匹配阈值"""
    raise_exception: Unset[bool] = field(default=UNSET, metadata={"default": False})
    "命令是否抛出异常"
    hide: Unset[bool] = field(default=UNSET, metadata={"default": False})
    "命令是否对manager隐藏"
    hide_shortcut: Unset[bool] = field(default=UNSET, metadata={"default": False})
    "命令的快捷指令是否在help信息中隐藏"
    keep_crlf: Unset[bool] = field(default=UNSET, metadata={"default": False})
    "命令是否保留换行字符"
    compact: Unset[bool] = field(default=UNSET, metadata={"default": False})
    "命令是否允许第一个参数紧随头部"
    strict: Unset[bool] = field(default=UNSET, metadata={"default": True})
    "命令是否严格匹配，若为 False 则未知参数将作为名为 $extra 的参数"
    context_style: Unset[Literal["bracket", "parentheses"] | None] = field(default=UNSET, metadata={"default": None})
    "命令上下文插值的风格，None 为关闭，bracket 为 {...}，parentheses 为 $(...)"
    extra: dict[str, Any] = field(default_factory=dict, hash=False)
    "命令的自定义额外配置"

    @classmethod
    def merge(cls, self: Config, other: Config) -> Config:
        """合并命令配置

        Args:
            self (Config): 当前命令配置
            other (Config): 另一个命令配置

        Returns:
            Config: 合并后的命令配置
        """
        result = {}
        self_data = asdict(self)
        other_data = asdict(other)
        for fld in fields(Config):
            if fld.name == "extra":
                result[fld.name] = {**other_data[fld.name], **self_data[fld.name]}
                continue
            if fld.name == "disable_builtin_options":
                default = fld.default_factory()  # type: ignore
                if self_data[fld.name] != default and other_data[fld.name] != default:
                    result[fld.name] = self_data[fld.name] | other_data[fld.name]
                else:
                    result[fld.name] = self_data[fld.name] if self_data[fld.name] != default else other_data[fld.name]
                continue
            if fld.name == "builtin_option_name":
                names = {}
                default = fld.default_factory()  # type: ignore
                for k in ("help", "shortcut", "completion"):
                    if self_data[fld.name][k] != default[k] and other_data[fld.name][k] != default[k]:
                        names[k] = self_data[fld.name][k] | other_data[fld.name][k]
                    else:
                        names[k] = self_data[fld.name][k] if self_data[fld.name][k] != default[k] else other_data[fld.name][k]
                result[fld.name] = names
                # result[fld.name] = {k: other_data[fld.name][k] | self_data[fld.name][k] for k in other_data[fld.name]}
                continue
            default = fld.metadata["default"]
            result[fld.name] = self_data[fld.name] if self_data[fld.name] is not UNSET else other_data[fld.name] if other_data[fld.name] is not UNSET else default
        return cls(**result)
