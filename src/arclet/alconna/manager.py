"""Alconna 负责记录命令的部分"""

import asyncio
import weakref
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Optional, Union, List, Tuple
import shelve

from .exceptions import ExceedMaxCount
from .util import Singleton, LruCache
from .typing import DataCollection
from .lang import lang_config

if TYPE_CHECKING:
    from .core import Alconna, AlconnaGroup
    from .arpamar import Arpamar
    from .analysis.analyser import Analyser


class CommandManager(metaclass=Singleton):
    """
    Alconna 命令管理器

    命令管理器负责记录命令, 并存储快捷指令。
    """

    sign: str
    default_namespace: str
    current_count: int
    max_count: int

    __commands: Dict[str, Dict[str, Union['Alconna', 'AlconnaGroup']]]
    __analysers: Dict['Alconna', 'Analyser']
    __abandons: List["Alconna"]
    __record: LruCache[int, "Arpamar"]
    __shortcuts: LruCache[str, Union['Arpamar', Union[str, DataCollection]]]

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.cache_path = f"{__file__.replace('manager.py', '')}manager_cache.db"
        self.default_namespace = "Alconna"
        self.sign = "ALCONNA::"
        self.max_count = 200
        self.current_count = 0

        self.__commands = {}
        self.__analysers = {}
        self.__abandons = []
        self.__shortcuts = LruCache()
        self.__record = LruCache(100)
        weakref.finalize(self, self.__del__)

    def __del__(self):  # td: save to file
        try:
            self.__commands.clear()
            self.__abandons.clear()
            self.__record.clear()
            self.__shortcuts.clear()
            Singleton.remove(self.__class__)
        except AttributeError:
            pass

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """设置事件循环"""
        self.loop = loop

    def load_cache(self) -> None:
        """加载缓存"""
        try:
            with shelve.open(self.cache_path) as db:
                self.__shortcuts.update(db["shortcuts"])  # type: ignore
        except (FileNotFoundError, KeyError):
            pass

    def dump_cache(self) -> None:
        """保存缓存"""
        with shelve.open(self.cache_path) as db:
            db["shortcuts"] = self.__shortcuts

    @property
    def get_loaded_namespaces(self):
        """获取所有命名空间"""
        return list(self.__commands.keys())

    def _command_part(self, command: str) -> Tuple[str, str]:
        """获取命令的组成部分"""
        command_parts = command.split(".", 1)
        if len(command_parts) != 2:
            command_parts.insert(0, self.default_namespace)
        return command_parts[0], command_parts[1]

    def register(self, delegate: "Analyser") -> None:
        """注册命令解析器, 会同时记录解析器对应的命令"""
        if self.current_count >= self.max_count:
            raise ExceedMaxCount
        self.__analysers[delegate.alconna] = delegate
        if delegate.alconna.namespace not in self.__commands:
            self.__commands[delegate.alconna.namespace] = {}
        cid = delegate.alconna.name.replace(self.sign, "")
        if _cmd := self.__commands[delegate.alconna.namespace].get(cid):
            if _cmd == delegate.alconna:
                return
            _cmd.__union__(delegate.alconna)
            # raise DuplicateCommand(
            #     lang_config.manager_duplicate_command.format(target=f"{delegate.alconna.namespace}.{cid}")
            # )
        else:
            self.__commands[delegate.alconna.namespace][cid] = delegate.alconna
            self.current_count += 1

    def require(self, command: "Alconna") -> "Analyser":
        """获取命令解析器"""
        try:
            return self.__analysers[command]
        except KeyError:
            namespace, name = self._command_part(command.path)
            raise ValueError(lang_config.manager_undefined_command.format(target=f"{namespace}.{name}"))

    def delete(self, command: Union["Alconna", 'AlconnaGroup', str]) -> None:
        """删除命令"""
        namespace, name = self._command_part(command if isinstance(command, str) else command.path)
        try:
            del self.__commands[namespace][name]
            self.current_count -= 1
        finally:
            if self.__commands[namespace] == {}:
                del self.__commands[namespace]
            return None

    def is_disable(self, command: "Alconna") -> bool:
        """判断命令是否被禁用"""
        return command in self.__abandons

    def set_enable(self, command: Union["Alconna", str]) -> None:
        """启用命令"""
        if isinstance(command, str):
            namespace, name = self._command_part(command)
            if namespace not in self.__commands or name not in self.__commands[namespace]:
                raise ValueError(lang_config.manager_undefined_command.format(target=command))
            temp = []
            for cmd in self.__abandons:
                if cmd.path == f"{namespace}.{name}":
                    temp.append(cmd)
            for cmd in temp:
                self.__abandons.remove(cmd)
            return
        self.__abandons.remove(command)

    def add_shortcut(
            self,
            target: Union["Alconna", str],
            shortcut: str,
            source: Union["Arpamar", Union[str, DataCollection]],
            expiration: int = 0,
    ) -> None:
        """添加快捷命令"""
        from .arpamar import Arpamar
        namespace, name = self._command_part(target if isinstance(target, str) else target.path)
        try:
            _ = self.__commands[namespace][name]
        except KeyError:
            raise ValueError(lang_config.manager_undefined_command.format(target=f"{namespace}.{name}"))
        if (
                isinstance(source, Arpamar)
                and source.matched
                or not isinstance(source, Arpamar)
        ):
            self.__shortcuts.set(f"{namespace}.{name}::{shortcut}", source, expiration)
        else:
            raise ValueError(lang_config.manager_incorrect_shortcut.format(target=f"{shortcut}"))

    def find_shortcut(self, shortcut: str, target: Optional[Union["Alconna", str]] = None):
        """查找快捷命令"""
        if target:
            namespace, name = self._command_part(target if isinstance(target, str) else target.path)
            try:
                _ = self.__commands[namespace][name]
            except KeyError:
                raise ValueError(lang_config.manager_undefined_command.format(target=f"{namespace}.{name}"))
            try:
                return self.__shortcuts[f"{namespace}.{name}::{shortcut}"]
            except KeyError:
                raise ValueError(
                    lang_config.manager_target_command_error.format(target=f"{namespace}.{name}", shortcut=shortcut)
                )
        else:
            for key in self.__shortcuts:
                if key.split("::")[1] == shortcut:
                    return self.__shortcuts.get(key)
            raise ValueError(lang_config.manager_undefined_shortcut.format(target=f"{shortcut}"))

    def update_shortcut(self, random: bool = False):
        if random:
            self.__shortcuts.update()
        else:
            self.__shortcuts.update_all()

    def delete_shortcut(self, shortcut: str, target: Optional[Union["Alconna", str]] = None):
        """删除快捷命令"""
        if target:
            namespace, name = self._command_part(target if isinstance(target, str) else target.path)
            try:
                _ = self.__commands[namespace][name]
            except KeyError:
                raise ValueError(lang_config.manager_undefined_command.format(target=f"{namespace}.{name}"))
            try:
                self.__shortcuts.delete(f"{namespace}.{name}::{shortcut}")
            except KeyError:
                raise ValueError(
                    lang_config.manager_target_command_error.format(target=f"{namespace}.{name}", shortcut=shortcut)
                )
        else:
            for key in self.__shortcuts:
                if key.split("::")[1] == shortcut:
                    self.__shortcuts.delete(key)
                    return
            raise ValueError(lang_config.manager_undefined_shortcut.format(target=f"{shortcut}"))

    def set_disable(self, command: Union["Alconna", str]) -> None:
        """禁用命令"""
        if isinstance(command, str):
            namespace, name = self._command_part(command)
            if namespace not in self.__commands or name not in self.__commands[namespace]:
                raise ValueError(lang_config.manager_undefined_command.format(target=f"{namespace}.{name}"))
            cmd = self.__commands[namespace][name]
            if hasattr(cmd, 'commands'):
                self.__abandons.extend(cmd.commands)
            else:
                self.__abandons.append(cmd)
            return
        self.__abandons.append(command)

    def get_command(self, command: str) -> Union["Alconna", "AlconnaGroup", None]:
        """获取命令"""
        namespace, name = self._command_part(command)
        if namespace not in self.__commands or name not in self.__commands[namespace]:
            return None
        return self.__commands[namespace][name]

    def get_commands(self, namespace: Optional[str] = None) -> List[Union["Alconna", "AlconnaGroup"]]:
        """获取命令列表"""
        if namespace is None:
            return [ana for namespace in self.__commands for ana in self.__commands[namespace].values()]
        if namespace not in self.__commands:
            return []
        return [ana for ana in self.__commands[namespace].values()]

    def broadcast(self, message: Union[str, DataCollection], namespace: Optional[str] = None) -> Optional['Arpamar']:
        """将一段命令广播给当前空间内的所有命令"""
        for cmd in self.get_commands(namespace):
            if (res := cmd.parse(message)).matched:
                return res

    def all_command_help(
            self,
            show_index: bool = False,
            namespace: Optional[str] = None,
            header: Optional[str] = None,
            pages: Optional[str] = None,
            footer: Optional[str] = None,
            max_length: int = -1,
            page: int = 1,
    ) -> str:
        """
        获取所有命令的帮助信息

        Args:
            show_index: 是否展示索引
            namespace: 指定的命名空间, 如果为None则选择所有命令
            header: 帮助信息的页眉
            pages: 帮助信息的页码
            footer: 帮助信息的页脚
            max_length: 单个页面展示的最大长度
            page: 当前页码
        """
        header = header or lang_config.manager_help_header
        pages = pages or lang_config.manager_help_pages
        footer = footer or lang_config.manager_help_footer
        cmds = self.get_commands(namespace)

        if max_length < 1:
            command_string = "\n".join(
                f" - {cmd.name} : {cmd.help_text.replace('Usage', ';').replace('Example', ';').split(';')[0]}"
                for cmd in cmds
            ) if not show_index else "\n".join(
                f" {str(index).rjust(len(str(len(cmds))), '0')} {slot.name} : " +
                slot.help_text.replace('Usage', ';').replace('Example', ';').split(';')[0]
                for index, slot in enumerate(cmds)
            )
        else:
            max_page = len(cmds) // max_length + 1
            if page < 1 or page > max_page:
                page = 1
            header += "\t" + pages.format(current=page, total=max_page)
            command_string = "\n".join(
                f" - {cmd.name} : {cmd.help_text.replace('Usage', ';').replace('Example', ';').split(';')[0]}"
                for cmd in cmds[(page - 1) * max_length: page * max_length]
            ) if not show_index else "\n".join(
                f" {str(index).rjust(len(str(page * max_length)), '0')} {cmd.name} : "
                f"{cmd.help_text.replace('Usage', ';').replace('Example', ';').split(';')[0]}"
                for index, cmd in enumerate(
                    cmds[(page - 1) * max_length: page * max_length], start=(page - 1) * max_length
                )
            )
        return f"{header}\n{command_string}\n{footer}"

    def command_help(self, command: str) -> Optional[str]:
        """获取单个命令的帮助"""
        command_parts = self._command_part(command)
        if cmd := self.get_command(f"{command_parts[0]}.{command_parts[1]}"):
            return cmd.get_help()

    def record(
        self,
        token: int,
        message: Union[str, DataCollection],
        result: "Arpamar"
    ):
        result.origin = message
        self.__record.set(token, result)

    def get_record(self, token: int) -> Optional["Arpamar"]:
        if not token:
            return
        return self.__record.get(token)

    @property
    def recent_message(self) -> Optional[Union[str, DataCollection]]:
        if rct := self.__record.recent:
            return rct.origin

    @property
    def last_using(self) -> Optional["Alconna"]:
        if rct := self.__record.recent:
            return rct.source

    @property
    def records(self) -> LruCache:
        return self.__record

    def reuse(self, index: int = -1):
        key = list(self.__record.cache.keys())[index]
        return self.__record.get(key)

    def __repr__(self):
        return f"Current: {hex(id(self))} in {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}\n" + \
               "Commands:\n" + \
               f"[{', '.join(map(lambda x: x.path, self.get_commands()))}]" + \
               "\nShortcuts:\n" + \
               "\n".join(f" {k} => {v}" for k, v in self.__shortcuts.items()) + \
               "\nRecords:\n" + \
               "\n".join(f" [{k}]: {v[1].origin}" for k, v in enumerate(self.__record.items(20))) + \
               "\nDisabled Commands:\n" + \
               f"[{', '.join(map(lambda x: x.path, self.__abandons))}]"


command_manager = CommandManager()
