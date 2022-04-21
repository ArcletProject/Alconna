import asyncio
import inspect
from asyncio.queues import Queue
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional, Union, Callable, Dict, AsyncIterator, Coroutine, Tuple, TypeVar, Generic
from .main import Alconna
from .arpamar import Arpamar
from .manager import command_manager
from .builtin.actions import help_manager
from .lang_config import lang_config


@lru_cache(4096)
def iscoroutinefunction(o):
    return inspect.iscoroutinefunction(o)


async def run_always_await(callable_target, *args, **kwargs):
    if iscoroutinefunction(callable_target):
        return await callable_target(*args, **kwargs)
    return callable_target(*args, **kwargs)


T_Origin = TypeVar('T_Origin')
T_Source = TypeVar('T_Source')


@dataclass
class AlconnaProperty(Generic[T_Origin, T_Source]):
    """对解析结果的封装"""
    origin: T_Origin
    result: Arpamar
    help_text: Optional[str] = field(default=None)
    source: T_Source = field(default=None)


class AlconnaMessageProxy(Generic[T_Origin, T_Source]):
    """消息解析的代理"""
    loop: asyncio.AbstractEventLoop
    export_results: Queue
    pre_treatments: Dict[
        Alconna,
        Callable[
            [T_Origin, Arpamar, Optional[str], Optional[T_Source]], AlconnaProperty[T_Origin, T_Source]
        ]
    ]

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.loop = loop or asyncio.get_event_loop()
        self.pre_treatments = {}
        self.export_results = Queue()
        self.default_pre_treatment = lambda o, r, h, s: AlconnaProperty(o, r, h, s)

    def register_middleware(self, middleware: Callable[
            [T_Origin, Arpamar, Optional[str], Optional[T_Source]],
            AlconnaProperty[T_Origin, T_Source]
    ]):
        self.default_pre_treatment = middleware

    def add_proxy(
            self,
            command: Union[str, Alconna],
            pre_treatment: Optional[
                Callable[
                    [T_Origin, Arpamar, Optional[str], Optional[T_Source]],
                    Union[
                        AlconnaProperty[T_Origin, T_Source],
                        Coroutine[None, None, AlconnaProperty[T_Origin, T_Source]]
                    ]
                ]
            ] = None,
    ):
        if isinstance(command, str):
            command = command_manager.get_command(command)  # type: ignore
            if not command:
                raise ValueError(lang_config.manager_undefined_command.format(target=command))
        self.pre_treatments.setdefault(command, pre_treatment or self.default_pre_treatment)  # type: ignore

    async def fetch_message(self) -> AsyncIterator[Tuple[T_Origin, T_Source]]:
        """主动拉取消息"""
        yield NotImplemented
        raise NotImplementedError
    # 改为middleware
    # @staticmethod
    # def later_condition(result: AlconnaProperty[T_Origin, T_Source]) -> bool:
    #     if not result.result.matched and not result.help_text:
    #         return False
    #     return True

    async def push_message(
            self,
            message: T_Origin,
            source: Optional[T_Source] = None,
            command: Optional[Alconna] = None,
    ):
        async def __exec(_command, _treatment):
            may_help_text = None

            def _h(string):
                nonlocal may_help_text
                may_help_text = string

            help_manager.require_send_action(_h, _command.name)

            _res = _command.parse(message)
            _property = await run_always_await(_treatment, message, _res, may_help_text, source)
            await self.export_results.put(_property)

        if command and command in self.pre_treatments:
            await __exec(command, self.pre_treatments[command])
        else:
            for command, treatment in self.pre_treatments.items():
                await __exec(command, treatment)

    async def run(self):
        async for message, source in self.fetch_message():
            await self.push_message(message, source)

    def run_blocking(self):
        self.loop.run_until_complete(self.run())
