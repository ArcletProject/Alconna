from __future__ import annotations

import re
from typing import Any

from tarina import lang

from .exceptions import ArgumentMissing, ParamsUnmatched
from .typing import InnerShortcutArgs, _ShortcutRegWrapper


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
