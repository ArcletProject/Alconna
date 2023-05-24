"""Alconna 参数相关"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Protocol, TypeVar, runtime_checkable

DataUnit = TypeVar("DataUnit", covariant=True)


@runtime_checkable
class DataCollection(Protocol[DataUnit]):
    """数据集合协议"""
    def __repr__(self) -> str: ...
    def __iter__(self) -> Iterator[DataUnit]: ...
    def __len__(self) -> int: ...


@dataclass(unsafe_hash=True)
class CommandMeta:
    """命令元数据"""
    raise_exception: bool = field(default=False)
    "命令是否抛出异常"
    keep_crlf: bool = field(default=False)
    "命令是否保留换行字符"
    compact: bool = field(default=False)
    "命令是否允许第一个参数紧随头部"


TDC = TypeVar("TDC", bound=DataCollection[Any])


__all__ = ["DataCollection", "TDC", "CommandMeta"]
