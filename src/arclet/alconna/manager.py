"""Alconna 负责记录命令的部分"""

from __future__ import annotations

import contextlib
import re
import shelve
import weakref
from copy import copy
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Match
from weakref import WeakValueDictionary

from nepattern import TPattern
from tarina import LRU, lang

from .arparma import Arparma
from .base import Header, Metadata
from .config import Namespace, global_config
from .exceptions import ExceedMaxCount
from .typing import TDC, DataCollection
from .shortcut import InnerShortcutArgs, ShortcutArgs, find_shortcut as _find_shortcut

if TYPE_CHECKING:
    from .ingedia._analyser import Analyser
    from .core import Alconna


class CommandManager:
    """
    `Alconna` 命令管理器

    命令管理器负责记录命令, 存储命令, 命令行参数, 命令解析器, 快捷指令等
    """

    sign: str
    current_count: int

    @property
    def max_count(self) -> int:
        return global_config.command_max_count

    __analysers: dict[int, Analyser]
    __abandons: list[int]
    __record: LRU[int, Arparma]
    _shortcuts: dict[str, tuple[dict[str, InnerShortcutArgs], dict[str, InnerShortcutArgs]]]

    def __init__(self):
        self.sign = "ALCONNA::"
        self.current_count = 0

        self.__analysers = {}
        self.__abandons = []
        self._shortcuts = {}
        self.__record = LRU(128)

        def _del():
            for ana in self.__analysers.values():
                ana._clr()
            self.__analysers.clear()
            self.__abandons.clear()
            for arp in self.__record.values():
                arp._clr()
            self.__record.clear()
            self._shortcuts.clear()

        weakref.finalize(self, _del)

    def load_shortcuts(self, file: str | Path | None = None) -> None:
        """加载缓存"""
        path = Path(file or (Path.cwd() / "shortcut.db"))
        with contextlib.suppress(FileNotFoundError, KeyError):
            with shelve.open(path.resolve().as_posix()) as db:
                data: dict[str, tuple[dict, dict]] = dict(db["shortcuts"])  # type: ignore
            for cmd, shorts in data.items():
                _data = self._shortcuts.setdefault(cmd, ({}, {}))
                for key, short in shorts[0].items():
                    if isinstance(short, dict):
                        _data[0][key] = InnerShortcutArgs.load(short)
                    else:
                        _data[0][key] = short
                for key, short in shorts[1].items():
                    if isinstance(short, dict):
                        _data[1][key] = InnerShortcutArgs.load(short)
                    else:
                        _data[1][key] = short

    load_cache = load_shortcuts

    def dump_shortcuts(self, file: str | Path | None = None) -> None:
        """保存缓存"""
        data = {}
        for cmd, shorts in self._shortcuts.items():
            _data = data.setdefault(cmd, ({}, {}))
            for key, short in shorts[0].items():
                if isinstance(short, InnerShortcutArgs):
                    _data[0][key] = short.dump()
                else:
                    _data[0][key] = short
            for key, short in shorts[1].items():
                if isinstance(short, InnerShortcutArgs):
                    _data[1][key] = short.dump()
                else:
                    _data[1][key] = short
        path = Path(file or (Path.cwd() / "shortcut.db"))
        with shelve.open(path.resolve().as_posix()) as db:
            db["shortcuts"] = data
        data.clear()

    dump_cache = dump_shortcuts

    @staticmethod
    def _command_part(command: str) -> tuple[str, str]:
        """获取命令的组成部分"""
        command_parts = command.split("::", maxsplit=1)[-2:]
        if len(command_parts) != 2:
            command_parts.insert(0, global_config.default_namespace.name)
        return command_parts[0], command_parts[1]

    def register(self, command: Alconna) -> None:
        """注册命令解析器, 会同时记录解析器对应的命令"""
        if self.current_count >= self.max_count:
            raise ExceedMaxCount
        cmd_hash = command._hash
        self.__analysers.pop(cmd_hash, None)
        self.__analysers[cmd_hash] = command.compile()

    def _resolve(self, cmd_hash: int) -> Alconna:
        return self.__analysers[cmd_hash].command

    def require(self, command: Alconna) -> Analyser:
        """获取命令解析器"""
        cmd_hash = command._hash
        try:
            return self.__analysers[cmd_hash]  # type: ignore
        except KeyError as e:
            namespace, name = self._command_part(command.path)
            raise ValueError(lang.require("manager", "undefined_command").format(target=f"{namespace}.{name}")) from e

    def delete(self, command: Alconna) -> None:
        """删除命令"""
        cmd_hash = command._hash
        try:
            command.formatter.remove(command)
            del self.__analysers[cmd_hash]
            self.current_count -= 1
        except KeyError:
            pass

    @contextlib.contextmanager
    def update(self, command: Alconna):
        """同步命令更改"""
        cmd_hash = command._hash
        if cmd_hash not in self.__analysers:
            raise ValueError(lang.require("manager", "undefined_command").format(target=command.path))
        self.clear_result(command)
        command.formatter.remove(command)
        del self.__analysers[cmd_hash]
        yield
        command._header = Header.generate(command.command, command.prefixes, bool(command.config.compact))
        name = next(iter(command._header.content), command.command or command.prefixes[0])
        command.path = f"{command.namespace}::{name}"
        command.dest = command.name = name
        command.aliases = frozenset(command._header.content)
        cmd_hash = command._hash = command._calc_hash()
        self.__analysers[cmd_hash] = command.compile()
        command.formatter.add(command)

    def is_disable(self, command: Alconna) -> bool:
        """判断命令是否被禁用"""
        return command._hash in self.__abandons

    def set_enabled(self, command: Alconna | str, enabled: bool):
        """设置命令是否被禁用"""
        if isinstance(command, str):
            command = self.get_command(command)
        if enabled and command._hash in self.__abandons:
            self.__abandons.remove(command._hash)
        if not enabled and command not in self.__abandons:
            self.__abandons.append(command._hash)

    def add_shortcut(self, target: Alconna, key: str | TPattern, source: ShortcutArgs):
        """添加快捷命令

        Args:
            target (Alconna): 目标命令
            key (str): 快捷命令的名称
            source (ShortcutArgs): 快捷命令的参数
        """
        namespace, name = self._command_part(target.path)
        argv = self.require(target).argv
        _shortcut = self._shortcuts.setdefault(f"{namespace}::{name}", ({}, {}))
        if isinstance(key, str):
            _key = key
            _flags = 0
        else:
            _key = key.pattern
            _flags = key.flags
        humanize = source.pop("humanized", None)
        if source.get("prefix", False) and target.prefixes:
            out = []
            for prefix in target.prefixes:
                _shortcut[1][f"{re.escape(prefix)}{_key}"] = InnerShortcutArgs(
                    **{**source, "command": argv.converter(prefix + source.get("command", str(target.command)))},
                    flags=_flags,
                )
                out.append(
                    lang.require("shortcut", "add_success").format(shortcut=f"{prefix}{_key}", target=target.path)
                )
            _shortcut[0][humanize or _key] = InnerShortcutArgs(
                **{**source, "command": argv.converter(source.get("command", str(target.command))), "prefixes": target.prefixes},
                flags=_flags,
            )
            target.formatter.update_shortcut(target)
            return "\n".join(out)
        _shortcut[0][humanize or _key] = _shortcut[1][_key] = InnerShortcutArgs(
            **{**source, "command": argv.converter(source.get("command", str(target.command)))},
            flags=_flags,
        )
        target.formatter.update_shortcut(target)
        return lang.require("shortcut", "add_success").format(shortcut=_key, target=target.path)

    def get_shortcut(self, target: Alconna) -> dict[str, InnerShortcutArgs]:
        """列出快捷命令

        Args:
            target (Alconna): 目标命令

        Returns:
            dict[str,  InnerShortcutArgs]: 快捷命令的参数
        """
        namespace, name = self._command_part(target.path)
        cmd_hash = target._hash
        if cmd_hash not in self.__analysers:
            raise ValueError(lang.require("manager", "undefined_command").format(target=f"{namespace}.{name}"))
        shortcuts = self._shortcuts.get(f"{namespace}::{name}", {})
        if not shortcuts:
            return {}
        return shortcuts[0]

    def find_shortcut(
        self, target: Alconna, data: list
    ) -> tuple[str, list, InnerShortcutArgs, Match[str] | None]:
        """查找快捷命令

        Args:
            target (Alconna): 目标命令对象
            data (list): 传入的命令数据

        Returns:
            tuple[str, list, InnerShortcutArgs, re.Match[str]]: 返回匹配的快捷命令
        """
        namespace, name = self._command_part(target.path)
        if not (_shortcut := self._shortcuts.get(f"{namespace}::{name}")):
            raise ValueError(lang.require("manager", "undefined_command").format(target=f"{namespace}.{name}"))
        if res := _find_shortcut(_shortcut[1], data.copy(), target.separators):
            return res
        raise ValueError(
            lang.require("manager", "shortcut_parse_error").format(target=f"{namespace}.{name}", query=data)
        )

    def delete_shortcut(self, target: Alconna, key: str | TPattern | None = None):
        """删除快捷命令"""
        namespace, name = self._command_part(target.path)
        if not (_shortcut := self._shortcuts.get(f"{namespace}::{name}")):
            raise ValueError(lang.require("manager", "undefined_command").format(target=f"{namespace}.{name}"))
        if key:
            _key = key if isinstance(key, str) else key.pattern
            try:
                _shortcut[0].pop(_key, None)
                del _shortcut[1][_key]
                return lang.require("shortcut", "delete_success").format(shortcut=_key, target=target.path)
            except KeyError as e:
                raise ValueError(
                    lang.require("manager", "shortcut_parse_error").format(target=f"{namespace}.{name}", query=_key)
                ) from e
        else:
            self._shortcuts.pop(f"{namespace}.{name}")
            return lang.require("shortcut", "delete_success").format(shortcut="all", target=target.path)

    def get_command(self, command: str) -> Alconna:
        """获取命令"""
        for ana in self.__analysers.values():
            namespace, name = self._command_part(command)
            if ana.command.namespace == namespace and (ana.command.command == name or ana.command.name == name):
                return ana.command
        raise ValueError(lang.require("manager", "undefined_command").format(target=command))

    def get_commands(self, namespace: str | Namespace = "") -> list[Alconna]:
        """获取命令列表"""
        if not namespace:
            return [ana.command for ana in self.__analysers.values()]
        if isinstance(namespace, Namespace):
            namespace = namespace.name
        return [ana.command for ana in self.__analysers.values() if ana.command.namespace == namespace]

    def test(self, message: TDC, namespace: str | Namespace = "") -> Arparma[TDC] | None:
        """将一段命令给当前空间内的所有命令测试匹配"""
        for cmd in self.get_commands(namespace):
            if (res := cmd.parse(message)) and res.matched:
                return res

    def broadcast(self, message: TDC, namespace: str | Namespace = "") -> WeakValueDictionary[str, Arparma[TDC]]:
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
        page: int = 1,
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
        cmds = [cmd for cmd in self.get_commands(namespace or "") if not cmd.config.hide]
        slots = [(cmd.header_display, cmd.meta.description) for cmd in cmds]
        header = header or lang.require("manager", "help_header")
        if max_length < 1:
            command_string = (
                "\n".join(f" {str(index).rjust(len(str(len(cmds))), '0')} {slot[0]} : {slot[1]}" for index, slot in enumerate(slots))  # noqa: E501
                if show_index
                else "\n".join(f" - {n} : {d}" for n, d in slots)
            )
        else:
            max_page = len(cmds) // max_length + 1
            if page < 1 or page > max_page:
                page = 1
            header += "\t" + pages.format(current=page, total=max_page)
            command_string = (
                "\n".join(
                    f" {str(index).rjust(len(str(page * max_length)), '0')} {slot[0]} : {slot[1]}"
                    for index, slot in enumerate(slots[(page - 1) * max_length: page * max_length], start=(page - 1) * max_length)  # noqa: E501
                )
                if show_index
                else "\n".join(f" - {n} : {d}" for n, d in slots[(page - 1) * max_length: page * max_length])
            )
        help_names = set()
        for i in cmds:
            help_names.update(i.config.builtin_option_name["help"])
        footer = footer or lang.require("manager", "help_footer").format(help="|".join(help_names))
        return f"{header}\n{command_string}\n{footer}"

    def all_command_raw_help(self, namespace: str | Namespace | None = None) -> dict[str, Metadata]:
        """获取所有命令的原始帮助信息"""
        cmds = list(c for c in self.get_commands(namespace or "") if not c.config.hide)
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

    def get_result(self, command: Alconna) -> list[Arparma[Any]]:
        """获取某个命令的所有 `Arparma` 对象"""
        return [v for v in self.__record.values() if v._id == command._hash]

    def clear_result(self, command: Alconna):
        """清除某个命令下的所有解析缓存"""
        tokens = list(self.__record.keys())
        for token in tokens:
            if self.__record[token]._id == command._hash:
                del self.__record[token]

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
    def records(self) -> LRU[int, Arparma[Any]]:
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
            f"Current: {hex(id(self))} in {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}\n"
            + "Commands:\n"
            + f"[{', '.join([cmd.path for cmd in self.get_commands()])}]"
            + "\nShortcuts:\n"
            + "\n".join([f" {k} => {v}" for short in self._shortcuts.values() for k, v in short[0].items()])
            + "\nRecords:\n"
            + "\n".join([f" [{k}]: {v[1].origin}" for k, v in enumerate(self.__record.items()[:20])])
            + "\nDisabled Commands:\n"
            + f"[{', '.join(map(lambda x: self.__analysers[x].command.path, self.__abandons))}]"
        )


command_manager = CommandManager()
__all__ = ["ShortcutArgs", "command_manager"]
