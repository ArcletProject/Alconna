"""Alconna 参数相关"""
from typing import TypeVar, Iterator, runtime_checkable, Protocol, Union, Any, Literal, Optional
from nepattern import BasePattern

DataUnit = TypeVar("DataUnit", covariant=True)


@runtime_checkable
class DataCollection(Protocol[DataUnit]):
    """数据集合协议"""

    def __repr__(self) -> str: ...

    def __iter__(self) -> Iterator[DataUnit]: ...

    def __len__(self) -> int: ...


TDataCollection = TypeVar("TDataCollection", bound=DataCollection[Union[str, Any]])


class MultiArg(BasePattern):
    """对可变参数的匹配"""
    flag: str
    array_length: Optional[int]

    def __init__(self, base: BasePattern, flag: Literal['args', 'kwargs'] = 'args', length: Optional[int] = None):
        self.flag = flag
        self.array_length = length
        if flag == 'args':
            alias = f"*({base})[:{length}]" if length else f"*({base})"
        else:
            alias = f"**{{{base}}}[:{length}]" if length else f"**{{{base}}}"
        super().__init__(
            base.pattern, base.model, base.origin, base.converter, alias, base.previous, base.accepts, base.validators
        )

    def __repr__(self):
        return self.alias


__all__ = [
    "DataCollection", "TDataCollection", "MultiArg"
]
