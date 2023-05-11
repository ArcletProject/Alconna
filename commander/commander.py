from arclet.alconna import Alconna
from arclet.alconna.core import ArparmaExecutor
from dataclasses import dataclass, field
from typing import TypeVar, Callable, Any, Optional
from weakref import WeakValueDictionary

TCall = TypeVar("TCall", bound=Callable)


@dataclass
class Commands:
    executors: dict[Alconna, ArparmaExecutor] = field(default_factory=dict)

    def on(self, alc: Alconna):
        def wrapper(func: TCall) -> TCall:
            self.executors[alc] = alc.bind(False)(func)
            return func

        return wrapper

    def test(self, message: Optional[Any] = None):
        for alc, executor in self.executors.items():
            res = alc.parse(message) if message else alc()
            if res.matched:
                return executor.result

    def broadcast(self, message: Optional[Any] = None):
        data = WeakValueDictionary()
        for alc, executor in self.executors.items():
            res = alc.parse(message) if message else alc()
            if res.matched:
                data[alc.path] = executor.result
        return data
