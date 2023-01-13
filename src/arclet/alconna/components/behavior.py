from __future__ import annotations

from abc import ABCMeta, abstractmethod
from functools import lru_cache
from typing import TYPE_CHECKING, Any
from inspect import Signature
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from ..arparma import Arparma


@dataclass(init=True, unsafe_hash=True, repr=True)
class ArparmaBehavior(metaclass=ABCMeta):
    """
    解析结果行为器的基类, 对应一个对解析结果的操作行为
    """

    record: dict[int, dict[str, tuple[Any, Any]]] = field(default_factory=dict, init=False, repr=False, hash=False)
    """record: dict[token, dict[path, (past, current)]]"""

    requires: list[ArparmaBehavior] = field(init=False, hash=False, repr=False)
    def before_operate(self, interface: Arparma):
        if not self.record:
            return
        if not (_record := self.record.get(interface.token, None)):
            return
        for path, (past, current) in _record.items():
            source, end = interface.__require__(path.split("."))
            if source is None:
                continue
            if isinstance(source, dict):
                if past != Signature.empty:
                    source[end] = past
                elif source.get(end, Signature.empty) != current:
                    source.pop(end)
            elif past != Signature.empty:
                setattr(source, end, past)
            elif getattr(source, end, Signature.empty) != current:
                delattr(source, end)
        _record.clear()

    @abstractmethod
    def operate(self, interface: Arparma):
        ...

    def update(self, interface: Arparma, path: str, value: Any):

        def _update(tkn, src, pth, ep, val):
            _record = self.record.setdefault(tkn, {})
            if isinstance(src, dict):
                _record[pth] = (src.get(ep, Signature.empty), val)
                src[ep] = val
            else:
                _record[pth] = (getattr(src, ep, Signature.empty), val)
                setattr(src, ep, val)

        source, end = interface.__require__(path.split("."))
        if source is None:
            return
        if end:
            _update(interface.token, source, path, end, value)
        elif isinstance(value, dict):
            for k, v in value.items():
                _update(interface.token, source, f"{path}.{k}", k, v)


@lru_cache(4096)
def requirement_handler(behavior: ArparmaBehavior) -> list[ArparmaBehavior]:
    return [*getattr(behavior, 'requires', []), behavior]
