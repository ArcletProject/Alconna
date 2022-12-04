from weakref import finalize
from typing import Dict, Callable, Union, Coroutine, Any, Optional, List, TYPE_CHECKING, Tuple
from dataclasses import dataclass
from nepattern import Empty, AllParam, BasePattern

from .action import ArgAction
from ..util import Singleton
from ..args import Args, Arg
from ..base import Option, Subcommand


class OutputAction(ArgAction):
    output_text_call: Callable[[], str]

    def __init__(self, send_action, out_call, command=None):
        super().__init__(send_action)
        self.output_text_call = out_call
        self.command = command

    def handle(self, option_dict=None, varargs=None, kwargs=None, raise_exception=False):
        return super().handle({"help": self.output_text_call()}, varargs, kwargs, raise_exception)


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
    separators: Tuple[str, ...]
    body: List[Union[Option, Subcommand]]

    def union(self, other: 'Trace'):
        self.head['header'] = list({*self.head['header'], *other.head['header']})
        self.body = list({*self.body, *other.body})


class TextFormatter:
    """
    帮助文档格式化器

    该格式化器负责将传入的命令节点字典解析并生成帮助文档字符串
    """

    def __init__(self, base: Union['Alconna', 'AlconnaGroup']):
        self.data = []
        self.ignore_names = set()

        def _handle(command: 'Alconna'):
            self.ignore_names.update(command.namespace_config.builtin_option_name['help'])
            self.ignore_names.update(command.namespace_config.builtin_option_name['shortcut'])
            self.ignore_names.update(command.namespace_config.builtin_option_name['completion'])
            hds = command.headers.copy()
            if command.name in hds:
                hds.remove(command.name)  # type: ignore
            return Trace(
                {
                    'name': command.name, 'header': hds or [], 'description': command.meta.description,
                    'usage': command.meta.usage, 'example': command.meta.example
                },
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
                if isinstance(_cache, dict) and text in _cache:
                    _cache = _cache[text]
                    _parts.append(text)
                if not _parts:
                    return self.format(trace)
            if isinstance(_cache, dict):
                _opts, _visited = [], set()
                for k, i in _cache.items():
                    if isinstance(i, dict):
                        _opts.append(Option(k, requires=_parts))
                    elif i not in _visited:
                        _opts.append(i)
                        _visited.add(i)
                return self.format(Trace(
                    {"name": _parts[-1], 'header': [], 'description': _parts[-1]}, Args(), trace.separators,
                    _opts
                ))
            if isinstance(_cache, Option):
                return self.format(Trace(
                    {"name": "", "header": list(_cache.aliases), "description": _cache.help_text}, _cache.args,
                    _cache.separators, []
                ))
            if isinstance(_cache, Subcommand):
                return self.format(Trace(
                    {"name": _cache.name, "header": [], "description": _cache.help_text}, _cache.args,
                    _cache.separators, _cache.options  # type: ignore
                ))
            return self.format(trace)

        return "\n".join(map(_handle, self.data))

    def format(self, trace: Trace) -> str:
        """help text的生成入口"""
        header = self.header(trace.head, trace.separators)
        param = self.parameters(trace.args)
        body = self.body(trace.body)
        return header % (param, body)

    def param(self, parameter: Arg) -> str:
        """对单个参数的描述"""
        name = parameter.name
        arg = f"[{name}" if parameter.optional else f"<{name}"
        if not parameter.hidden:
            if parameter.value is AllParam:
                return f"<...{name}>"
            if not isinstance(parameter.value, BasePattern) or parameter.value.pattern != name:
                arg += f":{parameter.value}"
            if parameter.field.display is Empty:
                arg += " = None"
            elif parameter.field.display is not None:
                arg += f" = {parameter.field.display} "
        return f"{arg}]" if parameter.optional else f"{arg}>"

    def parameters(self, args: Args) -> str:
        """参数列表的描述"""
        res = ""
        for arg in args.argument:
            if arg.name.startswith('_key_'):
                continue
            if len(arg.separators) == 1:
                sep = ' ' if arg.separators[0] == ' ' else f' {arg.separators[0]!r} '
            else:
                sep = f"[{'|'.join(arg.separators)!r}]"
            res += self.param(arg) + sep
        notice = [(arg.name, arg.notice) for arg in args.argument if arg.notice]
        return f"{res}\n## 注释\n  " + "\n  ".join(f"{v[0]}: {v[1]}" for v in notice) if notice else res

    def header(self, root: Dict[str, Any], separators: Tuple[str, ...]) -> str:
        """头部节点的描述"""
        help_string = f"\n{desc}" if (desc := root.get('description')) else ""
        usage = f"\n用法:\n{usage}" if (usage := root.get('usage')) else ""
        example = f"\n使用示例:\n{example}" if (example := root.get('example')) else ""
        headers = f"[{''.join(map(str, headers))}]" if (headers := root.get('header', [])) != [] else ""
        cmd = f"{headers}{root.get('name', '')}"
        command_string = cmd or (root['name'] + separators[0])
        return f"{command_string} %s{help_string}{usage}\n%s{example}"

    def part(self, node: Union[Subcommand, Option]) -> str:
        """每个子节点的描述"""
        if isinstance(node, Subcommand):
            name = " ".join(node.requires) + (' ' if node.requires else '') + node.name
            option_string = "".join([self.part(i).replace("\n", "\n ") for i in node.options])
            option_help = "## 该子命令内可用的选项有:\n " if option_string else ""
            return (
                f"# {node.help_text}\n"
                f"  {name}{tuple(node.separators)[0]}"
                f"{self.parameters(node.args)}\n"
                f"{option_help}{option_string}"
            )
        elif isinstance(node, Option):
            alias_text = " ".join(node.requires) + (' ' if node.requires else '') + ", ".join(node.aliases)
            return (
                f"# {node.help_text}\n"
                f"  {alias_text}{tuple(node.separators)[0]}"
                f"{self.parameters(node.args)}\n"
            )
        else:
            raise TypeError(f"{node} is not a valid node")

    def body(self, parts: List[Union[Option, Subcommand]]) -> str:
        """子节点列表的描述"""
        option_string = "".join(
            self.part(opt) for opt in filter(lambda x: isinstance(x, Option), parts)
            if opt.name not in self.ignore_names
        )
        subcommand_string = "".join(self.part(sub) for sub in filter(lambda x: isinstance(x, Subcommand), parts))
        option_help = "可用的选项有:\n" if option_string else ""
        subcommand_help = "可用的子命令有:\n" if subcommand_string else ""
        return f"{subcommand_help}{subcommand_string}{option_help}{option_string}"


__all__ = ["TextFormatter", "output_manager", "Trace"]
