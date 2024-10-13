from __future__ import annotations

import re
from typing import Any

from tarina import lang

from .. import Arparma
from ..exceptions import ArgumentMissing, ParamsUnmatched
from ..typing import _ShortcutRegWrapper, TDC, InnerShortcutArgs
from ._util import escape, unescape
from ._argv import Argv


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


def _handle_multi_slot(argv: Argv, unit: str, data: list, index: int, current: int, offset: int):
    slot = data[index]
    if not isinstance(slot, str):
        left, right = unit.split(f"{{%{index}}}", 1)
        if left.strip():
            argv.raw_data[current] = left.strip()
        argv.raw_data.insert(current + 1, slot)
        if right.strip():
            argv.raw_data[current + 2] = right.strip()
            offset += 1
    else:
        argv.raw_data[current + offset] = unescape(unit.replace(f"{{%{index}}}", slot))
    return offset


def _handle_shortcut_data(argv: Argv, data: list):
    data_len = len(data)
    record = set()
    offset = 0
    for i, unit in enumerate(argv.raw_data.copy()):
        if not isinstance(unit, str):
            continue
        unit = escape(unit)
        if mat := INDEX_SLOT.fullmatch(unit):
            index = int(mat[1])
            if index >= data_len:
                continue
            argv.raw_data[i + offset] = data[index]
            record.add(index)
        elif res := INDEX_SLOT.findall(unit):
            for index in map(int, res):
                if index >= data_len:
                    continue
                offset = _handle_multi_slot(argv, unit, data, index, i, offset)
                record.add(index)
        elif mat := WILDCARD_SLOT.search(unit):
            extend = _gen_extend(data, mat[1] or " ")
            if unit == f"{{*{mat[1]}}}":
                argv.raw_data.extend(extend)
            else:
                argv.raw_data[i + offset] = unescape(unit.replace(f"{{*{mat[1]}}}", "".join(map(str, extend))))
            data.clear()
            break

    def recover_quote(_unit):
        if isinstance(_unit, str) and any(_unit.count(sep) for sep in argv.separators) and not (_unit[0] in ('"', "'") and _unit[0] == _unit[-1]):
            return f'"{_unit}"'
        return _unit

    return [recover_quote(unit) for i, unit in enumerate(data) if i not in record]


INDEX_REG_SLOT = re.compile(r"\{(\d+)\}")
KEY_REG_SLOT = re.compile(r"\{(\w+)\}")


def _handle_shortcut_reg(argv: Argv, groups: tuple[str, ...], gdict: dict[str, str], wrapper: _ShortcutRegWrapper):
    data = []
    for unit in argv.raw_data:
        if not isinstance(unit, str):
            data.append(unit)
            continue
        unit = escape(unit)
        if mat := INDEX_REG_SLOT.fullmatch(unit):
            index = int(mat[1])
            if index >= len(groups):
                continue
            slot = groups[index]
            data.append(wrapper(index, slot, argv.context))
            continue
        if mat := KEY_REG_SLOT.fullmatch(unit):
            key = mat[1]
            if key not in gdict:
                continue
            slot = gdict[key]
            data.append(wrapper(key, slot, argv.context))
            continue
        if mat := INDEX_REG_SLOT.findall(unit):
            for index in map(int, mat):
                if index >= len(groups):
                    unit = unit.replace(f"{{{index}}}", "")
                    continue
                slot = groups[index]
                unit = unit.replace(f"{{{index}}}", str(wrapper(index, slot, argv.context) or ""))
        if mat := KEY_REG_SLOT.findall(unit):
            for key in mat:
                if key not in gdict:
                    unit = unit.replace(f"{{{key}}}", "")
                    continue
                slot = gdict[key]
                unit = unit.replace(f"{{{key}}}", str(wrapper(key, slot, argv.context) or ""))
        if unit:
            data.append(unescape(unit))
    return data


def shortcut(
    argv: Argv[TDC], data: list[Any], short: Arparma[Any] | InnerShortcutArgs, reg: re.Match | None = None
) -> Arparma[TDC] | None:
    """处理被触发的快捷命令

    Args:
        argv (Argv[TDC]): 命令行参数
        data (list[Any]): 剩余参数
        short (Arparma | InnerShortcutArgs): 快捷命令
        reg (Match | None): 可能的正则匹配结果

    Returns:
        Arparma[TDC] | None: Arparma 解析结果

    Raises:
        ParamsUnmatched: 若不允许快捷命令后随其他参数，则抛出此异常
    """

    if isinstance(short, Arparma):
        return short

    argv.build(short.command)  # type: ignore
    if not short.fuzzy and data:
        raise ParamsUnmatched(lang.require("analyser", "param_unmatched").format(target=data[0]))
    argv.addon(short.args, merge_str=False)
    data = _handle_shortcut_data(argv, data)
    if not data and argv.raw_data and any(
            isinstance(i, str) and bool(re.search(r"\{%(\d+)|\*(.*?)\}", i)) for i in argv.raw_data
    ):
        raise ArgumentMissing(lang.require("analyser", "param_missing"))
    argv.addon(data, merge_str=False)
    if reg:
        data = _handle_shortcut_reg(argv, reg.groups(), reg.groupdict(), short.wrapper)
        argv.raw_data.clear()
        argv.ndata = 0
        argv.current_index = 0
        argv.addon(data)
    return
