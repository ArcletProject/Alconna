from __future__ import annotations

import re
from inspect import isclass
from typing import TYPE_CHECKING, Any, Callable

from nepattern import BasePattern, MatchMode, UnionPattern, all_patterns, parser
from nepattern.util import TPattern
from tarina import lang

from ..typing import TPrefixes
from ._util import escape, unescape


def prefixed(pat: BasePattern):
    if pat.mode not in (MatchMode.REGEX_MATCH, MatchMode.REGEX_CONVERT):
        return pat
    new_pat = BasePattern(
        pattern=pat.pattern,
        mode=pat.mode,
        origin=pat.origin,
        converter=pat.converter,
        alias=pat.alias,
        previous=pat.previous,
        validators=pat.validators,
    )
    new_pat.regex_pattern = re.compile(f"^{new_pat.pattern}")
    return new_pat


def handle_bracket(name: str, mapping: dict):
    """处理字符串中的括号对并转为正则表达式"""
    pattern_map = all_patterns()
    name = escape(name)
    if len(parts := re.split(r"(\{.*?})", name)) <= 1:
        return unescape(name), False
    for i, part in enumerate(parts):
        if not part:
            continue
        if part.startswith("{") and part.endswith("}"):
            res = part[1:-1].split(":")
            if not res or (len(res) > 1 and not res[1] and not res[0]):
                parts[i] = ".+?"
            elif len(res) == 1 or not res[1]:
                parts[i] = f"(?P<{res[0]}>.+)"
            elif not res[0]:
                pat = pattern_map.get(res[1], res[1])
                parts[i] = str(pat.pattern if isinstance(pat, BasePattern) else pat)
            elif res[1] in pattern_map:
                mapping[res[0]] = pattern_map[res[1]]
                parts[i] = f"(?P<{res[0]}>{pattern_map[res[1]].pattern})"
            else:
                parts[i] = f"(?P<{res[0]}>{res[1]})"
    return unescape("".join(parts)), True


class Pair:
    """用于匹配前缀和命令的配对"""

    __slots__ = ("prefix", "pattern", "is_prefix_pat", "gd_supplier", "_match")

    def _match1(self, command: str, pbfn: Callable[..., Any], comp: bool):
        if command == self.pattern:
            return command, None
        if comp and command.startswith(self.pattern):
            pbfn(command[len(self.pattern):], replace=True)
            return self.pattern, None
        return None, None
    
    def _match2(self, command: str, pbfn: Callable[..., Any], comp: bool):
        if mat := self.pattern.fullmatch(command):
            return command, mat
        if comp and (mat := self.pattern.match(command)):
            pbfn(command[len(mat[0]):], replace=True)
            return mat[0], mat
        return None, None

    def __init__(self, prefix: Any, pattern: TPattern | str):
        self.prefix = prefix
        self.pattern = pattern
        self.is_prefix_pat = isinstance(self.prefix, BasePattern)
        if isinstance(self.pattern, str):
            self.gd_supplier = lambda mat: None
            self._match = self._match1
        else:
            self.gd_supplier = lambda mat: mat.groupdict()
            self._match = self._match2


    def match(self, _pf: Any, command: str, pbfn: Callable[..., Any], comp: bool):
        cmd, mat = self._match(command, pbfn, comp)
        if cmd is None:
            return
        if self.is_prefix_pat and (val := self.prefix.validate(_pf)).success:
            return (_pf, command), (val._value, command), True, self.gd_supplier(mat)
        if not isclass(_pf) and _pf == self.prefix or _pf.__class__ == self.prefix:
            return (_pf, command), (_pf, command), True, self.gd_supplier(mat)

    def __repr__(self):
        prefix = f"{self.prefix}" if self.is_prefix_pat else self.prefix.__name__ if isinstance(self.prefix, type) else self.prefix.__class__.__name__  # noqa: E501
        pattern = self.pattern if isinstance(self.pattern, str) else self.pattern.pattern
        return f"({prefix}{pattern!r})"


class Double:
    """用于匹配前缀和命令的组合"""

    command: TPattern | BasePattern
    comp_pattern: TPattern | BasePattern

    def __init__(
        self,
        prefixes: TPrefixes,
        command: str | BasePattern,
    ):
        patterns = []
        texts = []
        for h in prefixes:
            if isinstance(h, str):
                texts.append(h)
            elif isinstance(h, BasePattern):
                patterns.append(h)
            else:
                patterns.append(parser(h))
        self.patterns = UnionPattern(patterns)
        if isinstance(command, BasePattern):
            self.command = command
            self.prefix = set(texts) if texts else None
            self.comp_pattern = prefixed(command)
            self.cmd_type = 0
            self.match = self.match0
        elif not texts:
            self.prefix = None
            self.command = re.compile(command)
            self.comp_pattern = re.compile(f"^{command}")
            self.cmd_type = 1
            self.match = self.match1
        else:
            prf = "|".join(re.escape(h) for h in texts)
            self.prefix = re.compile(f"(?:{prf}){command}")
            self.command = re.compile(command)
            self.cmd_type = 2
            self.comp_pattern = re.compile(f"^(?:{prf}){command}")
            self.match = self.match2

    def __repr__(self):
        if self.cmd_type == 0:
            if self.prefix:
                return f"[{'│'.join(self.prefix)}]{self.command}"  # type: ignore
            return str(self.command)
        if self.cmd_type == 1:
            return self.command.pattern
        cmd = self.command.pattern
        prefixes = [str(self.patterns).replace("|", "│")]
        for pf in self.prefix.pattern[:-len(cmd)][3:-1].split("|"):
            for c in '()[]{}?*+-|^$\\.&~# \t\n\r\v\f':
                if f"\\{c}" in pf:
                    pf = pf.replace(f"\\{c}", c)
            prefixes.append(pf)
        return f"[{'│'.join(prefixes)}]{cmd}"

    def match0(self, pf: Any, cmd: Any, p_str: bool, c_str: bool, pbfn: Callable[..., Any], comp: bool):
        if self.prefix and p_str and pf in self.prefix:
            if (val := self.command.validate(cmd)).success:
                return (pf, cmd), (pf, val._value), True, None
            if comp and (val := self.comp_pattern.validate(cmd)).success:
                if c_str:
                    pbfn(cmd[len(str(val._value)):], replace=True)
                return (pf, cmd), (pf, cmd[:len(str(val._value))]), True, None
            return
        if (val := self.patterns.validate(pf)).success:
            if (val2 := self.command.validate(cmd)).success:
                return (pf, cmd), (val._value, val2._value), True, None
            if comp and (val2 := self.comp_pattern.validate(cmd)).success:
                if c_str:
                    pbfn(cmd[len(str(val2._value)):], replace=True)
                return (pf, cmd), (val._value, cmd[:len(str(val2._value))]), True, None
            return

    def match1(self, pf: Any, cmd: Any, p_str: bool, c_str: bool, pbfn: Callable[..., Any], comp: bool):
        if p_str or not c_str:
            return
        if (val := self.patterns.validate(pf)).success and (mat := self.command.fullmatch(cmd)):
            return (pf, cmd), (val._value, cmd), True, mat.groupdict()
        if comp and (mat := self.comp_pattern.match(cmd)):
            pbfn(cmd[len(mat[0]):], replace=True)
            return (pf, cmd), (pf, mat[0]), True, mat.groupdict()

    def match2(self, pf: Any, cmd: Any, p_str: bool, c_str: bool, pbfn: Callable[..., Any], comp: bool):
        if not p_str and not c_str:
            return
        if p_str:
            if mat := self.prefix.fullmatch(pf):
                pbfn(cmd)
                return pf, pf, True, mat.groupdict()
            if comp and (mat := self.comp_pattern.match(pf)):
                pbfn(cmd)
                pbfn(pf[len(mat[0]):], replace=True)
                return mat[0], mat[0], True, mat.groupdict()
            if not c_str:
                return
            if mat := self.prefix.fullmatch((name := pf + cmd)):
                return name, name, True, mat.groupdict()
            if comp and (mat := self.comp_pattern.match(name)):
                pbfn(name[len(mat[0]):], replace=True)
                return mat[0], mat[0], True, mat.groupdict()
            return
        if (val := self.patterns.validate(pf)).success:
            if mat := self.command.fullmatch(cmd):
                return (pf, cmd), (val._value, cmd), True, mat.groupdict()
            if comp and (mat := self.command.match(cmd)):
                pbfn(cmd[len(mat[0]):], replace=True)
                return (pf, cmd), (val._value, mat[0]), True, mat.groupdict()

    if TYPE_CHECKING:
        def match(self, pf: Any, cmd: Any, p_str: bool, c_str: bool, pbfn: Callable[..., Any], comp: bool) -> Any:
            ...


class Header:
    """命令头部的匹配表达式"""

    __slots__ = ("origin", "content", "mapping", "compact", "compact_pattern")

    def __init__(
        self,
        origin: tuple[str | type | BasePattern, TPrefixes],
        content: set[str] | TPattern | BasePattern | list[Pair] | Double,
        mapping: dict[str, BasePattern] | None = None,
        compact: bool = False,
        compact_pattern: TPattern | BasePattern | None = None,
    ):
        self.origin = origin
        self.content = content
        self.mapping = mapping or {}
        self.compact = compact
        self.compact_pattern = compact_pattern

    def __repr__(self):
        if isinstance(self.content, set):
            if not self.origin[1]:
                return self.origin[0]
            if self.origin[0]:
                return f"[{'│'.join(self.origin[1])}]{self.origin[0]}" if len(self.content) > 1 else f"{self.content.copy().pop()}"  # noqa: E501
            return '│'.join(self.origin[1])
        if isinstance(self.content, TPattern):
            if not self.origin[1]:
                return self.origin[0]
            return f"[{'│'.join(self.origin[1])}]{self.origin[0]}"
        if isinstance(self.content, list):
            return "│".join(map(str, self.content))
        return str(self.content)

    @classmethod
    def generate(
        cls,
        command: str | type | BasePattern,
        prefixes: TPrefixes,
        compact: bool,
    ):
        if isinstance(command, str):
            mapping = {}
            if command.startswith("re:"):
                _cmd = command[3:]
                to_regex = True
            else:
                _cmd, to_regex = handle_bracket(command, mapping)
            if not prefixes:
                cmd = re.compile(_cmd) if to_regex else {_cmd}
                return cls((command, prefixes), cmd, mapping, compact, re.compile(f"^{_cmd}"))
            if isinstance(prefixes[0], tuple):
                return cls(
                    (command, prefixes),
                    [Pair(h[0], re.compile(re.escape(h[1]) + _cmd) if to_regex else h[1] + _cmd) for h in prefixes],
                    mapping,
                    compact,
                )
            if all(isinstance(h, str) for h in prefixes):
                prf = "|".join(re.escape(h) for h in prefixes)
                compp = re.compile(f"^(?:{prf}){_cmd}")
                if to_regex:
                    return cls((command, prefixes), re.compile(f"(?:{prf}){_cmd}"), mapping, compact, compp)
                return cls((command, prefixes), {f"{h}{_cmd}" for h in prefixes}, mapping, compact, compp)
            return cls((command, prefixes), Double(prefixes, _cmd), mapping, compact)
        else:
            _cmd = parser(command)
            if not prefixes:
                return cls((command, prefixes), _cmd, {}, compact, prefixed(_cmd))
            if isinstance(prefixes[0], tuple):
                raise TypeError(lang.require("header", "prefix_error"))
            return cls((command, prefixes), Double(prefixes, _cmd), {}, compact)
