"""Alconna 负责记录命令的部分"""

from __future__ import annotations

import contextlib
import re
import shelve
import weakref
from copy import copy
from datetime import datetime
from typing import TYPE_CHECKING, Any, Generic, Match, TypedDict, Union, overload
from weakref import WeakKeyDictionary, WeakValueDictionary

from tarina import LRU, lang
from typing_extensions import NotRequired

from .argv import Argv, __argv_type__
from .arparma import Arparma
from .config import Namespace, config
from .exceptions import ExceedMaxCount
from .typing import TDC, CommandMeta, DataCollection

if TYPE_CHECKING:
    from ._internal._analyser import Analyser
    from .core import Alconna


    class ShortcutArgs(TypedDict, Generic[TDC]):
        """快捷指令参数"""

        command: NotRequired[TDC]
        """快捷指令的命令"""
        args: NotRequired[list[Any]]
        """快捷指令的附带参数"""
        fuzzy: NotRequired[bool]
        """是否允许命令后随参数"""
else:
    class ShortcutArgs(TypedDict):
        """快捷指令参数"""

        command: NotRequired[DataCollection[Any]]
        """快捷指令的命令"""
        args: NotRequired[list[Any]]
        """快捷指令的附带参数"""
        fuzzy: NotRequired[bool]
        """是否允许命令后随参数"""


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
    __abandons: list[Alconna]
    __record: LRU[int, Arparma]
    __shortcuts: dict[str, Union[Arparma, ShortcutArgs]]

    def __init__(self):
        self.cache_path = f"{__file__.replace('manager.py', '')}manager_cache.db"
        self.sign = "ALCONNA::"
        self.max_count = config.command_max_count
        self.current_count = 0

        self.__commands = {}
        self.__argv = WeakKeyDictionary()
        self.__analysers = WeakKeyDictionary()
        self.__abandons = []
        self.__shortcuts = {}
        self.__record = LRU(128)

        def _del():
            self.__commands.clear()
            for ana in self.__analysers.values():
                ana._clr()
            self.__analysers.clear()
            self.__abandons.clear()
            for arp in self.__record.values():
                arp._clr()
            self.__record.clear()
            self.__shortcuts.clear()

        weakref.finalize(self, _del)

    def load_cache(self) -> None:
        """加载缓存"""
        with contextlib.suppress(FileNotFoundError, KeyError):
            with shelve.open(self.cache_path) as db:
                self.__shortcuts = dict(db["shortcuts"])  # type: ignore

    def dump_cache(self) -> None:
        """保存缓存"""
        with shelve.open(self.cache_path) as db:
            db["shortcuts"] = self.__shortcuts

    @property
    def get_loaded_namespaces(self):
        """获取所有命名空间

        Returns:
            list[str]: 所有命名空间的名称
        """
        return list(self.__commands.keys())

    @staticmethod
    def _command_part(command: str) -> tuple[str, str]:
        """获取命令的组成部分"""
        command_parts = command.split("::", maxsplit=1)[-2:]
        if len(command_parts) != 2:
            command_parts.insert(0, config.default_namespace.name)
        return command_parts[0], command_parts[1]

    def get_namespace_config(self, name: str) -> Namespace | None:
        if name not in self.__commands:
            return
        return config.namespaces.get(name)

    def register(self, command: Alconna) -> None:
        """注册命令解析器, 会同时记录解析器对应的命令"""
        if self.current_count >= self.max_count:
            raise ExceedMaxCount
        self.__argv.pop(command, None)
        self.__argv[command] = __argv_type__.get()(
            command.namespace_config,  # type: ignore
            fuzzy_match=command.meta.fuzzy_match,  # type: ignore
            to_text=command.namespace_config.to_text,  # type: ignore
            converter=command.namespace_config.converter,  # type: ignore
            separators=command.separators,  # type: ignore
            message_cache=command.namespace_config.enable_message_cache,  # type: ignore
            filter_crlf=not command.meta.keep_crlf,  # type: ignore
        )
        self.__analysers.pop(command, None)
        self.__analysers[command] = command.compile(None)
        namespace = self.__commands.setdefault(command.namespace, WeakValueDictionary())
        if _cmd := namespace.get(command.name):
            if _cmd == command:
                return
            _cmd.formatter.add(command)
            command.formatter = _cmd.formatter
        else:
            command.formatter.add(command)
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
            base.formatter.remove(base)
            del self.__argv[base]
            del self.__analysers[base]
            del self.__commands[namespace][name]
            self.current_count -= 1
        except KeyError:
            if self.__commands.get(namespace) == {}:
                del self.__commands[namespace]

    def is_disable(self, command: Alconna) -> bool:
        """判断命令是否被禁用"""
        return command in self.__abandons

    def set_enabled(self, command: Alconna | str, enabled: bool):
        """设置命令是否被禁用"""
        if isinstance(command, str):
            command = self.get_command(command)
        if enabled and command in self.__abandons:
            self.__abandons.remove(command)
        if not enabled and command not in self.__abandons:
            self.__abandons.append(command)

    def add_shortcut(self, target: Alconna[TDC], key: str, source: Arparma | ShortcutArgs[TDC]):
        """添加快捷命令

        Args:
            target (Alconna): 目标命令
            key (str): 快捷命令的名称
            source (Arparma | ShortcutArgs): 快捷命令的参数
        """
        namespace, name = self._command_part(target.path)
        argv = self.resolve(target)
        if isinstance(source, dict):
            source['command'] = source.get('command', argv.converter(target.command or target.name))
            source.setdefault('fuzzy', True)
            self.__shortcuts[f"{namespace}.{name}::{key}"] = source
        elif source.matched:
            self.__shortcuts[f"{namespace}.{name}::{key}"] = source
        else:
            raise ValueError(lang.require("manager", "incorrect_shortcut").format(target=f"{key}"))

    @overload
    def find_shortcut(
        self, target: Alconna[TDC]
    ) -> list[Union[Arparma[TDC], ShortcutArgs[TDC]]]:
        ...

    @overload
    def find_shortcut(
        self, target: Alconna[TDC], query: str
    ) -> tuple[Arparma[TDC] | ShortcutArgs[TDC], Match[str] | None]:
        ...

    def find_shortcut(self, target: Alconna[TDC], query: str | None = None):
        """查找快捷命令

        Args:
            target (Alconna): 目标命令
            query (str, optional): 快捷命令的名称. Defaults to None.

        Returns:
            list[Union[Arparma, ShortcutArgs]] | tuple[Union[Arparma, ShortcutArgs], Match[str]]: \
            快捷命令的参数, 若没有 `query` 则返回目标命令的所有快捷命令, 否则返回匹配的快捷命令
        """
        namespace, name = self._command_part(target.path)
        if query:
            try:
                return self.__shortcuts[f"{namespace}.{name}::{query}"], None
            except KeyError as e:
                for k in self.__shortcuts:
                    prefix, key = k.rsplit("::", 1)
                    if f"{namespace}.{name}" == prefix and (mat := re.match(key, query)):
                        return self.__shortcuts[k], mat
                raise ValueError(
                    lang.require("manager", "target_command_error").format(target=f"{namespace}.{name}", shortcut=query)
                ) from e
        return [self.__shortcuts[k] for k in self.__shortcuts if f"{namespace}.{name}" in k]

    def delete_shortcut(self, target: Alconna, key: str | None = None):
        """删除快捷命令"""
        for res in [self.find_shortcut(target, key)[0]] if key else self.find_shortcut(target):
            with contextlib.suppress(StopIteration):
                self.__shortcuts.pop(next(filter(lambda x: self.__shortcuts[x] == res, self.__shortcuts)))

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

    def test(self, message: TDC, namespace: str | Namespace = '') -> Arparma[TDC] | None:
        """将一段命令给当前空间内的所有命令测试匹配"""
        for cmd in self.get_commands(namespace):
            if (res := cmd.parse(message)) and res.matched:
                return res

    def broadcast(self, message: TDC, namespace: str | Namespace = '') -> WeakValueDictionary[str, Arparma[TDC]]:
        """将一段命令给当前空间内的所有命令测试匹配"""
        data = WeakValueDictionary()
        for cmd in self.get_commands(namespace):
            if (res := cmd.parse(message)) and res.matched:
                data[cmd.path] = res
        return data

    def all_command_help(
        self,
        show_index: bool = False,
        namespace: str | Namespace | None = None,
        header: str | None = None,
        pages: str | None = None,
        footer: str | None = None,
        max_length: int = -1,
        page: int = 1
    ) -> str:
        """
        获取所有命令的帮助信息

        Args:
            show_index (bool, optional): 是否展示索引. Defaults to False.
            namespace (str | Namespace | None, optional): 指定的命名空间, 如果为None则选择所有命令.
            header (str | None, optional): 帮助信息的页眉.
            pages (str | None, optional): 帮助信息的页码.
            footer (str | None, optional): 帮助信息的页脚.
            max_length (int, optional): 单个页面展示的最大长度. Defaults to -1.
            page (int, optional): 当前页码. Defaults to 1.
        """
        pages = pages or lang.require("manager", "help_pages")
        cmds = list(filter(lambda x: not x.meta.hide, self.get_commands(namespace or '')))
        header = header or lang.require("manager", "help_header")
        if max_length < 1:
            command_string = "\n".join(
                f" {str(index).rjust(len(str(len(cmds))), '0')} {slot.name} : {slot.meta.description}"
                for index, slot in enumerate(cmds)
            ) if show_index else "\n".join(
                f" - {cmd.name} : {cmd.meta.description}"
                for cmd in cmds
            )
        else:
            max_page = len(cmds) // max_length + 1
            if page < 1 or page > max_page:
                page = 1
            header += "\t" + pages.format(current=page, total=max_page)
            command_string = "\n".join(
                f" {str(index).rjust(len(str(page * max_length)), '0')} {cmd.name} : {cmd.meta.description}"
                for index, cmd in enumerate(
                    cmds[(page - 1) * max_length: page * max_length], start=(page - 1) * max_length
                )
            ) if show_index else "\n".join(
                f" - {cmd.name} : {cmd.meta.description}"
                for cmd in cmds[(page - 1) * max_length: page * max_length]
            )
        help_names = set()
        for i in cmds:
            help_names.update(i.namespace_config.builtin_option_name['help'])
        footer = footer or lang.require("manager", "help_footer").format(help="|".join(help_names))
        return f"{header}\n{command_string}\n{footer}"

    def all_command_raw_help(self, namespace: str | Namespace | None = None) -> dict[str, CommandMeta]:
        """获取所有命令的原始帮助信息"""
        cmds = list(filter(lambda x: not x.meta.hide, self.get_commands(namespace or '')))
        return {cmd.path: copy(cmd.meta) for cmd in cmds}

    def command_help(self, command: str) -> str | None:
        """获取单个命令的帮助"""
        if cmd := self.get_command(command):
            return cmd.get_help()

    def record(self, token: int, result: Arparma):
        """记录某个命令的 `token`"""
        self.__record[token] = result

    def get_record(self, token: int) -> Arparma | None:
        """获取某个 `token` 对应的 `Arparma` 对象"""
        if token in self.__record:
            return self.__record[token]

    def get_token(self, result: Arparma) -> int:
        """获取某个命令的 `token`"""
        return next((token for token, res in self.__record.items() if res == result), 0)

    def get_result(self, command: Alconna) -> list[Arparma]:
        """获取某个命令的所有 `Arparma` 对象"""
        return [v for v in self.__record.values() if v.source == command]

    @property
    def recent_message(self) -> DataCollection[str | Any] | None:
        """获取最近一次使用的命令"""
        if rct := self.__record.peek_first_item():
            return rct[1].origin  # type: ignore

    @property
    def last_using(self):
        """获取最近一次使用的 `Alconna` 对象"""
        if rct := self.__record.peek_first_item():
            return rct[1].source  # type: ignore

    @property
    def records(self) -> LRU[int, Arparma]:
        """获取当前记录"""
        return self.__record

    def reuse(self, index: int = -1):
        """获取当前记录中的某个值"""
        key = self.__record.keys()[index]
        return self.__record[key]

    def set_record_size(self, size: int):
        """设置记录的最大长度"""
        self.__record.set_size(size)

    def __repr__(self):
        return (
            f"Current: {hex(id(self))} in {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}\n" +
            "Commands:\n" +
            f"[{', '.join([cmd.path for cmd in self.get_commands()])}]" +
            "\nShortcuts:\n" +
            "\n".join([f" {k} => {v}" for k, v in self.__shortcuts.items()]) +
            "\nRecords:\n" +
            "\n".join([f" [{k}]: {v[1].origin}" for k, v in enumerate(self.__record.items()[:20])]) +
            "\nDisabled Commands:\n" +
            f"[{', '.join(map(lambda x: x.path, self.__abandons))}]"
        )


command_manager = CommandManager()
__all__ = ["ShortcutArgs", "command_manager"]
