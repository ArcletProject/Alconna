from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

from nepattern import ANY, AnyString
from tarina import Empty, lang

from .args import Arg, _Args
from .base import Option, Subcommand
from .typing import AllParam
from .shortcut import InnerShortcutArgs

if TYPE_CHECKING:
    from .core import Alconna


def ensure_node(targets: list[str], options: list[Option | Subcommand], record: list) -> Option | Subcommand | None:
    if not targets:
        return None
    pf = targets.pop(0)
    for opt in options:
        if isinstance(opt, Option) and pf in opt.aliases:
            record.append(pf)
            return opt
        if isinstance(opt, Subcommand) and pf in opt.aliases:
            record.append(pf)
            if not targets:
                return opt
            return sub if (sub := ensure_node(targets, opt.options, record)) else opt
    return ensure_node(targets, options, record)


class TraceHead(TypedDict):
    name: str
    description: str
    usage: str | None
    example: str | None


@dataclass(eq=True)
class Trace:
    """存放命令节点数据的结构

    该结构用于存放命令节点的数据，包括命令节点的头部、参数、分隔符和主体。
    """

    head: TraceHead
    args: _Args
    separators: str
    body: list[Option | Subcommand]
    shortcuts: dict[str, Any]


class TextFormatter:
    """帮助文档格式化器

    该格式化器负责将传入的命令解析并生成帮助文档字符串
    """

    def __init__(self):
        self.data: "dict[int, Trace]" = {}
        self.ignore_names = set()

    def add(self, base: Alconna):
        """添加目标命令"""
        self.ignore_names.update(base.config.builtin_option_name["help"])
        self.ignore_names.update(base.config.builtin_option_name["shortcut"])
        self.ignore_names.update(base.config.builtin_option_name["completion"])
        res = Trace(
            {
                "name": base.header_display,
                "description": base.meta.description,
                "usage": base.meta.usage,
                "example": base.meta.example,
            },
            base.args,
            base.separators,
            base.options.copy(),
            {} if base.config.hide_shortcut else base._get_shortcuts(),
        )
        self.data[base._hash] = res
        return self

    def update_shortcut(self, base: Alconna):
        """更新目标命令的快捷指令"""
        if not base.config.hide_shortcut:
            self.data[base._hash].shortcuts = base._get_shortcuts()
        return self

    def remove(self, base: Alconna):
        """移除目标命令"""
        self.data.pop(base._hash)

    def format_node(self, parts: list | None = None):
        """格式化命令节点

        Args:
            parts (list | None, optional): 可能的节点路径.
        """

        def _handle(trace: Trace):
            if not parts or parts == [""]:
                return self.format(trace)
            rec = []
            prefix = parts[0]
            end = ensure_node(parts, trace.body, rec)
            if not end:
                return self.format(trace)
            if len(rec) > 1:
                prefix += trace.separators[0] + trace.separators[0].join(rec[:-1])
            if isinstance(end, Option):
                return self.format(
                    Trace({"name": prefix + trace.separators[0] + "│".join(sorted(end.aliases)), "description": end.help_text, 'example': None, 'usage': None}, end.args, end.separators, [], {})  # noqa: E501
                )
            if isinstance(end, Subcommand):
                return self.format(
                    Trace({"name": prefix + trace.separators[0] + "│".join(sorted(end.aliases)), "description": end.help_text, 'example': None, 'usage': None}, end.args, end.separators, end.options, {})  # noqa: E501
                )
            return self.format(trace)

        return "\n".join([_handle(v) for v in self.data.values()])

    def format(self, trace: Trace) -> str:
        """帮助文本的生成入口

        Args:
            trace (Trace): 命令节点数据
        """
        title, desc, usage, example = self.header(trace.head)
        param = self.parameters(trace.args)
        body = self.body(trace.body)
        res = f"{title}{trace.separators[0]}{param}\n{desc}"
        shortcuts = self.shortcut(trace.shortcuts)
        if usage:
            res += f"\n{usage}"
        if body:
            res += f"\n\n{body}"
        if example:
            res += f"\n{example}"
        if shortcuts:
            res += f"\n{shortcuts}"
        return res

    def param(self, parameter: Arg) -> str:
        """对单个参数的描述

        Args:
            parameter (Arg): 参数单元
        """
        name = parameter.name
        if str(parameter.type_).strip("'\"") == name:
            return f"[{name}]" if parameter.field.optional else name
        if parameter.field.hidden:
            return f"[{name}]" if parameter.field.optional else f"<{name}>"
        if parameter.type_ is AllParam:
            return f"<...{name}>"
        arg = f"[{name}" if parameter.field.optional else f"<{name}"
        if parameter.type_ not in (ANY, AnyString):
            arg += f": {parameter.type_}"
        if parameter.field.display is not Empty:
            arg += f" = {parameter.field.display}"
        return f"{arg}]" if parameter.field.optional else f"{arg}>"

    def parameters(self, args: _Args) -> str:
        """参数列表的描述

        Args:
            args (Args): 参数列表
        """
        res = ""
        for arg in args.data:
            if arg.name.startswith("_key_"):
                continue
            if len(arg.separators) == 1:
                sep = " " if arg.separators[0] == " " else f" {arg.separators[0]!r} "
            else:
                sep = f"[{'|'.join(arg.separators)!r}]"
            res += self.param(arg) + sep
        notice = [(arg.name, arg.field.notice) for arg in args.data if arg.field.notice]
        return (
            (f"{res}\n## {lang.require('format', 'notice')}\n  " + "\n  ".join([f"{v[0]}: {v[1]}" for v in notice]))
            if notice
            else res
        )

    def header(self, root: TraceHead) -> tuple[str, str, str, str]:
        """头部节点的描述

        Args:
            root (TraceHead): 头部节点数据
        """
        help_string = f"{desc}" if (desc := root["description"]) else ""
        usage = f"{lang.require('format', 'usage')}:\n{usage}" if (usage := root.get("usage")) else ""
        example = f"{lang.require('format', 'example')}:\n{example}" if (example := root.get("example")) else ""
        return root["name"], help_string, usage, example

    def opt(self, node: Option) -> str:
        """对单个选项的描述"""
        alias_text = "│".join(node.aliases)
        return f"* {node.help_text}\n" f"  {alias_text}{node.separators[0]}{self.parameters(node.args)}\n"

    def sub(self, node: Subcommand) -> str:
        """对单个子命令的描述"""
        alias_text = "│".join(node.aliases)
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
            f"  {alias_text}{node.separators[0]}{self.parameters(node.args)}\n"
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

    def shortcut(self, shortcuts: dict[str, Any]) -> str:
        """快捷指令的描述"""
        if not shortcuts:
            return ""
        result = []
        for key, short in shortcuts.items():
            if isinstance(short, InnerShortcutArgs):
                _key = key + (" ...args" if short.fuzzy else "")
                prefixes = f"[{'│'.join(short.prefixes)}]" if short.prefixes else ""
                result.append(f"'{prefixes}{_key}' => {prefixes}{short.command} {' '.join(map(str, short.args))}")
            else:
                result.append(f"'{key}' => {short.origin!r}")
        return f"{lang.require('format', 'shortcuts')}:\n" + "\n".join(result)


__all__ = ["TextFormatter", "Trace", "TraceHead"]
