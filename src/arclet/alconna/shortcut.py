from __future__ import annotations

import inspect
import re
from typing import Any, TypedDict, Protocol, cast

from tarina import lang
from typing_extensions import NotRequired, TypeAlias

from .exceptions import ArgumentMissing, ParamsUnmatched

class _ShortcutRegWrapper(Protocol):
    def __call__(self, slot: int | str, content: str | None, context: dict[str, Any]) -> Any: ...


class _OldShortcutRegWrapper(Protocol):
    def __call__(self, slot: int | str, content: str | None) -> Any: ...


ShortcutRegWrapper: TypeAlias = "_ShortcutRegWrapper | _OldShortcutRegWrapper"


class ShortcutArgs(TypedDict):
    """快捷指令参数"""

    command: NotRequired[str]
    """快捷指令的命令"""
    args: NotRequired[list[Any]]
    """快捷指令的附带参数"""
    fuzzy: NotRequired[bool]
    """是否允许命令后随参数"""
    prefix: NotRequired[bool]
    """是否调用时保留指令前缀"""
    wrapper: NotRequired[ShortcutRegWrapper]
    """快捷指令的正则匹配结果的额外处理函数"""
    humanized: NotRequired[str]
    """快捷指令的人类可读描述"""


DEFAULT_WRAPPER = lambda slot, content, context: content


class InnerShortcutArgs:
    command: str
    args: list[Any]
    fuzzy: bool
    prefix: bool
    prefixes: list[str]
    wrapper: _ShortcutRegWrapper
    flags: int | re.RegexFlag

    __slots__ = ("command", "args", "fuzzy", "prefix", "prefixes", "wrapper", "flags")

    def __init__(
        self,
        command: str,
        args: list[Any] | None = None,
        fuzzy: bool = True,
        prefix: bool = False,
        prefixes: list[str] | None = None,
        wrapper: ShortcutRegWrapper | None = None,
        flags: int | re.RegexFlag = 0,
    ):
        self.command = command
        self.args = args or []
        self.fuzzy = fuzzy
        self.prefix = prefix
        self.prefixes = prefixes or []
        if not wrapper:
            self.wrapper = DEFAULT_WRAPPER
        else:
            params = inspect.signature(wrapper).parameters
            if len(params) > 3:
                self.wrapper = cast(_ShortcutRegWrapper, wrapper)
            elif len(params) < 3 or "self" in params:
                wrapper = cast(_OldShortcutRegWrapper, wrapper)
                self.wrapper = cast(_ShortcutRegWrapper, lambda slot, content, context: wrapper(slot, content))
            else:
                self.wrapper = cast(_ShortcutRegWrapper, wrapper)
        self.flags = flags

    def __repr__(self):
        return f"ShortcutArgs({self.command!r}, args={self.args!r}, fuzzy={self.fuzzy}, prefix={self.prefix})"

    def dump(self):
        return {
            "command": self.command,
            "args": self.args,
            "fuzzy": self.fuzzy,
            "prefix": self.prefix,
            "prefixes": self.prefixes,
            "flags": self.flags,
        }

    @classmethod
    def load(cls, data: dict[str, Any]) -> InnerShortcutArgs:
        return cls(
            data["command"],
            data.get("args"),
            data.get("fuzzy", True),
            data.get("prefix", False),
            data.get("prefixes"),
            data.get("wrapper"),
            data.get("flags", 0),
        )


ESCAPE = {"\\": "\x01", "[": "\x01", "]": "\x02", "{": "\x03", "}": "\x04", "|": "\x05"}
R_ESCAPE = {v: k for k, v in ESCAPE.items()}


def escape(string: str) -> str:
    """转义字符串"""
    for k, v in ESCAPE.items():
        string = string.replace("\\" + k, v)
    return string


def unescape(string: str) -> str:
    """逆转义字符串, 自动去除空白符"""
    for k, v in R_ESCAPE.items():
        string = string.replace(k, v)
    return string.strip()


INDEX_SLOT = re.compile(r"\{%(\d+)\}")
WILDCARD_SLOT = re.compile(r"\{\*(.*)\}", re.DOTALL)


def _gen_extend(data: list, sep: str):
    extend = []
    for slot in data:
        if isinstance(slot, str) and extend and isinstance(extend[-1], str):
            extend[-1] += sep + slot
        else:
            extend.append(slot)
    return extend


def _handle_multi_slot(result: list, unit: str, data: list, index: int, current: int, offset: int):
    slot = data[index]
    if not isinstance(slot, str):
        left, right = unit.split(f"{{%{index}}}", 1)
        if left.strip():
            result[current] = left.strip()
        result.insert(current + 1, slot)
        if right.strip():
            result[current + 2] = right.strip()
            offset += 1
    else:
        result[current + offset] = unescape(unit.replace(f"{{%{index}}}", slot))
    return offset


def _handle_shortcut_data(result: list, data: list):
    data_len = len(data)
    record = set()
    offset = 0
    for i, unit in enumerate(result.copy()):
        if not isinstance(unit, str):
            continue
        unit = escape(unit)
        if mat := INDEX_SLOT.fullmatch(unit):
            index = int(mat[1])
            if index >= data_len:
                continue
            result[i + offset] = data[index]
            record.add(index)
        elif res := INDEX_SLOT.findall(unit):
            for index in map(int, res):
                if index >= data_len:
                    continue
                offset = _handle_multi_slot(result, unit, data, index, i, offset)
                record.add(index)
        elif mat := WILDCARD_SLOT.search(unit):
            extend = _gen_extend(data, mat[1] or " ")
            if unit == f"{{*{mat[1]}}}":
                result.extend(extend)
            else:
                result[i + offset] = unescape(unit.replace(f"{{*{mat[1]}}}", "".join(map(str, extend))))
            data.clear()
            break

    # def recover_quote(_unit):
    #     if isinstance(_unit, str) and any(_unit.count(sep) for sep in argv.separators) and not (_unit[0] in ('"', "'") and _unit[0] == _unit[-1]):
    #         return f'"{_unit}"'
    #     return _unit

    return [unit for i, unit in enumerate(data) if i not in record]


INDEX_REG_SLOT = re.compile(r"\{(\d+)\}")
KEY_REG_SLOT = re.compile(r"\{(\w+)\}")


def _handle_shortcut_reg(result: list, groups: tuple[str, ...], gdict: dict[str, str], wrapper: _ShortcutRegWrapper, ctx: dict[str, Any]):
    data = []
    for unit in result:
        if not isinstance(unit, str):
            data.append(unit)
            continue
        unit = escape(unit)
        if mat := INDEX_REG_SLOT.fullmatch(unit):
            index = int(mat[1])
            if index >= len(groups):
                continue
            slot = groups[index]
            data.append(wrapper(index, slot, ctx))
            continue
        if mat := KEY_REG_SLOT.fullmatch(unit):
            key = mat[1]
            if key not in gdict:
                continue
            slot = gdict[key]
            data.append(wrapper(key, slot, ctx))
            continue
        if mat := INDEX_REG_SLOT.findall(unit):
            for index in map(int, mat):
                if index >= len(groups):
                    unit = unit.replace(f"{{{index}}}", "")
                    continue
                slot = groups[index]
                unit = unit.replace(f"{{{index}}}", str(wrapper(index, slot, ctx) or ""))
        if mat := KEY_REG_SLOT.findall(unit):
            for key in mat:
                if key not in gdict:
                    unit = unit.replace(f"{{{key}}}", "")
                    continue
                slot = gdict[key]
                unit = unit.replace(f"{{{key}}}", str(wrapper(key, slot, ctx) or ""))
        if unit:
            data.append(unescape(unit))
    return data


def wrap_shortcut(
    data: list[Any], short: InnerShortcutArgs, reg: re.Match | None = None, ctx: dict[str, Any] | None = None
) -> list[Any]:
    """处理被触发的快捷命令

    Args:
        data (list[Any]): 剩余参数
        short (InnerShortcutArgs): 快捷命令
        reg (Match | None): 可能的正则匹配结果
        ctx (dict[str, Any] | None): 上下文
    Returns:
        list[Any]: 处理后的参数

    Raises:
        ParamsUnmatched: 若不允许快捷命令后随其他参数，则抛出此异常
    """
    result = [short.command]
    if not short.fuzzy and data:
        raise ParamsUnmatched(lang.require("analyser", "param_unmatched").format(target=data[0]))
    result.extend(short.args)
    data = _handle_shortcut_data(result, data)
    if not data and result and any(
        isinstance(i, str) and bool(re.search(r"\{%(\d+)|\*(.*?)\}", i)) for i in result
    ):
        raise ArgumentMissing(lang.require("analyser", "param_missing"))
    result.extend(data)
    if reg:
        data = _handle_shortcut_reg(result, reg.groups(), reg.groupdict(), short.wrapper, ctx or {})
        result.clear()
        result.extend(data)
    return result


def find_shortcut(table: dict[str, InnerShortcutArgs], data: list, separators: str = " "):
    query = data.pop(0)
    if not isinstance(query, str):
        return
    while True:
        if query in table:
            return query, data, table[query], None
        for key, args in table.items():
            if args.fuzzy and (mat := re.match(f"^{key}", query, args.flags)):
                if len(query) > mat.span()[1]:
                    data.insert(0, query[mat.span()[1]:].lstrip(separators))
                return query, data, args, mat
            elif mat := re.fullmatch(key, query, args.flags):
                if not (not args.fuzzy and data):
                    return query, data, table[key], mat
        if not data:
            break
        next_data = data.pop(0)
        if not isinstance(next_data, str):
            break
        query += f"{separators}{next_data}"
    return


def execute_shortcut(table: dict[str, InnerShortcutArgs], data: list, separators: str = " ", ctx: dict[str, Any] | None = None):
    """执行快捷命令

    Args:
        table (dict[str, InnerShortcutArgs]): 快捷命令表
        data (list): 参数列表
        separators (str, optional): 参数分隔符. Defaults to " ".
        ctx (dict[str, Any], optional): 上下文. Defaults to {}.

    Returns:
        list: 处理后的参数列表
    """
    if res := find_shortcut(table, data.copy(), separators):
        return wrap_shortcut(*res[1:], ctx=ctx or {})
    return data
