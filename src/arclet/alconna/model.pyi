from __future__ import annotations

from typing import Any

from nepattern import BasePattern

class Sentence:
    """句段

    句段由 `Analyser` 编译而来, 代表选项或者子命令的需求前缀。

    Attributes:
        name (str): 句段名称
    """

    name: str
    def __init__(self, name: str) -> None: ...

class OptionResult:
    """选项解析结果

    Attributes:
        value (Any): 选项值
        args (dict[str, Any]): 选项参数解析结果
    """

    value: Any
    args: dict[str, Any]
    def __init__(self, value: Any = ..., args: dict[str, Any] | None = ...) -> None: ...

class SubcommandResult:
    """子命令解析结果

    Attributes:
        value (Any): 子命令值
        args (dict[str, Any]): 子命令参数解析结果
        options (dict[str, OptionResult]): 子命令的子选项解析结果
        subcommands (dict[str, SubcommandResult]): 子命令的子子命令解析结果
    """

    value: Any
    args: dict[str, Any]
    options: dict[str, OptionResult]
    subcommands: dict[str, SubcommandResult]
    def __init__(
        self,
        value: Any = ...,
        args: dict[str, Any] | None = ...,
        options: dict[str, OptionResult] | None = ...,
        subcommands: dict[str, SubcommandResult] | None = ...,
    ) -> None: ...

class HeadResult:
    """命令头解析结果

    Attributes:
        origin (Any): 命令头原始值
        result (Any): 命令头解析结果
        matched (bool): 命令头是否匹配
        groups (dict[str, Any]): 命令头匹配组
    """

    origin: Any
    result: Any
    matched: bool
    groups: dict[str, Any]
    def __init__(
        self,
        origin: Any = ...,
        result: Any = ...,
        matched: bool = ...,
        groups: dict[str, str] | None = ...,
        fixes: dict[str, BasePattern] | None = ...,
    ) -> None: ...
