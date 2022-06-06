from abc import ABCMeta, abstractmethod
from weakref import finalize
from typing import Dict, Callable, Union, Coroutine, Any, Optional, List, TYPE_CHECKING, Set
from dataclasses import dataclass

from .action import ArgAction
from ..util import Singleton
from ..base import Option, Subcommand, Args, ArgUnit


class OutputActionManager(metaclass=Singleton):
    """帮助信息"""
    cache: Dict[str, Callable]
    outputs: Dict[str, "OutputAction"]
    send_action: Callable[[str], Union[Any, Coroutine]]

    def __init__(self):
        self.cache = {}
        self.outputs = {}
        self.send_action = lambda x: print(x)

        def _clr(mgr: 'OutputActionManager'):
            mgr.cache.clear()
            mgr.outputs.clear()
            Singleton.remove(mgr.__class__)

        finalize(self, _clr, self)

    def set_send_action(
            self,
            action: Callable[[str], Any],
            command: Optional[str] = None
    ):
        """修改help_send_action"""
        if command is None:
            self.send_action = action
        elif cmd := self.outputs.get(command):
            cmd.action = action
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
        return super().handle({"help": self.output_text_call()}, varargs, kwargs, is_raise_exception)


def output_send(command: str, output_call: Callable[[], str]) -> OutputAction:
    """帮助信息的发送 action"""
    if command not in output_manager.outputs:
        output_manager.outputs[command] = OutputAction(output_call, command)
    else:
        output_manager.outputs[command].output_text_call = output_call

    if command in output_manager.cache:
        output_manager.outputs[command].action = output_manager.cache[command]
        del output_manager.cache[command]
    return output_manager.outputs[command]


if TYPE_CHECKING:
    from ..core import Alconna, AlconnaGroup


@dataclass
class Trace:
    head: Dict[str, Any]
    args: Args
    separators: Set[str]
    body: List[Union[Option, Subcommand]]

    def union(self, other: 'Trace'):
        self.head['header'] = list({*self.head['header'], *other.head['header']})
        self.body = list({*self.body, *other.body})


class AbstractTextFormatter(metaclass=ABCMeta):
    """
    帮助文档格式化器

    该格式化器负责将传入的命令节点字典解析并生成帮助文档字符串
    """
    def __init__(self, base: Union['Alconna', 'AlconnaGroup']):
        self.data = []

        def _handle(command: 'Alconna'):
            return Trace(
                {'name': command.name, 'header': command.headers, 'description': command.help_text},
                command.args, command.separators, command.options
            )

        for cmd in base.commands if base._group else [base]:  # type: ignore
            if self.data and self.data[-1].head['name'] == cmd.name:
                self.data[-1].union(_handle(cmd))  # type: ignore
            else:
                self.data.append(_handle(cmd))  # type: ignore

    def format_node(self, end: Optional[List[str]] = None):
        """
        格式化命令节点
        """
        end = end  # TODO: 依据end确定起始位置
        res = ''
        for trace in self.data:
            res += self.format(trace) + '\n'
        return res

    @abstractmethod
    def format(self, trace: Trace) -> str:
        """
        help text的生成入口
        """
        pass

    @abstractmethod
    def param(self, name: str,  parameter: ArgUnit) -> str:
        """
        对单个参数的描述
        """
        pass

    @abstractmethod
    def parameters(self, args: Args) -> str:
        """
        参数列表的描述
        """
        pass

    @abstractmethod
    def header(self, root: Dict[str, Any], separators: Set[str]) -> str:
        """
        头部节点的描述
        """
        pass

    @abstractmethod
    def part(self, node: Union[Subcommand, Option]) -> str:
        """
        每个子节点的描述
        """
        pass

    @abstractmethod
    def body(self, parts: List[Union[Option, Subcommand]]) -> str:
        """
        子节点列表的描述
        """
        pass


__all__ = ["AbstractTextFormatter", "output_send", "output_manager", "Trace"]
