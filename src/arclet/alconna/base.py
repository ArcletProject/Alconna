"""Alconna 的基础内容相关"""
from __future__ import annotations

import dataclasses as dc
import re
import sys
from copy import deepcopy
from typing import Any, Callable, Generic, Iterable, Sequence, TypeVar, Union
from dataclasses import dataclass, replace
from enum import IntEnum, Enum
from nepattern import AllParam, AnyOne, BasePattern, RawStr, UnionPattern, all_patterns, type_parser
from tarina import Empty, lang, get_signature

from .typing import TDC

_repr_ = lambda self: "(" + " ".join([f"{k}={getattr(self, k, ...)!r}" for k in self.__slots__]) + ")"


@dataclass(init=False, eq=True)
class OptionResult:
    __slots__ = ("value", "args")
    __repr__ = _repr_
    def __init__(self, value=Ellipsis, args=None):
        self.value = value
        self.args = args or {}


@dataclass(init=False, eq=True)
class HeadResult:
    __slots__ = ("origin", "result", "matched", "groups")
    __repr__ = _repr_
    def __init__(self, origin=None, result=None, matched=False, groups=None, fixes=None):
        self.origin = origin
        self.result = result
        self.matched = matched
        self.groups = groups or {}
        if fixes:
            self.groups.update(
                {k: v.exec(self.groups[k]).value for k, v in fixes.items() if k in self.groups}  # noqa
            )


class ActType(IntEnum):
    """节点触发的动作类型"""
    STORE = 0
    """无 Args 时, 仅存储一个值, 默认为 Ellipsis; 有 Args 时, 后续的解析结果会覆盖之前的值"""
    APPEND = 1
    """无 Args 时, 将多个值存为列表, 默认为 Ellipsis; 有 Args 时, 每个解析结果会追加到列表中

    当存在默认值并且不为列表时, 会自动将默认值变成列表, 以保证追加的正确性
    """
    COUNT = 2
    """无 Args 时, 计数器加一; 有 Args 时, 表现与 STORE 相同

    当存在默认值并且不为数字时, 会自动将默认值变成 1, 以保证计数器的正确性
    """


@dataclass(eq=True, frozen=True)
class Action:
    """节点触发的动作"""
    type: ActType
    value: Any


store = Action(ActType.STORE, Ellipsis)
"""默认的存储动作"""
store_true = Action(ActType.STORE, True)
"""存储 True"""
store_false = Action(ActType.STORE, False)
"""存储 False"""

append = Action(ActType.APPEND, [Ellipsis])
"""默认的追加动作"""

count = Action(ActType.COUNT, 1)
"""默认的计数动作"""


def store_value(value: Any):
    """存储一个值

    Args:
        value (Any): 待存储的值
    """
    return Action(ActType.STORE, value)


def append_value(value: Any):
    """追加值

    Args:
        value (Any): 待存储的值
    """
    return Action(ActType.APPEND, [value])


class ParamsUnmatched(Exception):
    """一个 text 没有被任何参数匹配成功"""


class ArgumentMissing(Exception):
    """组件内的 Args 参数未能解析到任何内容"""


class InvalidParam(Exception):
    """构造 alconna 时某个传入的参数不正确"""


class NullMessage(Exception):
    """传入了无法解析的消息"""


def _handle_default(node: Option):
    if node.default is None:
        return
    act = node.action
    if act.type == 1 and not isinstance(act.value, list):
        act = node.action = replace(act, value=[act.value])
    elif act.type == 2 and not isinstance(act.value, int):
        act = node.action = replace(act, value=1)
    if isinstance(node.default, OptionResult):
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


class Option:
    """命令选项

    命令选项可以设置别名, 优先级, 允许名称与后随参数之间无分隔符
    """
    name: str
    """命令选项名称"""
    dest: str
    """命令选项目标名称"""
    args: list[Arg]
    """命令选项参数"""
    separators: tuple[str, ...]
    """命令选项分隔符"""
    default: OptionResult | None
    """命令选项默认值"""
    aliases: frozenset[str]
    """命令选项别名"""
    compact: bool
    "是否允许名称与后随参数之间无分隔符"
    action: Action
    """响应动作"""


    def __init__(
        self,
        name: str, *args: Arg, alias: Iterable[str] | None = None,
        dest: str | None = None, default: Any = None, action: Action | None = None,
        separators: str | Sequence[str] | set[str] | None = None,
        compact: bool = False,
    ):
        """初始化命令选项

        Args:
            name (str): 命令选项名称
            *args (Arg): 命令选项参数
            alias (Iterable[str] | None, optional): 命令选项别名
            dest (str | None, optional): 命令选项目标名称
            default (Any, optional): 命令选项默认值
            action (Action | None, optional): 响应动作
            separators (str | Sequence[str] | Set[str] | None, optional): 命令分隔符
            compact (bool, optional): 是否允许名称与后随参数之间无分隔符
        """
        aliases = list(alias or [])
        if not name:
            raise InvalidParam(lang.require("common", "name_empty"))
        if "|" in name:
            _aliases = name.split("|")
            _aliases.extend(aliases)
            _aliases.sort(key=len, reverse=True)
            self.name = _aliases[0]
            self.aliases = frozenset(_aliases)
        else:
            self.name = name
            self.aliases = frozenset(aliases)
        self.args = list(args)
        default = (
            None if default is None else
            default if isinstance(default, OptionResult) else OptionResult(default)
        )
        self.compact = compact
        self.default = default
        self.action = action or store
        _handle_default(self)
        self.separators = (' ',) if separators is None else (
            (separators,) if isinstance(separators, str) else tuple(separators)
        )
        self.nargs = len(self.args)
        self.dest = (dest or self.name).lstrip('-')
        self._hash = self._calc_hash()

    def __repr__(self):
        data = {}
        if self.args:
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


def safe_dcls_kw(**kwargs):
    if sys.version_info < (3, 10):  # pragma: no cover
        kwargs.pop('slots')
    return kwargs


_T = TypeVar("_T")
TAValue = Union[BasePattern, AllParam.__class__, type, str]
STRING = all_patterns()[str]


class ArgFlag(str, Enum):
    """标识参数单元的特殊属性"""
    OPTIONAL = '?'
    HIDDEN = "/"
    ANTI = "!"


@dc.dataclass(**safe_dcls_kw(init=False, eq=True, unsafe_hash=True, slots=True))
class Arg:
    """参数单元"""

    name: str = dc.field(compare=True, hash=True)
    """参数单元的名称"""
    value: BasePattern = dc.field(compare=False, hash=True)
    """参数单元的值"""
    default: Any = dc.field(compare=False, hash=False)
    """参数单元的字段"""
    flag: set[ArgFlag] = dc.field(compare=False, hash=False)
    """参数单元的标识"""
    separators: tuple[str, ...] = dc.field(compare=False, hash=False)
    """参数单元使用的分隔符"""
    optional: bool = dc.field(compare=False, hash=False)
    hidden: bool = dc.field(compare=False, hash=False)

    def __init__(
        self,
        name: str,
        value: TAValue | None = None,
        default: Any = None,
        seps: str | Iterable[str] = " ",
        flags: list[ArgFlag] | None = None,
    ):
        """构造参数单元

        Args:
            name (str): 参数单元的名称
            value (TAValue, optional): 参数单元的类型. Defaults to None.
            default (Any, optional): 参数单元的默认值. Defaults to None.
            seps (str | Iterable[str], optional): 参数单元使用的分隔符. Defaults to " ".
            flags (list[ArgFlag], optional): 参数单元的标识. Defaults to None.
        """
        if not isinstance(name, str) or name.startswith('$'):
            raise InvalidParam(lang.require("args", "name_error"))
        if not name.strip():
            raise InvalidParam(lang.require("args", "name_empty"))
        self.name = name
        _value = type_parser(value or RawStr(name))
        if isinstance(_value, UnionPattern) and _value.optional:
            default = Empty if default is None else default
        if default == "...":
            default = Empty
        if _value is Empty:
            raise InvalidParam(lang.require("args", "value_error").format(target=name))
        self.value = _value
        self.default = default
        self.separators = (seps,) if isinstance(seps, str) else tuple(seps)
        flags = flags or []
        if res := re.match(r"^(?P<name>.+?)(;)?(?P<flag>[?!/]+)", self.name):
            flags.extend(ArgFlag(c) for c in res["flag"])
            self.name = res["name"]
        self.flag = set(flags)
        self.optional = ArgFlag.OPTIONAL in self.flag
        self.hidden = ArgFlag.HIDDEN in self.flag
        if ArgFlag.ANTI in self.flag and self.value not in (AnyOne, AllParam):
            self.value = deepcopy(self.value).reverse()

    def __repr__(self):
        n, v = f"'{self.name}'", str(self.value)
        return (n if n == v else f"{n}: {v}") + (f" = '{self.default}'" if self.default is not None else "")


class Arparma(Generic[TDC]):
    """承载解析结果与操作数据的接口类

    Attributes:
        origin (TDC): 原始数据
        matched (bool): 是否匹配
        header_match (HeadResult): 命令头匹配结果
        error_info (type[BaseException] | BaseException | str): 错误信息
        error_data (list[str | Any]): 错误数据
        main_args (dict[str, Any]): 主参数匹配结果
        other_args (dict[str, Any]): 其他参数匹配结果
        options (dict[str, OptionResult]): 选项匹配结果
    """
    header_match: HeadResult
    options: dict[str, OptionResult]

    def __init__(
        self,
        origin: TDC,
        matched: bool = False,
        header_match: HeadResult | None = None,
        error_info: type[BaseException] | BaseException | str = '',
        error_data: list[str | Any] | None = None,
        main_args: dict[str, Any] | None = None,
        options: dict[str, OptionResult] | None = None,
    ):
        """初始化 `Arparma`
        Args:
            origin (TDC): 原始数据
            matched (bool, optional): 是否匹配
            header_match (HeadResult | None, optional): 命令头匹配结果
            error_info (type[BaseException] | BaseException | str, optional): 错误信息
            error_data (list[str | Any] | None, optional): 错误数据
            main_args (dict[str, Any] | None, optional): 主参数匹配结果
            options (dict[str, OptionResult] | None, optional): 选项匹配结果
        """
        self.origin = origin
        self.matched = matched
        self.header_match = header_match or HeadResult()
        self.error_info = error_info
        self.error_data = error_data or []
        self.main_args = main_args or {}
        self.other_args = {}
        self.options = options or {}

    def _clr(self):
        ks = list(self.__dict__.keys())
        for k in ks:
            delattr(self, k)

    @property
    def head_matched(self):
        """返回命令头是否匹配"""
        return self.header_match.matched

    @property
    def all_matched_args(self) -> dict[str, Any]:
        """返回 Alconna 中所有 Args 解析到的值"""
        return {**self.main_args, **self.other_args}

    def unpack(self) -> None:
        """处理 `Arparma` 中的数据"""
        for _v in self.options.values():
            self.other_args = {**self.other_args, **_v.args}

    def call(self, target: Callable[..., _T], **additional) -> _T:
        """依据 `Arparma` 中的数据调用函数

        Args:
            target (Callable[..., T]): 要调用的函数
            **additional (Any): 附加参数
        Returns:
            T: 函数返回值
        Raises:
            RuntimeError: 如果 Arparma 未匹配, 则抛出 RuntimeError
        """
        if self.matched:
            names = {p.name for p in get_signature(target)}
            return target(**{k: v for k, v in {**self.all_matched_args, **additional}.items() if k in names})
        raise RuntimeError

    def fail(self, exc: type[BaseException] | BaseException | str):
        """生成一个失败的 `Arparma`"""
        return Arparma(self.origin, False, self.header_match, error_info=exc)

    def __repr__(self):
        if self.error_info:
            attrs = ((s, getattr(self, s, None)) for s in ("matched", "header_match", "error_data", "error_info"))
            return ", ".join([f"{a}={v}" for a, v in attrs if v is not None])
        else:
            attrs = {
                "matched": self.matched, "header_match": self.header_match,
                "options": self.options,
                "main_args": self.main_args, "other_args": self.other_args
            }
            return ", ".join([f"{a}={v}" for a, v in attrs.items() if v])
