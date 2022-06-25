from abc import ABCMeta, abstractmethod
from weakref import finalize
from typing import Dict, Callable, Union, Coroutine, Any, Optional, List, TYPE_CHECKING, Set
from dataclasses import dataclass

from .action import ArgAction
from ..util import Singleton
from ..base import Option, Subcommand, Args, ArgUnit


class OutputAction(ArgAction):
    output_text_call: Callable[[], str]

    def __init__(self, send_action, out_call, command=None):
        super().__init__(send_action)
        self.output_text_call = out_call
        self.command = command

    def handle(self, option_dict=None, varargs=None, kwargs=None, is_raise_exception=False):
        return super().handle({"help": self.output_text_call()}, varargs, kwargs, is_raise_exception)


class OutputActionManager(metaclass=Singleton):
    """帮助信息"""
    cache: Dict[str, Callable]
    outputs: Dict[str, OutputAction]
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

    def get(self, command: str, output_call: Callable[[], str]) -> OutputAction:
        """获取发送帮助信息的 action"""
        if command not in self.outputs:
            self.outputs[command] = OutputAction(self.send_action, output_call, command)
        else:
            self.outputs[command].output_text_call = output_call

        if command in self.cache:
            self.outputs[command].action = self.cache[command]
            del self.cache[command]
        return self.outputs[command]

    def set_action(self, action: Callable[[str], Any], command: Optional[str] = None):
        """修改help_send_action"""
        if command is None:
            self.send_action = action
        elif cmd := self.outputs.get(command):
            cmd.action = action
        else:
            self.cache[command] = action


output_manager = OutputActionManager()


if TYPE_CHECKING:
    from ..core import Alconna, AlconnaGroup


def resolve_requires(options: List[Union[Option, Subcommand]]):
    reqs: Dict[str, Union[dict, Union[Option, Subcommand]]] = {}

    def _u(target, source):
        for k in source:
            if k not in target or isinstance(target[k], (Option, Subcommand)):
                target.update(source)
                break
            _u(target[k], source[k])

    for opt in options:
        if not opt.requires:
            reqs.setdefault(opt.name, opt)
            [reqs.setdefault(i, opt) for i in opt.aliases] if isinstance(opt, Option) else None
        else:
            _reqs = _cache = {}
            for req in opt.requires:
                if not _reqs:
                    _reqs[req] = {}
                    _cache = _reqs[req]
                else:
                    _cache[req] = {}
                    _cache = _cache[req]
            _cache[opt.name] = opt  # type: ignore
            [_cache.setdefault(i, opt) for i in opt.aliases] if isinstance(opt, Option) else None  # type: ignore

            _u(reqs, _reqs)

    return reqs


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
            hds = command.headers.copy()
            if command.name in hds:
                hds.remove(command.name)  # type: ignore
            return Trace(
                {'name': command.name, 'header': hds or [''], 'description': command.help_text},
                command.args, command.separators, command.options
            )

        for cmd in base.commands if base._group else [base]:  # type: ignore
            if self.data and self.data[-1].head['name'] == cmd.name:
                self.data[-1].union(_handle(cmd))  # type: ignore
            else:
                self.data.append(_handle(cmd))  # type: ignore

    def format_node(self, end: Optional[list] = None):
        """
        格式化命令节点
        """

        def _handle(trace: Trace):
            if not end or end == ['']:
                return self.format(trace)
            _cache = resolve_requires(trace.body)
            _parts = []
            for text in end:
                if text in _cache:
                    _cache = _cache[text]
                    _parts.append(text)
                if not isinstance(_cache, dict):
                    break
            else:
                return self.format(trace)
            if isinstance(_cache, dict):
                return self.format(Trace(
                    {"name": _parts[-1], 'header': [''], 'description': _parts[-1]}, Args(), trace.separators,
                    [Option(k, requires=_parts) if isinstance(i, dict) else i for k, i in _cache.items()]
                ))
            if isinstance(_cache, Option):
                _hdr = [i for i in _cache.aliases if i != _cache.name]
                return self.format(Trace(
                    {"name": _cache.name, "header": _hdr or [""], "description": _cache.help_text}, _cache.args,
                    _cache.separators, []
                ))
            if isinstance(_cache, Subcommand):
                return self.format(Trace(
                    {"name": _cache.name, "header": [""], "description": _cache.help_text}, _cache.args,
                    _cache.separators, _cache.options  # type: ignore
                ))
            return self.format(trace)

        return "\n".join(map(_handle, self.data))

    @abstractmethod
    def format(self, trace: Trace) -> str:
        """help text的生成入口"""

    @abstractmethod
    def param(self, name: str, parameter: ArgUnit) -> str:
        """对单个参数的描述"""

    @abstractmethod
    def parameters(self, args: Args) -> str:
        """参数列表的描述"""

    @abstractmethod
    def header(self, root: Dict[str, Any], separators: Set[str]) -> str:
        """头部节点的描述"""

    @abstractmethod
    def part(self, node: Union[Subcommand, Option]) -> str:
        """每个子节点的描述"""

    @abstractmethod
    def body(self, parts: List[Union[Option, Subcommand]]) -> str:
        """子节点列表的描述"""


__all__ = ["AbstractTextFormatter", "output_manager", "Trace"]
