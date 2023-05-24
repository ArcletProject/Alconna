"""Alconna 负责记录命令的部分"""

from __future__ import annotations

import weakref
from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary, WeakValueDictionary

from tarina import lang

from .argv import Argv, __argv_type__
from .config import Namespace, config
from .exceptions import ExceedMaxCount
from .typing import TDC

if TYPE_CHECKING:
    from ._internal._analyser import Analyser
    from .core import Alconna


class CommandManager:
    """
    `Alconna` 命令管理器

    命令管理器负责记录命令, 存储命令, 命令行参数, 命令解析器, 快捷指令等
    """

    sign: str
    current_count: int
    max_count: int

    __commands: dict[str, WeakValueDictionary[str, Alconna]]
    __analysers: WeakKeyDictionary[Alconna, Analyser]
    __argv: WeakKeyDictionary[Alconna, Argv]

    def __init__(self):
        self.cache_path = f"{__file__.replace('manager.py', '')}manager_cache.db"
        self.sign = "ALCONNA::"
        self.max_count = config.command_max_count
        self.current_count = 0

        self.__commands = {}
        self.__argv = WeakKeyDictionary()
        self.__analysers = WeakKeyDictionary()

        def _del():
            self.__commands.clear()
            for ana in self.__analysers.values():
                ana._clr()
            self.__analysers.clear()

        weakref.finalize(self, _del)

    @staticmethod
    def _command_part(command: str) -> tuple[str, str]:
        """获取命令的组成部分"""
        command_parts = command.split("::", maxsplit=1)[-2:]
        if len(command_parts) != 2:
            command_parts.insert(0, config.default_namespace.name)
        return command_parts[0], command_parts[1]

    def register(self, command: Alconna) -> None:
        """注册命令解析器, 会同时记录解析器对应的命令"""
        if self.current_count >= self.max_count:
            raise ExceedMaxCount
        self.__argv.pop(command, None)
        self.__argv[command] = __argv_type__.get()(
            to_text=command.namespace_config.to_text,  # type: ignore
            converter=command.namespace_config.converter,  # type: ignore
            separators=command.separators,  # type: ignore
            filter_crlf=not command.meta.keep_crlf,  # type: ignore
        )
        self.__analysers.pop(command, None)
        self.__analysers[command] = command.compile(None)
        namespace = self.__commands.setdefault(command.namespace, WeakValueDictionary())
        if _cmd := namespace.get(command.name):
            if _cmd == command:
                return
        else:
            namespace[command.name] = command
            self.current_count += 1

    def resolve(self, command: Alconna[TDC]) -> Argv[TDC]:
        """获取命令解析器的参数解析器"""
        try:
            return self.__argv[command]
        except KeyError as e:
            namespace, name = self._command_part(command.path)
            raise ValueError(lang.require("manager", "undefined_command").format(target=f"{namespace}.{name}")) from e

    def require(self, command: Alconna[TDC]) -> Analyser[TDC]:
        """获取命令解析器"""
        try:
            return self.__analysers[command]  # type: ignore
        except KeyError as e:
            namespace, name = self._command_part(command.path)
            raise ValueError(lang.require("manager", "undefined_command").format(target=f"{namespace}.{name}")) from e

    def requires(self, *paths: str) -> zip[tuple[Analyser, Argv]]:  # type: ignore
        """获取多个命令解析器"""
        return zip(
            [v for k, v in self.__analysers.items() if k.path in paths],
            [v for k, v in self.__argv.items() if k.path in paths],
        )

    def delete(self, command: Alconna | str) -> None:
        """删除命令"""
        namespace, name = self._command_part(command if isinstance(command, str) else command.path)
        try:
            base = self.__commands[namespace][name]
            del self.__argv[base]
            del self.__analysers[base]
            del self.__commands[namespace][name]
            self.current_count -= 1
        except KeyError:
            if self.__commands.get(namespace) == {}:
                del self.__commands[namespace]

    def get_command(self, command: str) -> Alconna:
        """获取命令"""
        namespace, name = self._command_part(command)
        if namespace not in self.__commands or name not in self.__commands[namespace]:
            raise ValueError(command)
        return self.__commands[namespace][name]

    def get_commands(self, namespace: str | Namespace = '') -> list[Alconna]:
        """获取命令列表"""
        if not namespace:
            return list(self.__analysers.keys())
        if isinstance(namespace, Namespace):
            namespace = Namespace.name
        if namespace not in self.__commands:
            return []
        return list(self.__commands[namespace].values())


command_manager = CommandManager()
__all__ = ["command_manager"]
