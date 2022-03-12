import abc
import asyncio
import inspect
from functools import lru_cache
from typing import Optional, Union, Callable, Any, Dict, AsyncIterator
from .types import DataCollection
from .main import Alconna
from .arpamar import Arpamar
from .manager import command_manager
from .builtin.actions import require_help_send_action


@lru_cache(4096)
def iscoroutinefunction(o):
    return inspect.iscoroutinefunction(o)


async def run_always_await(callable_target, *args, **kwargs):
    if iscoroutinefunction(callable_target):
        return await callable_target(*args, **kwargs)
    return callable_target(*args, **kwargs)


class ProxyResult:
    def __init__(self, result: Arpamar, help_text: Optional[Any] = None):
        self.result = result
        self.help_text = help_text


class AlconnaMessageProxy(metaclass=abc.ABCMeta):
    interval: float = 0.1
    loop: asyncio.AbstractEventLoop
    __handlers: Dict[Alconna, Callable[..., Any]]
    __pre_treatments: Dict[Alconna, Callable[[Arpamar, Optional[str]], ProxyResult]]

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.loop = loop or asyncio.get_event_loop()
        self.__handlers = {}
        self.__pre_conditions = None
        self.__suppliers = {}
        self.__default_pre_treatment = lambda x, y: ProxyResult(x, y)

    def add_proxy(
            self, command: Union[str, Alconna],
            handler: Callable[..., Any],
            pre_treatment: Optional[Callable[[Arpamar, Optional[str]], ProxyResult]] = None,
    ):
        if isinstance(command, str):
            command = command_manager.get_command(command)
        self.__handlers[command] = handler
        self.__pre_treatments[command] = pre_treatment or self.__default_pre_treatment

    def add_prelude_supplier(
            self,
            **suppliers
    ):
        def __wrapper(func):
            self.__suppliers.update(suppliers)
            self.__pre_conditions = func
            return func
        return __wrapper

    @abc.abstractmethod
    async def fetch_message(self) -> AsyncIterator[Union[str, DataCollection]]:
        """主动拉取消息"""
        yield
        raise NotImplementedError

    async def push_message(self, message: Union[str, DataCollection]):
        tasks = []
        for command, handler in self.__handlers.items():
            pass
        await asyncio.gather(*tasks)

    async def run(self):
        async for message in self.fetch_message():
            await self.push_message(message)

    def run_blocking(self):
        self.loop.run_until_complete(self.run())
