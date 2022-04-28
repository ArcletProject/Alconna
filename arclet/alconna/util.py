"""杂物堆"""
import random
import functools
import warnings
import logging
from datetime import datetime, timedelta
from inspect import stack
from typing import Callable, TypeVar, Optional, Dict, Any, List, Iterator, Generic, Hashable, Tuple

R = TypeVar('R')


class Singleton(type):
    """单例模式"""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def get_module_name() -> Optional[str]:
    """获取当前模块名"""
    for frame in stack():
        if name := frame.frame.f_locals.get("__name__"):
            return name


def get_module_filename() -> Optional[str]:
    """获取当前模块的文件名"""
    for frame in stack():
        if frame.frame.f_locals.get("__name__"):
            return frame.filename.split("/")[-1].split(".")[0]


def get_module_filepath() -> Optional[str]:
    """获取当前模块的路径"""
    for frame in stack():
        if frame.frame.f_locals.get("__name__"):
            return ".".join(frame.filename.split("/")[1:]).replace('.py', '')


def split_once(text: str, separate: str):  # 相当于另类的pop, 不会改变本来的字符串
    """单次分隔字符串"""
    out_text = []
    quotation = ""
    is_split = True
    for index, char in enumerate(text):
        if char in ("'", '"'):  # 遇到引号括起来的部分跳过分隔
            if not quotation:
                is_split = False
                quotation = char
            elif char == quotation:
                is_split = True
                quotation = ""
        if separate == char and is_split:
            break
        out_text.append(char)
    result = "".join(out_text)
    return result, text.lstrip(result + separate)


def split(text: str, separate: str = " ", ):
    """尊重引号与转义的字符串切分

    Args:
        text (str): 要切割的字符串
        separate (str): 切割符. 默认为 " ".

    Returns:
        List[str]: 切割后的字符串, 可能含有空格
    """
    result = []
    quote = ""
    cache = []
    for index, char in enumerate(text):
        if char in ("'", '"'):
            if not quote:
                quote = char
                if index and text[index - 1] == "\\":
                    cache.append(char)
            elif char == quote and index and text[index - 1] != "\\":
                quote = ""
            else:
                cache.append(char)
                continue
        elif char in ("\n", "\r"):
            result.append("".join(cache))
            cache = []
        elif not quote and char == separate and cache:
            result.append("".join(cache))
            cache = []
        elif char != "\\" and (char != separate or quote):
            cache.append(char)
    if cache:
        result.append("".join(cache))
    return result


def is_chinese(string: str) -> bool:
    """中文Unicode码范围参考：https://www.iteye.com/topic/558050     """
    r = [
        # 标准CJK文字
        (0x3400, 0x4DB5), (0x4E00, 0x9FA5), (0x9FA6, 0x9FBB), (0xF900, 0xFA2D),
        (0xFA30, 0xFA6A), (0xFA70, 0xFAD9), (0x20000, 0x2A6D6), (0x2F800, 0x2FA1D),
        # 全角ASCII、全角中英文标点、半宽片假名、半宽平假名、半宽韩文字母
        (0xFF00, 0xFFEF),
        # CJK部首补充
        (0x2E80, 0x2EFF),
        # CJK标点符号
        (0x3000, 0x303F),
        # CJK笔划
        (0x31C0, 0x31EF)
    ]
    for c in string:
        if any(s <= ord(c) <= e for s, e in r):
            return True
    return False


def levenshtein_norm(source: str, target: str) -> float:
    """编辑距离算法, 计算源字符串与目标字符串的相似度, 取值范围[0, 1], 值越大越相似"""
    return 1 - float(levenshtein(source, target)) / max(len(source), len(target))


def levenshtein(source: str, target: str) -> int:
    """编辑距离算法的具体内容"""
    s_range = range(len(source) + 1)
    t_range = range(len(target) + 1)
    matrix = [[(i if j == 0 else j) for j in t_range] for i in s_range]

    for i in s_range[1:]:
        for j in t_range[1:]:
            del_distance = matrix[i - 1][j] + 1
            ins_distance = matrix[i][j - 1] + 1
            if is_chinese(source) or is_chinese(target):
                if abs(ord(source[i - 1]) - ord(target[j - 1])) <= 2:
                    sub_trans_cost = 0
                else:
                    sub_trans_cost = 1
            else:
                sub_trans_cost = 0 if source[i - 1] == target[j - 1] else 1
            sub_distance = matrix[i - 1][j - 1] + sub_trans_cost
            matrix[i][j] = min(del_distance, ins_distance, sub_distance)
    return matrix[len(source)][len(target)]


def deprecated(remove_ver: str) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """标注一个方法 / 函数已被弃用"""

    def out_wrapper(func: Callable[..., R]) -> Callable[..., R]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> R:
            warnings.warn("{} will be removed in {}!".format(func.__qualname__, remove_ver), DeprecationWarning, 2)
            logging.warning(f"{func.__qualname__} will be removed in {remove_ver}!")
            return func(*args, **kwargs)

        return wrapper

    return out_wrapper


_K = TypeVar("_K", bound=Hashable)
_V = TypeVar("_V")


class LruCache(Generic[_K, _V]):
    max_size: int
    cache: Dict[_K, _V]
    order: List[_K]
    record: Dict[_K, Tuple[datetime, timedelta]]

    __slots__ = ("max_size", "cache", "order", "record")

    def __init__(self, max_size: int = -1) -> None:
        self.max_size = max_size
        self.cache = {}
        self.order = []
        self.record = {}

    def __getitem__(self, key: _K) -> _V:
        if key in self.cache:
            self.order.remove(key)
            self.order.append(key)
            return self.cache[key]
        raise KeyError(key)

    def get(self, key: _K, default: Any = None) -> _V:
        try:
            return self[key]
        except KeyError:
            return default

    def query_time(self, key: _K) -> datetime:
        if key in self.cache:
            return self.record[key][0]
        raise KeyError(key)

    def set(self, key: _K, value: Any, expiration: int = 0) -> None:
        if key in self.cache:
            self.order.remove(key)
        elif 0 < self.max_size <= len(self.cache):
            _k = self.order.pop(0)
            self.cache.pop(_k)
            self.record.pop(_k)
        self.order.append(key)
        self.cache[key] = value
        self.record[key] = (datetime.now(), timedelta(seconds=expiration))

    def delete(self, key: _K) -> None:
        if key in self.cache:
            self.order.remove(key)
            self.cache.pop(key)
            self.record.pop(key)
        else:
            raise KeyError(key)

    def size(self) -> int:
        return len(self.cache)

    def has(self, key: _K) -> bool:
        return key in self.cache

    def clear(self) -> None:
        self.cache.clear()
        self.order.clear()
        self.record.clear()

    def __len__(self) -> int:
        return len(self.cache)

    def __contains__(self, key: _K) -> bool:
        return key in self.cache

    def __iter__(self) -> Iterator[_K]:
        return iter(self.cache)

    def __repr__(self) -> str:
        return repr(self.cache)

    def update(self) -> None:
        now = datetime.now()
        key = random.choice(self.order)
        expire = self.record[key][1]
        if expire.total_seconds() > 0 and now > self.record[key][0] + expire:
            self.delete(key)

    def update_all(self) -> None:
        now = datetime.now()
        for key in self.order:
            expire = self.record[key][1]
            if expire.total_seconds() > 0 and now > self.record[key][0] + expire:
                self.delete(key)

    @property
    def recent(self) -> Optional[_V]:
        if self.order:
            try:
                return self.cache[self.order[-1]]
            except KeyError:
                return None
        return None
