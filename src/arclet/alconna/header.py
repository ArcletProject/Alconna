from __future__ import annotations

import re
from copy import deepcopy
from inspect import isclass
from typing import Any, Callable

from nepattern import BasePattern, UnionPattern, all_patterns, type_parser
from nepattern.util import TPattern
from tarina import Empty

from .typing import TPrefixes


def handle_bracket(name: str):
    """处理字符串中的括号对并转为正则表达式"""
    pattern_map = all_patterns()
    mapping = {}
    if len(parts := re.split(r"(\{.*?})", name)) <= 1:
        return name, mapping
    for i, part in enumerate(parts):
        if not part:
            continue
        if part.startswith("{") and part.endswith("}"):
            res = part[1:-1].split(":")
            if not res or (len(res) > 1 and not res[1] and not res[0]):
                parts[i] = ".+?"
            elif len(res) == 1 or not res[1]:
                parts[i] = f"(?P<{res[0]}>.+?)"
            elif not res[0]:
                parts[
                    i
                ] = f"{pattern_map[res[1]].pattern if res[1] in pattern_map else res[1]}"
            elif res[1] in pattern_map:
                mapping[res[0]] = pattern_map[res[1]]
                parts[i] = f"(?P<{res[0]}>{pattern_map[res[1]].pattern})"
            else:
                parts[i] = f"(?P<{res[0]}>{res[1]})"
    return "".join(parts), mapping


class Pair:
    """用于匹配前缀和命令的配对"""
    __slots__ = ("prefix", "pattern", "is_prefix_pat")

    def __init__(self, prefix: Any, pattern: TPattern):
        self.prefix = prefix
        self.pattern = pattern
        self.is_prefix_pat = isinstance(self.prefix, BasePattern)

    def match(self, prefix: Any, command: str, pbfn: Callable[..., ...], comp: bool):
        if not (mat := self.pattern.fullmatch(command)):
            if comp and (mat := self.pattern.match(command)):
                pbfn(command[len(mat[0]):], replace=True)
                command = mat[0]
            else:
                return
        if self.is_prefix_pat and (val := self.prefix.exec(prefix, Empty)).success:
            return (prefix, command), (val.value, command), True, mat.groupdict()
        if not isclass(prefix) and prefix == self.prefix or type(prefix) == self.prefix:
            return (prefix, command), (prefix, command), True, mat.groupdict()


class Double:
    """用于匹配前缀和命令的组合"""
    __slots__ = ("elements", "patterns", "prefix", "command")

    def __init__(self, es: list, pats: UnionPattern | None, prefix: TPattern | None, command: BasePattern | TPattern):
        self.elements = es
        self.patterns = pats
        self.prefix = prefix
        self.command = command

    def match(self, pf: Any, cmd: Any, p_str: bool, c_str: bool, pbfn: Callable[..., ...], comp: bool):
        if self.prefix and p_str:
            if c_str:
                pat = re.compile(self.prefix.pattern + self.command.pattern)
                if mat := pat.fullmatch(pf):
                    pbfn(cmd)
                    return pf, pf, True, mat.groupdict()
                elif mat := pat.fullmatch(name := (pf + cmd)):
                    return name, name, True, mat.groupdict()
                elif comp and (mat := pat.match(pf)):
                    pbfn(cmd)
                    pbfn(pf[len(mat[0]):], replace=True)
                    return mat[0], mat[0], True, mat.groupdict()
                elif comp and (mat := pat.match(name)):
                    pbfn(name[len(mat[0]):], replace=True)
                    return mat[0], mat[0], True, mat.groupdict()
            if (mat := self.prefix.fullmatch(pf)) and (_val := self.command.exec(cmd, Empty)).success:
                return (pf, cmd), (pf, _val.value), True, mat.groupdict()
            elif comp and (mat := self.prefix.fullmatch(pf)) and (
                _val := self.command.prefixed().exec(cmd, Empty)
            ).success:
                if c_str:
                    pbfn(cmd[len(str(_val.value)):], replace=True)
                return (pf, _val.value), (pf, _val.value), True, mat.groupdict()
        if self.patterns and (val := self.patterns.validate(pf, Empty)).success:
            _po, _pr = pf, val.value
        elif (
            self.elements
            and not isclass(pf)
            and (pf in self.elements or type(pf) in self.elements)
        ):
            _po, _pr = pf, pf
        else:
            return
        if self.command.__class__ is TPattern and c_str:
            if mat := self.command.fullmatch(cmd):
                return (_po, cmd), (_pr, cmd), True, mat.groupdict()
            if comp and (mat := self.command.match(cmd)):
                pbfn(cmd[len(mat[0]):], replace=True)
                return (_po, mat[0]), (_pr, mat[0]), True, mat.groupdict()
        elif isinstance(self.command, BasePattern):
            if (_val := self.command.exec(cmd, Empty)).success:
                return (_po, cmd), (_pr, _val.value), True
            if comp and (val := self.command.prefixed().exec(cmd, Empty)).success:
                if c_str:
                    pbfn(cmd[len(str(val.value)):], replace=True)
                return (_po, _val.value), (_pr, _val.value), True


class Header:
    """命令头部的匹配表达式"""
    __slots__ = ("origin", "content", "mapping", "compact")

    def __init__(
        self,
        origin: tuple[str | type | BasePattern, TPrefixes],
        content: TPattern | BasePattern | list[Pair] | Double,
        mapping: dict[str, BasePattern] | None = None,
        compact: bool = False
    ):
        self.origin = origin
        self.content = content
        self.mapping = mapping or {}
        self.compact = compact

    @classmethod
    def generate(
        cls,
        command: str | type | BasePattern,
        prefixes: TPrefixes,
        compact: bool,
    ):
        mapping = {}
        if isinstance(command, str):
            command, mapping = handle_bracket(command)
        _cmd_name: TPattern | BasePattern
        _cmd_str: str
        _cmd_name, _cmd_str = (
            (re.compile(command), command)
            if isinstance(command, str)
            else (deepcopy(type_parser(command)), str(command))
        )
        if not prefixes:
            return cls((command, prefixes), _cmd_name, mapping, compact)
        if isinstance(prefixes[0], tuple):
            return cls(
                (command, prefixes),
                [Pair(h[0], re.compile(re.escape(h[1]) + _cmd_str)) for h in prefixes],
                mapping,
                compact
            )
        elements = []
        patterns = []
        ch_text = ""
        for h in prefixes:
            if isinstance(h, str):
                ch_text += f"{re.escape(h)}|"
            elif isinstance(h, BasePattern):
                patterns.append(h)
            else:
                elements.append(h)
        if not elements and not patterns:
            if isinstance(_cmd_name, TPattern):
                return cls((command, prefixes), re.compile(f"(?:{ch_text[:-1]}){_cmd_str}"), mapping, compact)
            _cmd_name.pattern = f"(?:{ch_text[:-1]}){_cmd_name.pattern}"  # type: ignore
            _cmd_name.regex_pattern = re.compile(_cmd_name.pattern)  # type: ignore
            return cls((command, prefixes), _cmd_name, compact=compact)
        return cls(
            (command, prefixes),
            Double(
                elements,
                UnionPattern(patterns) if patterns else None,
                re.compile(f"(?:{ch_text[:-1]})") if ch_text else None,
                _cmd_name,
            ),
            mapping,
            compact
        )
