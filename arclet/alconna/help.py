import inspect
from abc import ABCMeta, abstractmethod
from typing import Dict, Callable, Union, Coroutine, Any, Optional, List

from .base import ArgAction
from .util import Singleton


class HelpActionManager(metaclass=Singleton):
    """帮助信息"""
    cache: Dict[str, Callable]
    helpers: Dict[str, "HelpAction"]
    send_action: Callable[[str], Union[Any, Coroutine]]

    def __init__(self):
        self.cache = {}
        self.helpers = {}
        self.send_action = lambda x: print(x)

    def require_send_action(
            self,
            action: Optional[Callable[[str], Any]] = None,
            command: Optional[str] = None
    ):
        """修改help_send_action"""
        if action is None:
            if command is None:
                return self.send_action
            return self.helpers[command].action
        if command is None:
            self.send_action = action
            for helper in self.helpers.values():
                helper.awaitable = inspect.iscoroutinefunction(action)
        else:
            if not self.helpers.get(command):
                self.cache[command] = action
            else:
                self.helpers[command].action = action


help_manager = HelpActionManager()


class HelpAction(ArgAction):
    help_string_call: Callable[[], str]

    def __init__(self, help_call, command=None):
        super().__init__(help_manager.send_action)
        self.help_string_call = help_call
        self.command = command

    def handle(self, option_dict, varargs=None, kwargs=None, is_raise_exception=False):
        action = help_manager.require_send_action(command=self.command)
        if action:
            return super().handle({"help": self.help_string_call()}, varargs, kwargs, is_raise_exception)
        return option_dict


def help_send(command: str, help_string_call: Callable[[], str]):
    """帮助信息的发送 action"""
    if command not in help_manager.helpers:
        help_manager.helpers[command] = HelpAction(help_string_call, command)
    else:
        help_manager.helpers[command].help_string_call = help_string_call

    if command in help_manager.cache:
        help_manager.helpers[command].action = help_manager.cache[command]
        del help_manager.cache[command]
    return help_manager.helpers[command]


class AbstractHelpTextFormatter(metaclass=ABCMeta):
    """
    帮助文档格式化器

    该格式化器负责将传入的命令节点字典解析并生成帮助文档字符串
    """

    @abstractmethod
    def format(self, trace: Dict[str, Union[str, List, Dict]]) -> str:
        """
        help text的生成入口
        """
        pass

    @abstractmethod
    def param(self, parameter: Dict[str, Any]) -> str:
        """
        对单个参数的描述
        """
        pass

    @abstractmethod
    def parameters(self, params: List[Dict[str, Any]], separator: str = " ") -> str:
        """
        参数列表的描述
        """
        pass

    @abstractmethod
    def header(self, root: Dict[str, Any]) -> str:
        """
        头部节点的描述
        """
        pass

    @abstractmethod
    def part(self, sub: Dict[str, Any], node_type: str) -> str:
        """
        每个子节点的描述
        """
        pass

    @abstractmethod
    def body(self, parts: List[Dict[str, Any]]) -> str:
        """
        子节点列表的描述
        """
        pass
