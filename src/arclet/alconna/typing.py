"""Alconna 参数相关"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Literal,
    Protocol,
    Tuple,
    TypedDict,
    TypeVar,
    Union,
    final,
    runtime_checkable,
)
from typing_extensions import NotRequired

from nepattern import BasePattern, MatchMode, parser

TPrefixes = Union[List[Union[str, object]], List[Tuple[object, str]]]
DataUnit = TypeVar("DataUnit", covariant=True)


class ShortcutRegWrapper(Protocol):
    def __call__(self, slot: int | str, content: str | None) -> Any: ...


class ShortcutArgs(TypedDict):
    """快捷指令参数"""

    command: NotRequired[str]
    """快捷指令的命令"""
    args: NotRequired[list[Any]]
    """快捷指令的附带参数"""
    fuzzy: NotRequired[bool]
    """是否允许命令后随参数"""
    prefix: NotRequired[bool]
    """是否调用时保留指令前缀"""
    wrapper: NotRequired[ShortcutRegWrapper]
    """快捷指令的正则匹配结果的额外处理函数"""
    humanized: NotRequired[str]
    """快捷指令的人类可读描述"""


DEFAULT_WRAPPER = lambda slot, content: content


class InnerShortcutArgs:
    command: DataCollection[Any]
    args: list[Any]
    fuzzy: bool
    prefix: bool
    prefixes: list[str]
    wrapper: ShortcutRegWrapper

    __slots__ = ("command", "args", "fuzzy", "prefix", "prefixes", "wrapper")

    def __init__(
        self,
        command: DataCollection[Any],
        args: list[Any] | None = None,
        fuzzy: bool = True,
        prefix: bool = False,
        prefixes: list[str] | None = None,
        wrapper: ShortcutRegWrapper | None = None
    ):
        self.command = command
        self.args = args or []
        self.fuzzy = fuzzy
        self.prefix = prefix
        self.prefixes = prefixes or []
        self.wrapper = wrapper or DEFAULT_WRAPPER

    def __repr__(self):
        return f"ShortcutArgs({self.command!r}, args={self.args!r}, fuzzy={self.fuzzy}, prefix={self.prefix})"


@runtime_checkable
class DataCollection(Protocol[DataUnit]):
    """数据集合协议"""
    def __repr__(self) -> str: ...
    def __iter__(self) -> Iterator[DataUnit]: ...
    def __len__(self) -> int: ...


@dataclass(unsafe_hash=True)
class CommandMeta:
    """命令元数据"""

    description: str = field(default="Unknown")
    "命令的描述"
    usage: str | None = field(default=None)
    "命令的用法"
    example: str | None = field(default=None)
    "命令的使用样例"
    author: str | None = field(default=None)
    "命令的作者"
    fuzzy_match: bool = field(default=False)
    "命令是否开启模糊匹配"
    fuzzy_threshold: float = field(default=0.6)
    """模糊匹配阈值"""
    raise_exception: bool = field(default=False)
    "命令是否抛出异常"
    hide: bool = field(default=False)
    "命令是否对manager隐藏"
    hide_shortcut: bool = field(default=False)
    "命令的快捷指令是否在help信息中隐藏"
    keep_crlf: bool = field(default=False)
    "命令是否保留换行字符"
    compact: bool = field(default=False)
    "命令是否允许第一个参数紧随头部"
    strict: bool = field(default=True)
    "命令是否严格匹配，若为 False 则未知参数将作为名为 $extra 的参数"
    context_style: Literal["bracket", "parentheses"] | None = field(default=None)
    "命令上下文插值的风格，None 为关闭，bracket 为 {...}，parentheses 为 $(...)"
    extra: Dict[str, Any] = field(default_factory=dict, hash=False)
    "命令的自定义额外信息"


TDC = TypeVar("TDC", bound=DataCollection[Any])
T = TypeVar("T")


@final
class _AllParamPattern(BasePattern[Any, Any, Literal[MatchMode.KEEP]]):
    def __init__(self):
        super().__init__(mode=MatchMode.KEEP, origin=Any, alias="*")

    def match(self, input_: Any) -> Any:  # pragma: no cover
        return input_

    def __calc_eq__(self, other):  # pragma: no cover
        return other.__class__ is _AllParamPattern


AllParam = _AllParamPattern()


class KeyWordVar(BasePattern[T, Any, Literal[MatchMode.KEEP]]):
    """对具名参数的包装"""

    base: BasePattern

    def __init__(self, value: BasePattern[T, Any, Any] | type[T], sep: str = "="):
        """构建一个具名参数

        Args:
            value (type | BasePattern): 参数的值
            sep (str, optional): 参数的分隔符
        """
        self.base = value if isinstance(value, BasePattern) else parser(value)  # type: ignore
        self.sep = sep
        assert isinstance(self.base, BasePattern)
        super().__init__(mode=MatchMode.KEEP, origin=self.base.origin, alias=f"@{sep}{self.base}")

    def __repr__(self):
        return self.alias


class _Kw:
    __slots__ = ()

    def __getitem__(self, item: BasePattern[T, Any, Any] | type[T]):
        return KeyWordVar(item)

    __matmul__ = __getitem__
    __rmatmul__ = __getitem__


class MultiVar(BasePattern[T, Any, Literal[MatchMode.KEEP]]):
    """对可变参数的包装"""

    base: BasePattern[T, Any, Any]
    flag: Literal["+", "*"]
    length: int

    def __init__(self, value: BasePattern[T, Any, Any] | type[T], flag: int | Literal["+", "*"] = "+"):
        """构建一个可变参数

        Args:
            value (type | BasePattern): 参数的值
            flag (int | Literal["+", "*"]): 参数的标记
        """
        self.base = value if isinstance(value, BasePattern) else parser(value)  # type: ignore
        assert isinstance(self.base, BasePattern)
        if not isinstance(flag, int):
            alias = f"({self.base}{flag})"
            self.flag = flag
            self.length = -1
        elif flag > 1:
            alias = f"({self.base}+)[:{flag}]"
            self.flag = "+"
            self.length = flag
        else:  # pragma: no cover
            alias = str(self.base)
            self.flag = "+"
            self.length = 1
        super().__init__(mode=MatchMode.KEEP, origin=self.base.origin, alias=alias)

    def __repr__(self):
        return self.alias


class MultiKeyWordVar(MultiVar):
    base: KeyWordVar


Nargs = MultiVar
Kw = _Kw()


class KWBool(BasePattern):
    """对布尔参数的包装"""


class UnpackVar(BasePattern):
    """特殊参数，利用dataclass 的 field 生成 arg 信息，并返回dcls"""

    def __init__(self, dcls: Any, kw_only: bool = False, kw_sep: str = "="):
        """构建一个可变参数

        Args:
            dcls: dataclass 类
        """
        if not is_dataclass(dcls):
            raise TypeError(dcls)
        self.kw_only = kw_only
        self.kw_sep = kw_sep
        self.fields = fields(dcls)  # can override if other use Pydantic?
        super().__init__(mode=MatchMode.KEEP, origin=dcls, alias=f"{dcls.__name__}")  # type: ignore


class _Up:
    __slots__ = ()

    def __mul__(self, other):
        return UnpackVar(other)


Up = _Up()
