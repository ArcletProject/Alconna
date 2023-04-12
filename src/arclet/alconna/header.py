from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from inspect import isclass
from typing import Any, Callable

from nepattern import BasePattern, UnionPattern, all_patterns, type_parser
from nepattern.util import TPattern
from tarina import Empty


def handle_bracket(name: str):
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


@dataclass
class Pair:
    prefix: Any
    pattern: TPattern
    is_prefix_pat: bool = field(default=False, init=False)

    def __post_init__(self):
        self.is_prefix_pat = isinstance(self.prefix, BasePattern)

    def match(self, prefix: Any, command: str):
        if mat := self.pattern.fullmatch(command):
            if self.is_prefix_pat and (val := self.prefix(prefix, Empty)).success:
                return (prefix, command), (val.value, command), True, mat.groupdict()
            if (
                not isclass(prefix)
                and prefix == self.prefix
                or type(prefix) == self.prefix
            ):
                return (prefix, command), (prefix, command), True, mat.groupdict()


@dataclass
class Double:
    elements: list[Any]
    patterns: UnionPattern | None
    prefix: TPattern | None
    command: BasePattern | TPattern

    def match(
        self,
        prefix: Any,
        command: Any,
        prefix_str: bool,
        command_str: bool,
        pushback_fn: Callable[[str], ...],
    ):
        if self.prefix and prefix_str:
            if command_str:
                pat = re.compile(self.prefix.pattern + self.command.pattern)
                if mat := pat.fullmatch(prefix):
                    pushback_fn(command)
                    return prefix, prefix, True, mat.groupdict()
                elif mat := pat.fullmatch(name := (prefix + command)):
                    return name, name, True, mat.groupdict()
            if (mat := self.prefix.fullmatch(prefix)) and (
                _val := self.command(command, Empty)
            ).success:
                return (prefix, command), (prefix, _val.value), True, mat.groupdict()
        if self.patterns and (val := self.patterns.validate(prefix, Empty)).success:
            _po, _pr = prefix, val.value
        elif (
            self.elements
            and not isclass(prefix)
            and (prefix in self.elements or type(prefix) in self.elements)
        ):
            _po, _pr = prefix, prefix
        else:
            return
        if (
            isinstance(self.command, TPattern)
            and command_str
            and (mat := self.command.fullmatch(command))
        ):
            return (_po, command), (_pr, command), True, mat.groupdict()
        elif (
            isinstance(self.command, BasePattern)
            and (_val := self.command(command, Empty)).success
        ):
            return (_po, command), (_pr, _val.value), True


@dataclass
class Header:
    content: TPattern | BasePattern | list[Pair] | Double
    mapping: dict[str, BasePattern] = field(default_factory=dict)

    @classmethod
    def generate(
        cls,
        command: str | type | BasePattern,
        headers: list[Any] | list[tuple[Any, str]],
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
        if not headers:
            return cls(_cmd_name, mapping)
        if isinstance(headers[0], tuple):
            return cls(
                [Pair(h[0], re.compile(re.escape(h[1]) + _cmd_str)) for h in headers],
                mapping,
            )
        elements = []
        patterns = []
        ch_text = ""
        for h in headers:
            if isinstance(h, str):
                ch_text += f"{re.escape(h)}|"
            elif isinstance(h, BasePattern):
                patterns.append(h)
            else:
                elements.append(h)
        if not elements and not patterns:
            if isinstance(_cmd_name, TPattern):
                return cls(re.compile(f"(?:{ch_text[:-1]}){_cmd_str}"), mapping)
            _cmd_name.pattern = f"(?:{ch_text[:-1]}){_cmd_name.pattern}"  # type: ignore
            _cmd_name.regex_pattern = re.compile(_cmd_name.pattern)  # type: ignore
            return cls(_cmd_name)
        return cls(
            Double(
                elements,
                UnionPattern(patterns) if patterns else None,
                re.compile(f"(?:{ch_text[:-1]})") if ch_text else None,
                _cmd_name,
            ),
            mapping,
        )
