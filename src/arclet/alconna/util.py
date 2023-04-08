"""杂物堆"""
from __future__ import annotations

import sys
from functools import lru_cache


def _safe_dcs_args(**kwargs):
    if sys.version_info < (3, 10):
        kwargs.pop('slots')
    return kwargs


QUOTATION = {"'", '"', "’", "“"}


@lru_cache(4096)
def split_once(text: str, separates: str | tuple[str, ...], crlf: bool = True):
    """单次分隔字符串"""
    index, out_text, quotation, escape = 0, "", "", False
    separates = tuple(separates)
    text = text.lstrip()
    for char in text:
        if char == "\\":
            escape = True
            out_text += char
        elif char in QUOTATION:  # 遇到引号括起来的部分跳过分隔
            if not quotation:
                quotation = char
                if escape:
                    out_text = out_text[:-1] + char
            elif char == quotation:
                quotation = ""
                if escape:
                    out_text = out_text[:-1] + char
        elif (char in separates or (crlf and char in {"\n", "\r"})) and not quotation:
            break
        else:
            out_text += char
            escape = False
        index += 1
    return out_text, text[index + 1:]


@lru_cache(4096)
def split(text: str, separates: tuple[str, ...] | None = None, crlf: bool = True):
    """尊重引号与转义的字符串切分

    Args:
        text (str): 要切割的字符串
        separates (Set(str)): 切割符. 默认为 " ".
        crlf (bool): 是否去除 \n 与 \r，默认为 True

    Returns:
        List[str]: 切割后的字符串, 可能含有空格
    """
    separates = separates or (" ",)
    result, quotation, escape = "", "", False
    for char in text:
        if char == "\\":
            escape = True
            result += char
        elif char in QUOTATION:
            if not quotation:
                quotation = char
                if escape:
                    result = result[:-1] + char
            elif char == quotation:
                quotation = ""
                if escape:
                    result = result[:-1] + char
        elif (not quotation and char in separates) or (crlf and char in {"\n", "\r"}):
            if result and result[-1] != "\0":
                result += "\0"
        else:
            result += char
            escape = False
    return result.split('\0') if result else []


def levenshtein_norm(source: str, target: str) -> float:
    """编辑距离算法, 计算源字符串与目标字符串的相似度, 取值范围[0, 1], 值越大越相似"""
    l_s, l_t = len(source), len(target)
    s_range, t_range = range(l_s + 1), range(l_t + 1)
    matrix = [[(i if j == 0 else j) for j in t_range] for i in s_range]

    for i in s_range[1:]:
        for j in t_range[1:]:
            sub_distance = matrix[i - 1][j - 1] + (0 if source[i - 1] == target[j - 1] else 1)
            matrix[i][j] = min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1, sub_distance)

    return 1 - float(matrix[l_s][l_t]) / max(l_s, l_t)
