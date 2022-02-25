"""Alconna 负责记录命令的部分"""

import re
from typing import TYPE_CHECKING, Dict, Union, List, Tuple
from .exceptions import DuplicateCommand, ExceedMaxCount

if TYPE_CHECKING:
    from .main import Alconna


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class CommandManager(metaclass=Singleton):
    sign: str = "ALCONNA::"
    default_namespace: str = "Alconna"
    __shortcuts: Dict[str, Tuple[str, str, bool]] = {}
    __commands: Dict[str, Dict[str, "Alconna"]]
    __abandons: List["Alconna"]
    current_count: int
    max_count: int = 100

    def __init__(self):
        self.__commands = {}
        self.__abandons = []
        self.current_count = 0

    def __del__(self):  # TODO: save to file
        self.__commands = {}
        self.__abandons = []

    @property
    def commands(self) -> Dict[str, Dict[str, "Alconna"]]:
        """获取命令字典"""
        return self.__commands

    def _command_part(self, command: str) -> Tuple[str, str]:
        """获取命令的组成部分"""
        command_parts = command.split(".")
        if len(command_parts) != 2:
            command_parts.insert(0, self.default_namespace)
        return command_parts[0], command_parts[1]

    def register(self, command: "Alconna") -> None:
        """注册命令"""
        if self.current_count >= self.max_count:
            raise ExceedMaxCount
        if command.namespace not in self.__commands:
            self.__commands[command.namespace] = {}
        cid = command.name.replace(self.sign, "")
        if cid not in self.__commands[command.namespace]:
            self.__commands[command.namespace][cid] = command
            self.current_count += 1
        else:
            raise DuplicateCommand("命令已存在")

    def delete(self, command: Union["Alconna", str]) -> None:
        """删除命令"""
        if isinstance(command, str):
            namespace, name = self._command_part(command)
            try:
                del self.__commands[namespace][name]
            finally:
                if self.__commands[namespace] == {}:
                    del self.__commands[namespace]
                return None
        cid = command.name.replace(self.sign, "")
        namespace = command.namespace
        try:
            del self.__commands[namespace][cid]
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

    def add_shortcut(self, target: Union["Alconna", str], shortcut: str, command: str, reserve: bool = False) -> None:
        """添加快捷命令"""
        if isinstance(target, str):
            namespace, name = self._command_part(target)
            try:
                target = self.__commands[namespace][name]
            except KeyError:
                raise ValueError("命令不存在")
        if shortcut in self.__shortcuts:
            raise DuplicateCommand("快捷命令已存在")
        self.__shortcuts[shortcut] = (target.namespace + "." + target.name.replace(self.sign, ""), command, reserve)

    def find_shortcut(self, target: Union["Alconna", str], shortcut: str):
        """查找快捷命令"""
        if shortcut not in self.__shortcuts:
            raise ValueError("快捷命令不存在")
        info, command, reserve = self.__shortcuts[shortcut]
        if isinstance(target, str):
            namespace, name = self._command_part(target)
            if info != (namespace + "." + name):
                raise ValueError("目标命令错误")
            try:
                target = self.__commands[namespace][name]
            except KeyError:
                raise ValueError("目标命令不存在")
            else:
                return target, command, reserve
        if info != (target.namespace + "." + target.name.replace(self.sign, "")):
            raise ValueError("目标命令错误")
        return target, command, reserve

    def set_disable(self, command: Union["Alconna", str]) -> None:
        """禁用命令"""
        if isinstance(command, str):
            namespace, name = self._command_part(command)
            try:
                self.__abandons.append(self.__commands[namespace][name])
            finally:
                return None
        self.__abandons.append(command)

    def get_command(self, command: str) -> Union["Alconna", None]:
        """获取命令"""
        command_parts = command.split(".")
        if command_parts[0] not in self.__commands:
            return None
        if command_parts[1] not in self.__commands[command_parts[0]]:
            return None
        return self.__commands[command_parts[0]][command_parts[1]]

    def get_commands(self, namespace: str = None) -> List["Alconna"]:
        """获取命令列表"""
        if namespace is None:
            return [alc for alc in self.__commands[self.default_namespace].values()]
        if namespace not in self.__commands:
            return []
        return [alc for alc in self.__commands[namespace].values()]

    def broadcast(self, command: str, namespace: str = None):
        """广播命令"""
        may_command_head = command.split(" ")[0]
        if namespace is None:
            for n in self.__commands:
                if self.__commands[n].get(may_command_head):
                    return self.__commands[n][may_command_head].analyse_message(command)
                for k in self.__commands[n]:
                    if re.match("^" + k + ".*" + "$", str(command)):
                        return self.__commands[n][k].analyse_message(command)
        else:
            if self.__commands[namespace].get(may_command_head):
                return self.__commands[namespace][may_command_head].analyse_message(command)
            for k in self.__commands[namespace]:
                if re.match("^" + k + ".*" + "$", str(command)):
                    return self.__commands[namespace][k].analyse_message(command)

    def all_command_help(self, namespace: str = None) -> str:
        command_string = ""
        for name, cmd in self.__commands[namespace or self.default_namespace].items():
            command_string += "\n - " + name + " " + cmd.help_text
        return f"# 当前可用的命令有:{command_string}\n# 输入'命令名 --help' 查看特定命令的语法"
