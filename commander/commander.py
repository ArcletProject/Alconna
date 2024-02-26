from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Tuple, TypeVar
from weakref import WeakKeyDictionary

from tarina import is_awaitable

from arclet.alconna import Alconna, Arparma
from arclet.alconna.core import ArparmaExecutor

TCall = TypeVar("TCall", bound=Callable)


@dataclass
class Commands:
    executors: WeakKeyDictionary[Alconna, Tuple[ArparmaExecutor, bool]] = field(default_factory=WeakKeyDictionary)

    def __post_init__(self):
        Arparma.addition(commander=lambda: self)

    def on(self, alc: Alconna, block: bool = True):
        def wrapper(func: TCall) -> TCall:
            self.executors[alc] = (alc.bind(False)(func), block)
            return func

        return wrapper

    async def broadcast(self, message: Optional[Any] = None):
        data = {}
        for alc, (executor, block) in self.executors.items():
            arp = alc.parse(message) if message else alc()
            if arp.matched:
                res = executor.result
                data[alc.path] = (await res) if is_awaitable(res) else res
                if block:
                    break
        return data
