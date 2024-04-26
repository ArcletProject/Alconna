from __future__ import annotations

import re
from inspect import isclass
from typing import TYPE_CHECKING, Any, Callable, TypeVar, Generic

from nepattern import BasePattern, MatchMode, UnionPattern, all_patterns, parser
from nepattern.util import TPattern
from tarina import lang

from ..typing import TPrefixes
from ._util import escape, unescape


def prefixed(pat: BasePattern):
    if pat.mode not in (MatchMode.REGEX_MATCH, MatchMode.REGEX_CONVERT):
        return pat
    new_pat = pat.copy()
    new_pat.regex_pattern = re.compile(f"^{new_pat.pattern}")
    return new_pat


regex_patterns = {
    "str": r".+",
    "int": r"\-?\d+",
    "float": r"\-?\d+\.?\d*",
    "number": r"\-?\d+(?:\.\d*)?",
    "bool": "(?i:True|False)",
    "list": r"\[.+?\]",
    "tuple": r"\(.+?\)",
    "set": r"\{.+?\}",
    "dict": r"\{.+?\}",
}


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
                parts[i] = regex_patterns.get(res[1], str(pat.pattern if isinstance(pat, BasePattern) else pat))
            elif res[1] in pattern_map:
                mapping[res[0]] = pattern_map[res[1]]
                pat = regex_patterns.get(res[1], str(pattern_map[res[1]].pattern))
                parts[i] = f"(?P<{res[0]}>{pat})"
            else:
                parts[i] = f"(?P<{res[0]}>{res[1]})"
    return unescape("".join(parts)), True


TP = TypeVar("TP", TPattern, str)


class Pair(Generic[TP]):
    """用于匹配前缀和命令的配对"""

    __slots__ = ("prefix", "pattern", "is_prefix_pat", "gd_supplier", "_match")

    def _match1(self: "Pair[str]", command: str, rbfn: Callable[..., Any], comp: bool):
        if command == self.pattern:
            return command, None
        if comp and command.startswith(self.pattern):
            rbfn(command[len(self.pattern):], replace=True)
            return self.pattern, None
        return None, None

    def _match2(self: "Pair[TPattern]", command: str, rbfn: Callable[..., Any], comp: bool):
        if mat := self.pattern.fullmatch(command):
            return command, mat
        if comp and (mat := self.pattern.match(command)):
            rbfn(command[len(mat[0]):], replace=True)
            return mat[0], mat
        return None, None

    def __init__(self, prefix: Any, pattern: TP):
        self.prefix = prefix
        self.pattern: TP = pattern
        self.is_prefix_pat = isinstance(self.prefix, BasePattern)
        if isinstance(self.pattern, str):
            self.gd_supplier = lambda mat: None
            self._match = self._match1  # type: ignore
        else:
            self.gd_supplier = lambda mat: mat.groupdict()
            self._match = self._match2  # type: ignore

    def match(self, _pf: Any, command: str, rbfn: Callable[..., Any], comp: bool):
        cmd, mat = self._match(command, rbfn, comp)
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


TC = TypeVar("TC", TPattern, BasePattern)
TP1 = TypeVar("TP1", TPattern, "set[str] | None")


class Double(Generic[TC, TP1]):
    """用于匹配前缀和命令的组合"""

    command: TC
    comp_pattern: TC
    prefix: TP1
    flag: int

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
        self.patterns: UnionPattern = UnionPattern(patterns)
        if isinstance(command, BasePattern):
            _self0: Double[BasePattern, set[str] | None] = self  # type: ignore
            _self0.command = command
            _self0.prefix = set(texts) if texts else None
            _self0.comp_pattern = prefixed(command)
            _self0.flag = 0
            _self0.match = _self0.match0
        elif not texts:
            _self1: Double[TPattern, None] = self  # type: ignore
            _self1.prefix = None
            _self1.command = re.compile(command)
            _self1.comp_pattern = re.compile(f"^{command}")
            _self1.flag = 1
            _self1.match = _self1.match1
        else:
            _self2: Double[TPattern, TPattern] = self  # type: ignore
            prf = "|".join(re.escape(h) for h in texts)
            _self2.prefix = re.compile(f"(?:{prf}){command}")
            _self2.command = re.compile(command)
            _self2.flag = 2
            _self2.comp_pattern = re.compile(f"^(?:{prf}){command}")
            _self2.match = _self2.match2

    def __repr__(self):
        if self.flag == 0:
            if self.prefix:
                return f"[{'│'.join(self.prefix)}]{self.command}"  # type: ignore
            return str(self.command)
        if self.flag == 1:
            return self.command.pattern
        _self: Double[TPattern, TPattern] = self  # type: ignore
        cmd = self.command.pattern
        prefixes = [str(_self.patterns).replace("|", "│")]
        for pf in _self.prefix.pattern[:-len(cmd)][3:-1].split("|"):
            for c in '()[]{}?*+-|^$\\.&~# \t\n\r\v\f':
                if f"\\{c}" in pf:
                    pf = pf.replace(f"\\{c}", c)
            prefixes.append(pf)
        return f"[{'│'.join(prefixes)}]{cmd}"

    def match0(self: "Double[BasePattern, set[str] | None]", pf: Any, cmd: Any, p_str: bool, c_str: bool, rbfn: Callable[..., Any], comp: bool):
        if self.prefix and p_str and pf in self.prefix:
            if (val := self.command.validate(cmd)).success:
                return (pf, cmd), (pf, val._value), True, None
            if comp and (val := self.comp_pattern.validate(cmd)).success:
                if c_str:
                    rbfn(cmd[len(str(val._value)):], replace=True)
                return (pf, cmd), (pf, cmd[:len(str(val._value))]), True, None
            return
        if (val := self.patterns.validate(pf)).success:
            if (val2 := self.command.validate(cmd)).success:
                return (pf, cmd), (val._value, val2._value), True, None
            if comp and (val2 := self.comp_pattern.validate(cmd)).success:
                if c_str:
                    rbfn(cmd[len(str(val2._value)):], replace=True)
                return (pf, cmd), (val._value, cmd[:len(str(val2._value))]), True, None
            return

    def match1(self: "Double[TPattern, None]", pf: Any, cmd: Any, p_str: bool, c_str: bool, rbfn: Callable[..., Any], comp: bool):
        if p_str or not c_str:
            return
        if (val := self.patterns.validate(pf)).success and (mat := self.command.fullmatch(cmd)):
            return (pf, cmd), (val._value, cmd), True, mat.groupdict()
        if comp and (mat := self.comp_pattern.match(cmd)):
            rbfn(cmd[len(mat[0]):], replace=True)
            return (pf, cmd), (pf, mat[0]), True, mat.groupdict()

    def match2(self: "Double[TPattern, TPattern]", pf: Any, cmd: Any, p_str: bool, c_str: bool, rbfn: Callable[..., Any], comp: bool):
        if not p_str and not c_str:
            return
        if p_str:
            if mat := self.prefix.fullmatch(pf):
                rbfn(cmd)
                return pf, pf, True, mat.groupdict()
            if comp and (mat := self.comp_pattern.match(pf)):
                rbfn(cmd)
                rbfn(pf[len(mat[0]):], replace=True)
                return mat[0], mat[0], True, mat.groupdict()
            if not c_str:
                return
            if mat := self.prefix.fullmatch((name := pf + cmd)):
                return name, name, True, mat.groupdict()
            if comp and (mat := self.comp_pattern.match(name)):
                rbfn(name[len(mat[0]):], replace=True)
                return mat[0], mat[0], True, mat.groupdict()
            return
        if (val := self.patterns.validate(pf)).success:
            if mat := self.command.fullmatch(cmd):
                return (pf, cmd), (val._value, cmd), True, mat.groupdict()
            if comp and (mat := self.command.match(cmd)):
                rbfn(cmd[len(mat[0]):], replace=True)
                return (pf, cmd), (val._value, mat[0]), True, mat.groupdict()

    if TYPE_CHECKING:
        def match(self, pf: Any, cmd: Any, p_str: bool, c_str: bool, rbfn: Callable[..., Any], comp: bool) -> Any:
            ...


TContent = TypeVar("TContent", TPattern, "set[str]", "list[Pair]", Double, BasePattern)
TCompact = TypeVar("TCompact", TPattern, BasePattern, None)


class Header(Generic[TContent, TCompact]):
    """命令头部的匹配表达式"""

    __slots__ = ("origin", "content", "mapping", "compact", "compact_pattern", "flag")

    def __init__(
        self,
        origin: tuple[str | BasePattern, TPrefixes],
        content: set[str] | TPattern | BasePattern | list[Pair] | Double,
        mapping: dict[str, BasePattern] | None = None,
        compact: bool = False,
        compact_pattern: TPattern | BasePattern | None = None,
    ):
        self.origin = origin  # type: ignore
        self.content: TContent = content  # type: ignore
        self.mapping = mapping or {}
        self.compact = compact
        self.compact_pattern: TCompact = compact_pattern  # type: ignore

        if isinstance(self.content, set):
            self.flag = 0
        elif isinstance(self.content, TPattern):  # type: ignore
            self.flag = 1
        elif isinstance(self.content, BasePattern):
            self.flag = 2
        elif isinstance(self.content, list):
            self.flag = 3
        else:
            self.flag = 4

    def __repr__(self):
        if isinstance(self.content, set):
            self.origin: tuple[str, list[str]]
            if not self.origin[1]:
                return self.origin[0]
            if self.origin[0]:
                return f"[{'│'.join(self.origin[1])}]{self.origin[0]}" if len(self.content) > 1 else f"{self.content.copy().pop()}"  # noqa: E501
            return '│'.join(self.origin[1])
        if isinstance(self.content, TPattern):  # type: ignore
            self.origin: tuple[str, list[str]]
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
            if isinstance(prefixes[0], tuple):  # prefixes: List[Tuple[Any, str]]
                _prefixes: list[tuple[Any, str]] = prefixes  # type: ignore
                return cls(
                    (command, prefixes),
                    [Pair(h[0], re.compile(re.escape(h[1]) + _cmd) if to_regex else h[1] + _cmd) for h in _prefixes],
                    mapping,
                    compact,
                )
            if all(isinstance(h, str) for h in prefixes):
                _prefixes: list[str] = prefixes  # type: ignore
                prf = "|".join(re.escape(h) for h in _prefixes)
                compp = re.compile(f"^(?:{prf}){_cmd}")
                if to_regex:
                    return cls((command, prefixes), re.compile(f"(?:{prf}){_cmd}"), mapping, compact, compp)
                return cls((command, prefixes), {f"{h}{_cmd}" for h in prefixes}, mapping, compact, compp)
            return cls((command, prefixes), Double(prefixes, _cmd), mapping, compact)
        else:
            _cmd = parser(command)
            if not prefixes:
                return cls((_cmd, prefixes), _cmd, {}, compact, prefixed(_cmd))
            if isinstance(prefixes[0], tuple):
                raise TypeError(lang.require("header", "prefix_error"))
            return cls((_cmd, prefixes), Double(prefixes, _cmd), {}, compact)
