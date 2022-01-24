from typing import Dict, Callable, Type
from arclet.cesloi.event.messages import Message, MessageChain
from arclet.alconna import Alconna
from arclet.letoderea import EventSystem
from arclet.letoderea.handler import await_exec_target
from arclet.cesloi.event.messages import FriendMessage
from arclet.cesloi.model.relation import Friend
import asyncio


class CommandParser:
    alconna: Alconna
    param_reaction: Callable

    def __init__(self, alconna, func: Callable):
        self.alconna = alconna
        self.param_reaction = func

    async def exec(self, all_args):
        await await_exec_target(self.param_reaction, all_args)


class Commander:
    command_parsers: Dict[str, CommandParser]
    event_system: EventSystem

    def __init__(self, event_system):
        self.event_system = event_system
        self.command_parsers = {}
        self._init_subscriber()

    def command(
            self,
            command: str,
            *option: str,
            custom_types: Dict[str, Type] = None,
            sep: str = " "
    ):
        alc = Alconna.from_string(command, *option, custom_types=custom_types, sep=sep)

        def __wrapper(func):
            cmd = CommandParser(alc, func)
            self.command_parsers.setdefault(alc.command, cmd)
            return command

        return __wrapper

    def _init_subscriber(self):
        @self.event_system.register(Message)
        async def command_handler(message: MessageChain):
            for k, v in self.command_parsers.items():
                result = v.alconna.analyse_message(message)
                if result.matched:
                    await v.exec(result.all_matched_args)
                    break


es = EventSystem()
commander = Commander(es)


@commander.command("test", "--name <pak>", "--foo <bar:bool>")
async def _(pak: str, bar: str):
    print(pak)
    print(bar)


friend = Friend(id=3165388245, nickname="RF")
msg = MessageChain.create("test --name ces --foo True")
fri_msg = FriendMessage(messageChain=msg, sender=friend)


async def main():
    es.event_spread(fri_msg)
    await asyncio.sleep(0.1)


es.loop.run_until_complete(main())
