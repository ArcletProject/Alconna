from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

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
    args: Dict[str, Any]

    def __init__(self, value: Any = Ellipsis, args: Optional[Dict[str, Any]] = None) -> None:
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

    if TYPE_CHECKING:
        value: Any
        args: Dict[str, Any]
        options: Dict[str, OptionResult]
        subcommands: Dict[str, SubcommandResult]

    def __init__(
        self,
        value: Any = Ellipsis,
        args: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, OptionResult]] = None,
        subcommands: Optional[Dict[str, SubcommandResult]] = None,
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

    if TYPE_CHECKING:
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
