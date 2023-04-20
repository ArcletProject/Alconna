from arclet.alconna import (
    Alconna,
    AlconnaString,
    output_manager,
    command_manager,
    split_once,
    config
)
from arclet.letoderea.entities.subscriber import Subscriber
from arclet.letoderea.handler import await_exec_target
from typing import Callable, Dict, Type, Optional
from arclet.edoves.main.interact.module import BaseModule, ModuleMetaComponent, Component
from arclet.edoves.main.typings import TProtocol
from arclet.edoves.main.utilles.security import EDOVES_DEFAULT

from arclet.edoves.builtin.event.message import MessageReceived
from arclet.edoves.builtin.medium import Message


class CommandParser:
    command: Alconna
    param_reaction: Callable

    def __init__(self, alconna: Alconna, func: Callable):
        self.command = alconna
        self.param_reaction = Subscriber(func)

    async def exec(self, params):
        await await_exec_target(self.param_reaction, MessageReceived.param_export(**params))


class CommanderData(ModuleMetaComponent):
    verify_code: str = EDOVES_DEFAULT
    identifier = "edoves.builtin.commander"
    name = "Builtin Commander Module"
    description = "Based on Edoves and Arclet-Alconna"
    usage = """\n@commander.command("test <foo:str>")\ndef test(foo: str):\n\t..."""
    command_namespace: str
    max_command_length: int = 10


class CommandParsers(Component):
    io: "Commander"
    parsers: Dict[str, CommandParser]

    def __init__(self, io: "Commander"):
        super(CommandParsers, self).__init__(io)
        self.parsers = {}

    def command(
            self,
            command: str,
            *option: str,
            sep: str = " "
    ):
        alc = AlconnaString(command, *option, sep=sep)

        def __wrapper(func):
            cmd = CommandParser(alc, func)
            self.parsers.setdefault(alc.name, cmd)
            return command

        return __wrapper

    def shortcut(self, shortcut: str, command: str):
        name = split_once(command, " ")[0]
        cmd = self.parsers.get(name)
        if cmd is None:
            return
        cmd.command.shortcut(shortcut, command)

    def remove_handler(self, command: str):
        del self.parsers[command]


class Commander(BaseModule):
    prefab_metadata = CommanderData
    command_parsers: CommandParsers

    __slots__ = ["command_parsers"]

    def __init__(self, protocol: TProtocol, namespace: Optional[str] = None):
        super().__init__(protocol)
        self.metadata.command_namespace = namespace or protocol.current_scene.scene_name + "_Commander"
        self.command_parsers = CommandParsers(self)
        if self.local_storage.get(self.__class__):
            for k, v in self.local_storage[self.__class__].items():
                self.get_component(CommandParsers).parsers.setdefault(k, v)
        config.set_loop(self.protocol.screen.edoves.loop)

        @self.behavior.add_handlers(MessageReceived)
        async def command_message_handler(message: Message):
            async def _action(doc: str):
                await message.set(doc).send()

            for cmd, psr in self.command_parsers.parsers.items():
                output_manager.set_send_action(_action, psr.command.name)
                result = psr.command.parse(message.content)
                if result.matched:
                    await psr.exec(
                        {
                            **result.all_matched_args,
                            "result": result,
                            "message": message,
                            "sender": message.purveyor,
                            "edoves": self.protocol.screen.edoves,
                            "scene": self.protocol.current_scene
                        }
                    )
                    break

        @self.command("help <page:int:1> #显示帮助")
        async def _(message: Message, page: int):
            await message.set(command_manager.all_command_help(
                self.metadata.command_namespace,
                max_length=self.metadata.max_command_length,
                page=page
            )).send()

    def command(
            __commander_self__,
            command: str,
            *option: str,
            sep: str = " "
    ):
        alc = AlconnaString(command, *option, sep=sep).reset_namespace(
            __commander_self__.metadata.command_namespace
        )

        def __wrapper(func):
            cmd = CommandParser(alc, func)
            try:
                __commander_self__.command_parsers.parsers.setdefault(alc.prefixes[0], cmd)
            except AttributeError:
                if not __commander_self__.local_storage.get(__commander_self__.__class__):
                    __commander_self__.local_storage.setdefault(__commander_self__.__class__, {})
                __commander_self__.local_storage[__commander_self__.__class__].setdefault(alc.prefixes[0], cmd)
            return command

        return __wrapper
