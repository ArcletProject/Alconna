from __future__ import annotations

from abc import ABCMeta, abstractmethod
from functools import lru_cache
from typing import TYPE_CHECKING, Union, Type, Any
from inspect import isclass
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from ..arparma import Arparma


@dataclass(init=True, unsafe_hash=True, repr=True)
class ArparmaBehavior(metaclass=ABCMeta):
    """
    解析结果行为器的基类, 对应一个对解析结果的操作行为
    """

    record: dict[str, tuple[Any, Any]] = field(default_factory=dict, init=False, repr=False, hash=False)
    requires: list[type[ArparmaBehavior] | ArparmaBehavior] = field(default_factory=list, init=False, hash=False)

    def before_operate(self, interface: Arparma):
        ...
    @abstractmethod
    def operate(self, interface: Arparma):
        ...

    def update(self, interface: Arparma, path: str, value: Any):
        ...


T_ABehavior = Union[Type['ArparmaBehavior'], 'ArparmaBehavior']


@lru_cache(4096)
def requirement_handler(behavior: T_ABehavior) -> list[ArparmaBehavior]:
    unbound_mixin = getattr(behavior, "requires", [])
    result: list[T_ABehavior] = []
    for i in unbound_mixin:
        result.extend(requirement_handler(i))
    if isclass(behavior):
        result.append(behavior())
    else:
        result.append(behavior)
    return result
