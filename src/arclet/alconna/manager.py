"""Alconna 负责记录命令的部分"""
import weakref
from copy import copy
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Optional, Union, List, Tuple, Any
import shelve
import contextlib

from .exceptions import ExceedMaxCount
from .util import Singleton, LruCache
from .typing import TDataCollection, DataCollection
from .config import config, Namespace

if TYPE_CHECKING:
    from .analysis.analyser import Analyser
    from .core import Alconna, AlconnaGroup, CommandMeta
    from .arparma import Arparma


class CommandManager(metaclass=Singleton):
    """
    Alconna 命令管理器

    命令管理器负责记录命令, 并存储快捷指令。
    """

    sign: str
    current_count: int
    max_count: int

    __commands: Dict[str, Dict[str, Union['Alconna', 'AlconnaGroup']]]
    __analysers: Dict['Alconna', 'Analyser']
    __abandons: List["Alconna"]
    __record: LruCache[int, "Arparma"]
    __shortcuts: LruCache[str, Union['Arparma', DataCollection[Union[str, Any]]]]

    def __init__(self):
        self.cache_path = f"{__file__.replace('manager.py', '')}manager_cache.db"
        self.sign = "ALCONNA::"
        self.max_count = config.command_max_count
        self.current_count = 0

        self.__commands = {}
        self.__analysers = {}
        self.__abandons = []
        self.__shortcuts = LruCache()
        self.__record = LruCache(config.message_max_cache)

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
            Singleton.remove(self.__class__)

        weakref.finalize(self, _del)

    def load_cache(self) -> None:
        """加载缓存"""
        with contextlib.suppress(FileNotFoundError, KeyError):
            with shelve.open(self.cache_path) as db:
                self.__shortcuts = db["shortcuts"]  # type: ignore

    def dump_cache(self) -> None:
        """保存缓存"""
        with shelve.open(self.cache_path) as db:
            db["shortcuts"] = self.__shortcuts

    @property
    def get_loaded_namespaces(self):
        """获取所有命名空间"""
        return list(self.__commands.keys())

    @staticmethod
    def _command_part(command: str) -> Tuple[str, str]:
        """获取命令的组成部分"""
        command_parts = command.split("::", maxsplit=1)[-2:]
        if len(command_parts) != 2:
            command_parts.insert(0, config.default_namespace.name)
        return command_parts[0], command_parts[1]

    def get_namespace_config(self, name: str) -> Optional[Namespace]:
        if name not in self.__commands:
            return
        return config.namespaces.get(name)

    def register(self, command: Union["Alconna", "AlconnaGroup"]) -> None:
        """注册命令解析器, 会同时记录解析器对应的命令"""
        from .analysis.base import compile
        if self.current_count >= self.max_count:
            raise ExceedMaxCount
        if not command._group:   # noqa
            self.__analysers.pop(command, None)
            self.__analysers[command] = compile(command)  # type: ignore
        else:
            for cmd in command.commands:  # type: ignore
                self.__analysers.pop(cmd, None)
                self.__analysers[cmd] = compile(cmd)
        namespace = self.__commands.setdefault(command.namespace, {})
        if _cmd := namespace.get(command.name):
            if _cmd == command:
                return
            _cmd.__union__(command)
        else:
            namespace[command.name] = command
            self.current_count += 1

    def require(self, command: "Alconna") -> "Analyser":
        """获取命令解析器"""
        try:
            return self.__analysers[command]
        except KeyError as e:
            namespace, name = self._command_part(command.path)
            raise ValueError(config.lang.manager_undefined_command.format(target=f"{namespace}.{name}")) from e

    def delete(self, command: Union["Alconna", 'AlconnaGroup', str]) -> None:
        """删除命令"""
        namespace, name = self._command_part(command if isinstance(command, str) else command.path)
        try:
            base = self.__commands[namespace][name]
            if base._group:  # noqa
                for cmd in base.commands:  # type: ignore
                    del self.__analysers[cmd]
            else:
                del self.__analysers[base]  # type: ignore
            del self.__commands[namespace][name]
            self.current_count -= 1
        finally:
            if self.__commands.get(namespace) == {}:
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
                raise ValueError(config.lang.manager_undefined_command.format(target=command))
            temp = [cmd for cmd in self.__abandons if cmd.path == f"{namespace}.{name}"]
            for cmd in temp:
                self.__abandons.remove(cmd)
            return
        self.__abandons.remove(command)

    def add_shortcut(
            self,
            target: Union["Alconna", str],
            shortcut: str,
            source: Union["Arparma", DataCollection[Union[str, Any]]]
    ) -> None:
        """添加快捷命令"""
        from .arparma import Arparma
        namespace, name = self._command_part(target if isinstance(target, str) else target.path)
        try:
            _ = self.__commands[namespace][name]
        except KeyError as e:
            raise ValueError(config.lang.manager_undefined_command.format(target=f"{namespace}.{name}")) from e
        if isinstance(source, Arparma) and source.matched or not isinstance(source, Arparma):
            self.__shortcuts.set(f"{namespace}.{name}::{shortcut}", source)
        else:
            raise ValueError(config.lang.manager_incorrect_shortcut.format(target=f"{shortcut}"))

    def find_shortcut(self, shortcut: str, target: Optional[Union["Alconna", str]] = None):
        """查找快捷命令"""
        if target:
            namespace, name = self._command_part(target if isinstance(target, str) else target.path)
            try:
                _ = self.__commands[namespace][name]
            except KeyError as e:
                raise ValueError(config.lang.manager_undefined_command.format(target=f"{namespace}.{name}")) from e
            try:
                return self.__shortcuts[f"{namespace}.{name}::{shortcut}"]
            except KeyError as e:
                raise ValueError(
                    config.lang.manager_target_command_error.format(target=f"{namespace}.{name}", shortcut=shortcut)
                ) from e
        else:
            with contextlib.suppress(StopIteration):
                return self.__shortcuts.get(next(filter(lambda x: x.split("::")[1] == shortcut, self.__shortcuts)))
            raise ValueError(config.lang.manager_undefined_shortcut.format(target=f"{shortcut}"))

    def delete_shortcut(self, shortcut: str, target: Optional[Union["Alconna", str]] = None):
        """删除快捷命令"""
        res = self.find_shortcut(shortcut, target)
        with contextlib.suppress(StopIteration):
            self.__shortcuts.delete(next(filter(lambda x: self.__shortcuts[x] == res, self.__shortcuts)))
        return

    def set_disable(self, command: Union["Alconna", str]) -> None:
        """禁用命令"""
        if isinstance(command, str):
            namespace, name = self._command_part(command)
            if namespace not in self.__commands or name not in self.__commands[namespace]:
                raise ValueError(config.lang.manager_undefined_command.format(target=f"{namespace}.{name}"))
            cmd = self.__commands[namespace][name]
            return (
                self.__abandons.extend(cmd.commands)  # type: ignore
                if hasattr(cmd, 'commands') else self.__abandons.append(cmd)  # type: ignore
            )
        self.__abandons.append(command)

    def get_command(self, command: str) -> Union["Alconna", "AlconnaGroup", None]:
        """获取命令"""
        namespace, name = self._command_part(command)
        if namespace not in self.__commands or name not in self.__commands[namespace]:
            return None
        return self.__commands[namespace][name]

    def get_commands(self, namespace: Union[str, Namespace] = '') -> List[Union["Alconna", "AlconnaGroup"]]:
        """获取命令列表"""
        if not namespace:
            return [ana for namespace in self.__commands for ana in self.__commands[namespace].values()]
        if isinstance(namespace, Namespace):
            namespace = Namespace.name
        if namespace not in self.__commands:
            return []
        return list(self.__commands[namespace].values())

    def broadcast(
        self, message: TDataCollection, namespace: Union[str, Namespace] = ''
    ) -> Optional['Arparma[TDataCollection]']:
        """将一段命令广播给当前空间内的所有命令"""
        for cmd in self.get_commands(namespace):
            if (res := cmd.parse(message)) and res.matched:
                return res

    def all_command_help(
            self,
            show_index: bool = False,
            namespace: Optional[Union[str, Namespace]] = None,
            header: Optional[str] = None,
            pages: Optional[str] = None,
            footer: Optional[str] = None,
            max_length: int = -1,
            page: int = 1
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
        pages = pages or config.lang.manager_help_pages
        cmds = list(filter(lambda x: not x.meta.hide, self.get_commands(namespace or '')))

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
        header = header or config.lang.manager_help_header
        footer = footer or config.lang.manager_help_footer.format(help="|".join(help_names))
        return f"{header}\n{command_string}\n{footer}"

    def all_command_raw_help(self, namespace: Optional[Union[str, Namespace]] = None) -> Dict[str, 'CommandMeta']:
        """获取所有命令的原始帮助信息"""
        cmds = list(filter(lambda x: not x.meta.hide, self.get_commands(namespace or '')))
        return {cmd.path: copy(cmd.meta) for cmd in cmds}

    def command_help(self, command: str) -> Optional[str]:
        """获取单个命令的帮助"""
        command_parts = self._command_part(command)
        if cmd := self.get_command(f"{command_parts[0]}.{command_parts[1]}"):
            return cmd.get_help()

    def record(self, token: int, message: DataCollection[Union[str, Any]], result: "Arparma"):
        result.origin = message
        self.__record.set(token, result)

    def get_record(self, token: int) -> Optional["Arparma"]:
        if not token:
            return
        return self.__record.get(token)

    def get_result(self, command: 'Alconna'):
        res = None
        for v in self.__record.values():
            if v.source == command:
                res = v
        return res

    @property
    def recent_message(self) -> Optional[DataCollection[Union[str, Any]]]:
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
