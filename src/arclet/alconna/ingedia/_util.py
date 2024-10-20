from typing import Generic, TypeVar, Optional

T = TypeVar("T")


class ChainMap(Generic[T]):
    def __init__(self, base: Optional[dict[str, T]] = None, *maps: dict[str, T]):
        self.base: dict[str, T] = base or {}
        self.stack: "list[dict[str, T]]" = list(maps)

    def enter(self, map: dict):
        self.stack.insert(0, map)

    def __contains__(self, item: str):
        return item in self.base or any(item in m for m in self.stack)

    def __getitem__(self, item: str) -> T:
        for m in self.stack:
            if item in m:
                return m[item]
        if item in self.base:
            return self.base[item]
        raise KeyError(item)

    def parents(self):
        if not self.stack:
            return ChainMap()
        return ChainMap(self.base, *self.stack[1:])

    def leave(self):
        self.stack.pop(0)


def levenshtein(source: str, target: str) -> float:
    """`编辑距离算法`_, 计算源字符串与目标字符串的相似度, 取值范围[0, 1], 值越大越相似

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


ESCAPE = {"\\": "\x00", "[": "\x01", "]": "\x02", "{": "\x03", "}": "\x04", "|": "\x05"}
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
