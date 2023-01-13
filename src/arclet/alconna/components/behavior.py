from __future__ import annotations

from abc import ABCMeta, abstractmethod
from functools import lru_cache
from typing import TYPE_CHECKING, Union, Type, Any
from inspect import isclass, Signature
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from ..arparma import Arparma


@dataclass(init=True, unsafe_hash=True, repr=True)
class ArparmaBehavior(metaclass=ABCMeta):
    """
    解析结果行为器的基类, 对应一个对解析结果的操作行为
    """

    record: dict[str, tuple[Any, Any]] = field(default_factory=dict, init=False, repr=False, hash=False)
    """record: dict[path, (past, current)]"""

    requires: list[type[ArparmaBehavior] | ArparmaBehavior] = field(default_factory=list, init=False, hash=False)
    def before_operate(self, interface: Arparma):
        if not self.record:
            return
        for path, (past, current) in self.record.items():
            source, end = interface.__require__(path.split("."))
            if source is None:
                continue
            if isinstance(source, dict):
                if past is Signature.empty:
                    source.pop(end, None)
                elif source.get(end, Signature.empty) != current:
                    source[end] = past
            elif getattr(source, end, Signature.empty) != current:
                setattr(source, end, past)
            else:
                delattr(source, end)
        self.record.clear()

    @abstractmethod
    def operate(self, interface: Arparma):
        ...

    def _update(self, src, pth, ep, val):
        if isinstance(src, dict):
            self.record[pth] = (src.get(ep, Signature.empty), val)
            src[ep] = val
        else:
            self.record[pth] = (getattr(src, ep, Signature.empty), val)
            setattr(src, ep, val)

    def update(self, interface: Arparma, path: str, value: Any):
        source, end = interface.__require__(path.split("."))
        if source is None:
            return
        if end:
            self._update(source, path, end, value)
        elif isinstance(value, dict):
            for k, v in value.items():
                self._update(source, f"{path}.{k}", k, v)


T_ABehavior = Union[Type["ArparmaBehavior"], "ArparmaBehavior"]


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
