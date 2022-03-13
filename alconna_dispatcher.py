from typing import Literal, Dict, Callable, Optional, Coroutine, Union, AsyncIterator
import asyncio

from arclet.alconna.arpamar import Arpamar
from arclet.alconna import Alconna
from arclet.alconna.proxy import AlconnaMessageProxy, AlconnaProperty
from arclet.alconna.manager import command_manager

from graia.broadcast.entities.event import Dispatchable
from graia.broadcast.exceptions import ExecutionStop
from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.interfaces.dispatcher import DispatcherInterface
from graia.broadcast.utilles import run_always_await_safely

from graia.ariadne import get_running
from graia.ariadne.app import Ariadne
from graia.ariadne.dispatcher import ContextDispatcher
from graia.ariadne.event.message import GroupMessage, MessageEvent
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.util import resolve_dispatchers_mixin


class AriadneAMP(AlconnaMessageProxy):
    pre_treatments: Dict[Alconna, Callable[[MessageChain, Arpamar, Optional[str]], AlconnaProperty]]

    def add_proxy(
            self,
            command: Union[str, Alconna],
            pre_treatment: Optional[
                Callable[[MessageChain, Arpamar, Optional[str]], Coroutine[None, None, AlconnaProperty]]
            ] = None,
    ):
        if isinstance(command, str):
            command = command_manager.get_command(command)
        self.pre_treatments.setdefault(command, pre_treatment or self.default_pre_treatment)

    async def fetch_message(self) -> AsyncIterator[MessageChain]:
        pass


class AlconnaHelpDispatcher(BaseDispatcher):
    mixin = [ContextDispatcher]

    def __init__(self, alconna: "Alconna", help_string: str, source_event: MessageEvent):
        self.command = alconna
        self.help_string = help_string
        self.source_event = source_event

    async def catch(self, interface: "DispatcherInterface"):
        if interface.name == "help_string" and interface.annotation == str:
            return self.help_string
        if isinstance(interface.annotation, Alconna):
            return self.command
        if issubclass(interface.annotation, MessageEvent) or interface.annotation == MessageEvent:
            return self.source_event


class AlconnaHelpMessage(Dispatchable):
    """
    Alconna帮助信息发送事件
    如果触发的某个命令的帮助选项, 当AlconnaDisptcher的reply_help为False时, 会发送该事件
    """

    command: "Alconna"
    """命令"""

    help_string: str
    """帮助信息"""

    source_event: MessageEvent
    """来源事件"""


class AlconnaDispatcher(BaseDispatcher):
    proxy = AriadneAMP(loop=asyncio.get_event_loop())

    def __init__(
            self,
            *,
            alconna: "Alconna",
            help_flag: Literal["reply", "post", "stay"] = "stay",
            skip_for_unmatch: bool = True,
            help_handler: Optional[Callable[[str], MessageChain]] = None,
    ):
        """
        构造 Alconna调度器
        Args:
            alconna (Alconna): Alconna实例
            help_flag ("reply", "post", "stay"): 帮助信息发送方式
            skip_for_unmatch (bool): 当指令匹配失败时是否跳过对应的事件监听器, 默认为 True
        """
        super().__init__()
        self.command = alconna
        self.help_flag = help_flag
        self.skip_for_unmatch = skip_for_unmatch
        self.help_handler = help_handler or (lambda x: MessageChain.create(x))

    async def beforeExecution(self, interface: DispatcherInterface):
        event: MessageEvent = interface.event
        app: Ariadne = get_running()

        async def reply_help_message(
                origin: MessageChain,
                result: Arpamar,
                help_text: Optional[str] = None
        ):

            if result.matched is False and help_text:
                if self.help_flag == "reply":
                    help_text = await run_always_await_safely(self.help_handler, help_text)
                    if isinstance(event, GroupMessage):
                        await app.sendGroupMessage(event.sender.group, help_text)
                    else:
                        await app.sendMessage(event.sender, help_text)
                    return AlconnaProperty(origin, result, None)
                if self.help_flag == "post":
                    dispatchers = resolve_dispatchers_mixin(
                        [AlconnaHelpDispatcher(self.command, help_text, event), event.Dispatcher]
                    )
                    for listener in interface.broadcast.default_listener_generator(AlconnaHelpMessage):
                        await interface.broadcast.Executor(listener, dispatchers=dispatchers)
                    return AlconnaProperty(origin, result, None)
            return AlconnaProperty(origin, result, help_text)

        message = await interface.lookup_param("message", MessageChain, None)
        self.proxy.add_proxy(self.command, reply_help_message)
        self.proxy.push_message(message)

    async def catch(self, interface: DispatcherInterface):
        res = await self.proxy.export(self.command)
        if not res.result.matched and not res.help_text:
            if "-h" in str(res.origin):
                raise ExecutionStop
            if self.skip_for_unmatch:
                raise ExecutionStop

        if interface.annotation == AlconnaProperty:
            return res
        if interface.annotation == Arpamar:
            return res.result
