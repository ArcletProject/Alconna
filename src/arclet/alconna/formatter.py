from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from tarina import Empty, lang
from nepattern import AllParam, BasePattern

from .args import Arg, Args
from .base import Option, Subcommand

if TYPE_CHECKING:
    from .core import Alconna


def resolve_requires(options: list[Option | Subcommand]):
    reqs: dict[str, dict | Option | Subcommand] = {}

    def _u(target, source):
        for k in source:
            if k not in target or isinstance(target[k], (Option, Subcommand)):
                target.update(source)
                break
            _u(target[k], source[k])

    for opt in options:
        if not opt.requires:
            # reqs.setdefault(opt.name, opt)
            [reqs.setdefault(i, opt) for i in opt.aliases] if isinstance(opt, Option) else None
            reqs.setdefault(opt.name, resolve_requires(opt.options)) if isinstance(opt, Subcommand) else None
        else:
            _reqs = _cache = {}
            for req in opt.requires:
                if not _reqs:
                    _reqs[req] = {}
                    _cache = _reqs[req]
                else:
                    _cache[req] = {}
                    _cache = _cache[req]
            # _cache[opt.name] = opt  # type: ignore
            [_cache.setdefault(i, opt) for i in opt.aliases] if isinstance(opt, Option) else None  # type: ignore
            _cache.setdefault(opt.name, resolve_requires(opt.options)) if isinstance(opt, Subcommand) else None
            _u(reqs, _reqs)
    return reqs


def ensure_node(target: str, options: list[Option | Subcommand]):
    for opt in options:
        if isinstance(opt, Option) and target in opt.aliases:
            return opt
        if isinstance(opt, Subcommand):
            return opt if target == opt.name else ensure_node(target, opt.options)


@dataclass(eq=True)
class Trace:
    head: dict[str, Any]
    args: Args
    separators: tuple[str, ...]
    body: list[Option | Subcommand]

    def union(self, others: list[Trace]):
        if not others:
            return self
        if others[0] == self:
            return self.union(others[1:])
        pfs = self.head.copy()
        pfs['prefix'] = list({*self.head['prefix'], *others[0].head['prefix']})
        return Trace(pfs, self.args, self.separators, list({*self.body, *others[0].body})).union(others[1:])


class TextFormatter:
    """帮助文档格式化器

    该格式化器负责将传入的命令节点字典解析并生成帮助文档字符串
    """

    def __init__(self):
        self.data = {}
        self.ignore_names = set()

    def add(self, base: Alconna):
        self.ignore_names.update(base.namespace_config.builtin_option_name['help'])
        self.ignore_names.update(base.namespace_config.builtin_option_name['shortcut'])
        self.ignore_names.update(base.namespace_config.builtin_option_name['completion'])
        pfs = base.prefixes.copy()
        if base.name in pfs:
            pfs.remove(base.name)  # type: ignore
        res = Trace(
            {
                'name': base.name, 'prefix': pfs or [], 'description': base.meta.description,
                'usage': base.meta.usage, 'example': base.meta.example
            },
            base.args, base.separators, base.options.copy()
        )
        self.data.setdefault(base.path, []).append(res)
        return self

    def remove(self, base: Alconna | str):
        if isinstance(base, str):
            self.data.pop(base)
        else:
            with suppress(ValueError):
                self.data.get(base.path, []).remove(base)

    def format_node(self, end: list | None = None):
        """格式化命令节点"""
        def _handle(traces: list[Trace]):
            trace = traces[0].union(traces[1:])
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
                if ensure := ensure_node(_parts[-1], trace.body):
                    _cache = ensure
                else:
                    _opts, _visited = [], set()
                    for k, i in _cache.items():
                        if isinstance(i, dict):
                            _opts.append(Option(k, requires=_parts))
                        elif i not in _visited:
                            _opts.append(i)
                            _visited.add(i)
                    return self.format(Trace(
                        {"name": _parts[-1], 'prefix': [], 'description': _parts[-1]}, Args(), trace.separators,
                        _opts
                    ))
            if isinstance(_cache, Option):
                return self.format(Trace(
                    {"name": "", "prefix": list(_cache.aliases), "description": _cache.help_text}, _cache.args,
                    _cache.separators, []
                ))
            if isinstance(_cache, Subcommand):
                return self.format(Trace(
                    {"name": _cache.name, "prefix": [], "description": _cache.help_text}, _cache.args,
                    _cache.separators, _cache.options  # type: ignore
                ))
            return self.format(trace)

        return "\n".join([_handle(v) for v in self.data.values()])

    def format(self, trace: Trace) -> str:
        """help text的生成入口"""
        prefix = self.header(trace.head, trace.separators)
        param = self.parameters(trace.args)
        body = self.body(trace.body)
        return prefix % (param, body)

    def param(self, parameter: Arg) -> str:
        """对单个参数的描述"""
        name = parameter.name
        arg = f"[{name}" if parameter.optional else f"<{name}"
        if not parameter.hidden:
            if parameter.value is AllParam:
                return f"<...{name}>"
            if not isinstance(parameter.value, BasePattern) or parameter.value.pattern != name:
                arg += f": {parameter.value}"
            if parameter.field.display is Empty:
                arg += " = None"
            elif parameter.field.display is not None:
                arg += f" = {parameter.field.display}"
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
        return (
            f"{res}\n## {lang.require('format', 'notice')}\n  " +
            "\n  ".join([f"{v[0]}: {v[1]}" for v in notice])
        ) if notice else res


    def header(self, root: dict[str, Any], separators: tuple[str, ...]) -> str:
        """头部节点的描述"""
        help_string = f"\n{desc}" if (desc := root.get('description')) else ""
        usage = f"\n{lang.require('format', 'usage')}:\n{usage}" if (usage := root.get('usage')) else ""
        example = f"\n{lang.require('format', 'example')}:\n{example}" if (example := root.get('example')) else ""
        prefixs = f"[{''.join(map(str, prefixs))}]" if (prefixs := root.get('prefix', [])) != [] else ""
        cmd = f"{prefixs}{root.get('name', '')}"
        command_string = cmd or (root['name'] + separators[0])
        return f"{command_string} %s{help_string}{usage}\n\n%s{example}"

    def opt(self, node: Option) -> str:
        """对单个选项的描述"""
        alias_text = " ".join(node.requires) + (' ' if node.requires else '') + "|".join(node.aliases)
        return (
            f"* {node.help_text}\n"
            f"  {alias_text}{node.separators[0]}{self.parameters(node.args)}\n"
        )

    def sub(self, node: Subcommand) -> str:
        """对单个子命令的描述"""
        name = " ".join(node.requires) + (' ' if node.requires else '') + node.name
        opt_string = "".join(
            [
                self.opt(opt).replace("\n", "\n  ").replace("# ", "* ")
                for opt in filter(lambda x: isinstance(x, Option), node.options)
            ]
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
            f"  {name}{tuple(node.separators)[0]}{self.parameters(node.args)}\n"
            f"{sub_help}{sub_string}"
            f"{opt_help}{opt_string}"
        ).rstrip(' ')

    def body(self, parts: list[Option | Subcommand]) -> str:
        """子节点列表的描述"""
        option_string = "".join(
            [
                self.opt(opt) for opt in filter(lambda x: isinstance(x, Option), parts)
                if opt.name not in self.ignore_names
            ]
        )
        subcommand_string = "".join(
            [self.sub(sub) for sub in filter(lambda x: isinstance(x, Subcommand), parts)]
        )
        option_help = f"{lang.require('format', 'options')}:\n" if option_string else ""
        subcommand_help = f"{lang.require('format', 'subcommands')}:\n" if subcommand_string else ""
        return f"{subcommand_help}{subcommand_string}{option_help}{option_string}"


__all__ = ["TextFormatter", "Trace"]
