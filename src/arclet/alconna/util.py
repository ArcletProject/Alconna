"""杂物堆"""
from __future__ import annotations

import sys
import dataclasses


def dataclass(*args, **kwargs):
    if sys.version_info < (3, 10):  # pragma: no cover
        kwargs.pop('slots')
    return dataclasses.dataclass(*args, **kwargs)


def levenshtein(source: str, target: str) -> float:
    """ `编辑距离算法`_, 计算源字符串与目标字符串的相似度, 取值范围[0, 1], 值越大越相似

    Args:
        source (str): 源字符串
        target (str): 目标字符串

    .. _编辑距离算法:
        https://en.wikipedia.org/wiki/Levenshtein_distance

    """
    l_s, l_t = len(source), len(target)
    s_range, t_range = range(l_s + 1), range(l_t + 1)
    matrix = [[(i if j == 0 else j) for j in t_range] for i in s_range]

    for i in s_range[1:]:
        for j in t_range[1:]:
            sub_distance = matrix[i - 1][j - 1] + (0 if source[i - 1] == target[j - 1] else 1)
            matrix[i][j] = min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1, sub_distance)

    return 1 - float(matrix[l_s][l_t]) / max(l_s, l_t)
