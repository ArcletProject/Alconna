from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from weakref import WeakKeyDictionary

from nepattern import ANY, AnyString
from tarina import Empty, lang

from .args import Arg, Args
from .base import Option, Subcommand
from .typing import AllParam

if TYPE_CHECKING:
    from .core import Alconna


def resolve(parts: list[str], options: list[Option | Subcommand]):
    if not parts:
        return None
    pf = parts.pop(0)
    for opt in options:
        if isinstance(opt, Option) and pf in opt.aliases:
            return opt
        if isinstance(opt, Subcommand) and pf == opt.name:
            if not parts:
                return opt
            return sub if (sub := resolve(parts, opt.options)) else opt


@dataclass(eq=True)
class Trace:
    """存放命令节点数据的结构

    该结构用于存放命令节点的数据，包括命令节点的头部、参数、分隔符和主体。
    """

    head: dict[str, Any]
    args: Args
    separators: tuple[str, ...]
    body: list[Option | Subcommand]


class TextFormatter:
    """帮助文档格式化器

    该格式化器负责将传入的命令解析并生成帮助文档字符串
    """

    def __init__(self):
        self.data = WeakKeyDictionary()
        self.ignore_names = set()

    def add(self, base: Alconna):
        """添加目标命令"""
        self.ignore_names.update(base.namespace_config.builtin_option_name["help"])
        self.ignore_names.update(base.namespace_config.builtin_option_name["shortcut"])
        self.ignore_names.update(base.namespace_config.builtin_option_name["completion"])
        res = Trace(
            {
                "name": base.header_display,
                "prefix": [],
                "description": base.meta.description,
                "usage": base.meta.usage,
                "example": base.meta.example,
            },
            base.args,
            base.separators,
            base.options.copy(),
        )
        self.data[base] = res
        return self

    def remove(self, base: Alconna):
        """移除目标命令"""
        self.data.pop(base)

    def format_node(self, parts: list | None = None):
        """格式化命令节点

        Args:
            parts (list | None, optional): 可能的节点路径.
        """

        def _handle(trace: Trace):
            if not parts or parts == [""]:
                return self.format(trace)
            end = resolve(parts, trace.body)
            if isinstance(end, Option):
                return self.format(Trace(
                    {"name": "", "prefix": list(end.aliases), "description": end.help_text}, end.args,
                    end.separators, []
                ))
            if isinstance(end, Subcommand):
                return self.format(Trace(
                    {"name": end.name, "prefix": [], "description": end.help_text}, end.args,
                    _cache.separators, _cache.options  # type: ignore
                ))
            return self.format(trace)

        return "\n".join([_handle(v) for v in self.data.values()])

    def format(self, trace: Trace) -> str:
        """帮助文本的生成入口

        Args:
            trace (Trace): 命令节点数据
        """
        title, desc, usage, example = self.header(trace.head, trace.separators)
        param = self.parameters(trace.args)
        body = self.body(trace.body)
        res = f"{title} {param}\n{desc}"
        if usage:
            res += f"\n{usage}"
        if body:
            res += f"\n\n{body}"
        if example:
            res += f"\n{example}"
        return res

    def param(self, parameter: Arg) -> str:
        """对单个参数的描述

        Args:
            parameter (Arg): 参数单元
        """
        name = parameter.name
        if str(parameter.value).strip("'\"") == name:
            return f"[{name}]" if parameter.optional else name
        if parameter.hidden:
            return f"[{name}]" if parameter.optional else f"<{name}>"
        if parameter.value is AllParam:
            return f"<...{name}>"
        arg = f"[{name}" if parameter.optional else f"<{name}"
        if parameter.value not in (ANY, AnyString):
            arg += f": {parameter.value}"
        if parameter.field.display is not Empty:
            arg += f" = {parameter.field.display}"
        return f"{arg}]" if parameter.optional else f"{arg}>"

    def parameters(self, args: Args) -> str:
        """参数列表的描述

        Args:
            args (Args): 参数列表
        """
        res = ""
        for arg in args.argument:
            if arg.name.startswith("_key_"):
                continue
            if len(arg.separators) == 1:
                sep = " " if arg.separators[0] == " " else f" {arg.separators[0]!r} "
            else:
                sep = f"[{'|'.join(arg.separators)!r}]"
            res += self.param(arg) + sep
        notice = [(arg.name, arg.notice) for arg in args.argument if arg.notice]
        return (
            (f"{res}\n## {lang.require('format', 'notice')}\n  " + "\n  ".join([f"{v[0]}: {v[1]}" for v in notice]))
            if notice
            else res
        )

    def header(self, root: dict[str, Any], separators: tuple[str, ...]) -> tuple[str, str, str, str]:
        """头部节点的描述

        Args:
            root (dict[str, Any]): 头部节点数据
            separators (tuple[str, ...]): 分隔符
        """
        help_string = f"{desc}" if (desc := root.get("description")) else ""
        usage = f"{lang.require('format', 'usage')}:\n{usage}" if (usage := root.get("usage")) else ""
        example = f"{lang.require('format', 'example')}:\n{example}" if (example := root.get("example")) else ""
        prefixs = f"[{''.join(map(str, prefixs))}]" if (prefixs := root.get("prefix", [])) != [] else ""
        cmd = f"{prefixs}{root.get('name', '')}"
        command_string = cmd or (root["name"] + separators[0])
        return command_string, help_string, usage, example

    def opt(self, node: Option) -> str:
        """对单个选项的描述"""
        alias_text = "|".join(node.aliases)
        return (
            f"* {node.help_text}\n"
            f"  {alias_text}{node.separators[0]}{self.parameters(node.args)}\n"
        )

    def sub(self, node: Subcommand) -> str:
        """对单个子命令的描述"""
        opt_string = "".join(
            [self.opt(opt).replace("\n", "\n  ").replace("# ", "* ") for opt in node.options if isinstance(opt, Option)]
        )
        sub_string = "".join(
            [
                self.opt(sub).replace("\n", "\n  ").replace("# ", "* ")  # type: ignore
                for sub in filter(lambda x: isinstance(x, Subcommand), node.options)
            ]
        )
        opt_help = f"  {lang.require('format', 'subcommands.opts')}:\n  " if opt_string else ""
        sub_help = f"  {lang.require('format', 'subcommands.subs')}:\n  " if sub_string else ""
        return (
            f"* {node.help_text}\n"
            f"  {node.name}{tuple(node.separators)[0]}{self.parameters(node.args)}\n"
            f"{sub_help}{sub_string}"
            f"{opt_help}{opt_string}"
        ).rstrip(" ")

    def body(self, parts: list[Option | Subcommand]) -> str:
        """子节点列表的描述"""
        option_string = "".join(
            [self.opt(opt) for opt in parts if isinstance(opt, Option) and opt.name not in self.ignore_names]
        )
        subcommand_string = "".join([self.sub(sub) for sub in parts if isinstance(sub, Subcommand)])
        option_help = f"{lang.require('format', 'options')}:\n" if option_string else ""
        subcommand_help = f"{lang.require('format', 'subcommands')}:\n" if subcommand_string else ""
        return f"{subcommand_help}{subcommand_string}{option_help}{option_string}"


__all__ = ["TextFormatter", "Trace"]
