from __future__ import annotations
from typing import Any

class Sentence:
    name: str
    separators: tuple[str, ...]
    def __init__(self, name: str, separators: tuple[str, ...] | None = ...) -> None: ...

class OptionResult:
    value: Any
    args: dict[str, Any]
    def __init__(self, value: Any = ..., args: dict[str, Any] | None = ...) -> None: ...

class SubcommandResult:
    value: Any
    args: dict[str, Any]
    options: dict[str, OptionResult]
    subcommands: dict[str, SubcommandResult]
    def __init__(
        self,
        value: Any = ...,
        args: dict[str, Any] | None = ...,
        options: dict[str, OptionResult] | None = ...,
        subcommands: dict[str, SubcommandResult] | None = ...
    ) -> None: ...

class HeadResult:
    origin: Any
    result: Any
    matched: bool
    groups: dict[str, str]
    def __init__(
        self, origin: Any = ..., result: Any = ..., matched: bool = ..., groups: dict[str, str] | None = ...
    ) -> None: ...
