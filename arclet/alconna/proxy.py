import abc
import asyncio
import inspect
from functools import lru_cache
from typing import Optional, Union, Callable, Dict, AsyncIterator, Coroutine
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


class AlconnaProperty:
    """对解析结果的封装"""
    def __init__(
            self,
            origin: Union[str, DataCollection],
            result: Arpamar,
            help_text: Optional[str] = None
    ):
        self.origin = origin
        self.result = result
        self.help_text = help_text


class AlconnaMessageProxy(metaclass=abc.ABCMeta):
    """消息解析的代理"""
    loop: asyncio.AbstractEventLoop
    export_results: Dict[Alconna, asyncio.Task]
    pre_treatments: Dict[Alconna, Callable[[Union[str, DataCollection], Arpamar, Optional[str]], AlconnaProperty]]

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.loop = loop or asyncio.get_event_loop()
        self.pre_treatments = {}
        self.export_results = {}
        self.default_pre_treatment = lambda x, y, z: AlconnaProperty(x, y, z)

    def add_proxy(
            self,
            command: Union[str, Alconna],
            pre_treatment: Optional[
                Callable[[Union[str, DataCollection], Arpamar, Optional[str]],
                         Union[AlconnaProperty, Coroutine[None, None, AlconnaProperty]]]
            ] = None,
    ):
        if isinstance(command, str):
            command = command_manager.get_command(command)
        self.pre_treatments.setdefault(command, pre_treatment or self.default_pre_treatment)

    @abc.abstractmethod
    async def fetch_message(self) -> AsyncIterator[Union[str, DataCollection]]:
        """主动拉取消息"""
        yield
        raise NotImplementedError

    def push_message(self, message: Union[str, DataCollection]):
        for command, treatment in self.pre_treatments.items():
            may_help_text = None

            def _h(string):
                nonlocal may_help_text
                may_help_text = string

            require_help_send_action(_h, command.name)

            _res = command.parse(message)
            self.export_results[command] = self.loop.create_task(
                run_always_await(treatment, message, _res, may_help_text),
                name=command.name
            )

    async def export(self, command: Union[str, Alconna]) -> AlconnaProperty:
        if isinstance(command, str):
            command = command_manager.get_command(command)
        return await self.export_results[command]

    async def run(self):
        async for message in self.fetch_message():
            self.push_message(message)

    def run_blocking(self):
        self.loop.run_until_complete(self.run())
