"""Alconna 负责记录命令的部分"""

import asyncio
import weakref
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Optional, Union, List, Tuple
import shelve

from .exceptions import DuplicateCommand, ExceedMaxCount
from .util import Singleton, LruCache
from .typing import DataCollection
from .lang import lang_config

if TYPE_CHECKING:
    from .core import Alconna
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

    __commands: Dict[str, Dict[str, 'Analyser']]
    __abandons: List["Alconna"]
    __record: LruCache[int, Tuple[str, "Arpamar"]]
    __shortcuts: LruCache[str, Union['Arpamar', Union[str, DataCollection]]]

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.cache_path = f"{__file__.replace('manager.py', '')}manager_cache.db"
        self.default_namespace = "Alconna"
        self.sign = "ALCONNA::"
        self.max_count = 200
        self.current_count = 0

        self.__commands = {}
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
        if delegate.alconna.namespace not in self.__commands:
            self.__commands[delegate.alconna.namespace] = {}
        cid = delegate.alconna.name.replace(self.sign, "")
        if cid not in self.__commands[delegate.alconna.namespace]:
            self.__commands[delegate.alconna.namespace][cid] = delegate
            self.current_count += 1
        else:
            raise DuplicateCommand(
                lang_config.manager_duplicate_command.format(target=f"{delegate.alconna.namespace}.{cid}")
            )

    def require(self, command: Union["Alconna", str]) -> "Analyser":
        """获取命令解析器"""
        namespace, name = self._command_part(command if isinstance(command, str) else command.path)
        try:
            ana = self.__commands[namespace][name]
        except KeyError:
            raise ValueError(lang_config.manager_undefined_command.format(target=f"{namespace}.{name}"))
        return ana

    def delete(self, command: Union["Alconna", str]) -> None:
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
        if command in self.__abandons:
            return True
        return False

    def set_enable(self, command: Union["Alconna", str]) -> None:
        """启用命令"""
        if isinstance(command, str):
            namespace, name = self._command_part(command)
            for alc in self.__abandons:
                if alc.namespace == namespace and alc.name.replace(self.sign, "") == name:
                    self.__abandons.remove(alc)
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
        if isinstance(source, Arpamar):
            if source.matched:
                self.__shortcuts.set(f"{namespace}.{name}::{shortcut}", source, expiration)
            else:
                raise ValueError(lang_config.manager_incorrect_shortcut.format(target=f"{shortcut}"))
        else:
            self.__shortcuts.set(f"{namespace}.{name}::{shortcut}", source, expiration)

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
            try:
                self.__abandons.append(self.__commands[namespace][name].alconna)
            finally:
                return None
        self.__abandons.append(command)

    def get_command(self, command: str) -> Union["Alconna", None]:
        """获取命令"""
        namespace, name = self._command_part(command)
        if namespace not in self.__commands:
            return None
        if name not in self.__commands[namespace]:
            return None
        return self.__commands[namespace][name].alconna

    def get_commands(self, namespace: Optional[str] = None) -> List["Alconna"]:
        """获取命令列表"""
        if namespace is None:
            return [ana.alconna for namespace in self.__commands for ana in self.__commands[namespace].values()]
        if namespace not in self.__commands:
            return []
        return [ana.alconna for ana in self.__commands[namespace].values()]

    def broadcast(self, command: Union[str, DataCollection], namespace: Optional[str] = None) -> Optional['Arpamar']:
        """将一段命令广播给当前空间内的所有命令"""
        if namespace is None:
            for n in self.__commands:
                for v in self.__commands[n].values():
                    res = v.alconna.parse(command)
                    if res.matched:
                        return res

        else:
            if namespace not in self.__commands:
                return None
            for v in self.__commands[namespace].values():
                res = v.alconna.parse(command)
                if res.matched:
                    return res

    def all_command_help(
            self,
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
        command_string = ""
        cmds = self.__commands[namespace or self.default_namespace]
        if max_length < 1:
            for name, cmd in cmds.items():
                command_string += "\n - " + name + " : " + cmd.alconna.help_text
        else:
            max_page = len(cmds) // max_length + 1
            if page < 1 or page > max_page:
                page = 1
            header += "\t" + pages.format(current=page, total=max_page)
            for name in list(cmds.keys())[(page - 1) * max_length: page * max_length]:
                alc = cmds[name].alconna
                command_string += "\n - " + (
                    f"[{'|'.join([f'{h}' for h in alc.headers])}]" if len(alc.headers) > 1
                    else f"{alc.headers[0]}" if alc.headers != [''] else ""
                ) + alc.command + " : " + alc.help_text
        return f"{header}{command_string}\n{footer}"

    def command_help(self, command: str) -> Optional[str]:
        """获取单个命令的帮助"""
        command_parts = self._command_part(command)
        cmd = self.get_command(f"{command_parts[0]}.{command_parts[1]}")
        if cmd:
            return cmd.get_help()

    def record(
            self,
            token: int,
            message: Union[str, DataCollection],
            command: Union[str, "Alconna"],
            result: "Arpamar"
    ):
        cmd = command if isinstance(command, str) else command.path
        result.origin = message
        self.__record.set(token, (cmd, result))

    def get_record(self, token: int) -> Optional[Tuple[str, "Arpamar"]]:
        if not token:
            return
        return self.__record.get(token)

    @property
    def recent_message(self) -> Optional[Union[str, DataCollection]]:
        if rct := self.__record.recent:
            return rct[1].origin

    @property
    def last_using(self) -> Optional["Alconna"]:
        if rct := self.__record.recent:
            return self.get_command(rct[0])

    @property
    def records(self) -> LruCache:
        return self.__record

    def reuse(self, index: int = -1):
        key = list(self.__record.cache.keys())[index]
        return self.__record.get(key)[1]

    def __repr__(self):
        return f"Current: {hex(id(self))} in {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}\n" + \
               "Commands:\n" + \
               f"[{', '.join(map(lambda x: x.path, self.get_commands()))}]" + \
               "\nShortcuts:\n" + \
               "\n".join(f" {k} => {v}" for k, v in self.__shortcuts.items()) + \
               "\nRecords:\n" + \
               "\n".join(f" [{k}]: {v[1][1].origin}" for k, v in enumerate(self.__record.items(20))) + \
               "\nDisabled Commands:\n" + \
               f"[{', '.join(map(lambda x: x.path, self.__abandons))}]"


command_manager = CommandManager()
