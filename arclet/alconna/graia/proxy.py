from typing import Dict, Callable, Optional, Coroutine, Union, AsyncIterator, Literal, Tuple

# from graia.amnesia.message import MessageChain
from graia.ariadne import Ariadne, get_running
from graia.ariadne.dispatcher import ContextDispatcher
from graia.ariadne.util import resolve_dispatchers_mixin
from graia.broadcast import Broadcast, Dispatchable
from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.interfaces.dispatcher import DispatcherInterface
from graia.ariadne.event.message import FriendMessage, GroupMessage, MessageEvent
from graia.ariadne.message.chain import MessageChain
from arclet.alconna.arpamar import Arpamar
from arclet.alconna.proxy import AlconnaMessageProxy, AlconnaProperty, run_always_await
from arclet.alconna.manager import command_manager

from . import Alconna


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


class GraiaAlconnaPropetry(AlconnaProperty):
    origin: MessageChain

    def __init__(
            self,
            origin: MessageChain,
            result: Arpamar,
            help_text: Optional[str] = None,
            source_event: Optional[MessageEvent] = None,
    ):
        super().__init__(origin, result, help_text, source_event)


class GraiaAMP(AlconnaMessageProxy):
    pre_treatments: Dict[
        Alconna, Callable[[MessageChain, Arpamar, Optional[str], Optional[MessageEvent]],
                          Coroutine[None, None, GraiaAlconnaPropetry]
        ]
    ]

    def __init__(self, broadcast: Broadcast, skip_for_unmatch: bool = True):
        self.broadcast = broadcast
        self.skip_for_unmatch = skip_for_unmatch
        super().__init__(broadcast.loop)

        _queue = self.export_results

        @self.broadcast.prelude_dispatchers.append
        class ExportResultDispatcher(BaseDispatcher):
            @staticmethod
            async def catch(interface: DispatcherInterface):
                if interface.annotation in (GraiaAlconnaPropetry, AlconnaProperty):
                    return await _queue.get()
                if interface.annotation == Arpamar:
                    return (await _queue.get()).result

        @self.broadcast.receiver(FriendMessage, priority=8)
        async def _(event: FriendMessage):
            await self.push_message(event.messageChain, event)

        @self.broadcast.receiver(GroupMessage, priority=8)
        async def _(event: GroupMessage):
            await self.push_message(event.messageChain, event)

    def add_proxy(
            self,
            command: Union[str, Alconna],
            pre_treatment: Optional[
                Callable[
                    [MessageChain, Arpamar, Optional[str], Optional[MessageEvent]],
                    Coroutine[None, None, GraiaAlconnaPropetry]
                ]
            ] = None,
            help_flag: Literal["reply", "post", "stay"] = "stay",
            help_handler: Optional[Callable[[str], MessageChain]] = None,
    ):
        if isinstance(command, str):
            command = command_manager.get_command(command)  # type: ignore
            if not command:
                raise ValueError(f'Command {command} not found')

        async def reply_help_message(
                origin: MessageChain,
                result: Arpamar,
                help_text: Optional[str] = None,
                source: Optional[MessageEvent] = None,
        ):
            app: Ariadne = get_running()
            if result.matched is False and help_text:
                if help_flag == "reply":
                    help_text = await run_always_await(help_handler, help_text)
                    if isinstance(source, GroupMessage):
                        await app.sendGroupMessage(source.sender.group, help_text)
                    else:
                        await app.sendMessage(source.sender, help_text)
                    return GraiaAlconnaPropetry(origin, result, None, source)
                if help_flag == "post":
                    dispatchers = resolve_dispatchers_mixin(
                        [AlconnaHelpDispatcher(command, help_text, source), source.Dispatcher]
                    )
                    for listener in self.broadcast.default_listener_generator(AlconnaHelpMessage):
                        await self.broadcast.Executor(listener, dispatchers=dispatchers)
                    return GraiaAlconnaPropetry(origin, result, None, source)
            return GraiaAlconnaPropetry(origin, result, help_text, source)

        self.pre_treatments.setdefault(command, pre_treatment or reply_help_message)  # type: ignore

    async def fetch_message(self) -> AsyncIterator[Tuple[MessageChain, MessageEvent]]:
        pass

    def later_condition(self, result: AlconnaProperty) -> bool:
        if not result.result.matched and not result.help_text:
            if "-h" in str(result.origin):
                return False
            if self.skip_for_unmatch:
                return False
        return True
