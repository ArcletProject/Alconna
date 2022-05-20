from abc import ABCMeta, abstractmethod
from typing import Dict, Callable, Union, Coroutine, Any, Optional, List, Set

from .action import ArgAction
from ..util import Singleton


class OutputActionManager(metaclass=Singleton):
    """帮助信息"""
    cache: Dict[str, Callable]
    outputs: Dict[str, "OutputAction"]
    send_action: Callable[[str], Union[Any, Coroutine]]

    def __init__(self):
        self.cache = {}
        self.outputs = {}
        self.send_action = lambda x: print(x)

    def require_send_action(
            self,
            action: Optional[Callable[[str], Any]] = None,
            command: Optional[str] = None
    ):
        """修改help_send_action"""
        if action is None:
            return self.send_action if command is None else self.outputs[command].action
        if command is None:
            self.send_action = action
        elif self.outputs.get(command):
            self.outputs[command].action = action

        else:
            self.cache[command] = action


output_manager = OutputActionManager()


class OutputAction(ArgAction):
    output_text_call: Callable[[], str]

    def __init__(self, out_call, command=None):
        super().__init__(output_manager.send_action)
        self.output_text_call = out_call
        self.command = command

    def handle(self, option_dict, varargs=None, kwargs=None, is_raise_exception=False):
        if action := output_manager.require_send_action(command=self.command):
            return super().handle({"help": self.output_text_call()}, varargs, kwargs, is_raise_exception)
        return option_dict


def output_send(command: str, output_call: Callable[[], str]):
    """帮助信息的发送 action"""
    if command not in output_manager.outputs:
        output_manager.outputs[command] = OutputAction(output_call, command)
    else:
        output_manager.outputs[command].output_text_call = output_call

    if command in output_manager.cache:
        output_manager.outputs[command].action = output_manager.cache[command]
        del output_manager.cache[command]
    return output_manager.outputs[command]


class AbstractTextFormatter(metaclass=ABCMeta):
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
    def parameters(self, params: List[Dict[str, Any]], separator: Set[str]) -> str:
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
