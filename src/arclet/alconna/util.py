"""杂物堆"""
import random
import functools
import warnings
import logging

from collections import OrderedDict
from datetime import datetime, timedelta
from inspect import stack
from typing import Callable, TypeVar, Optional, Dict, Any, List, Iterator, Generic, Hashable, Tuple, Set, Union

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


def split_once(text: str, separates: Union[str, Set[str]]):  # 相当于另类的pop, 不会改变本来的字符串
    """单次分隔字符串"""
    out_text = ""
    quotation = ""
    is_split = True
    separates = separates if isinstance(separates, set) else {separates}
    for index, char in enumerate(text):
        if char in {"'", '"'}:  # 遇到引号括起来的部分跳过分隔
            if not quotation:
                is_split = False
                quotation = char
            elif char == quotation:
                is_split = True
                quotation = ""
        if char in separates and is_split:
            break
        out_text += char
    result = "".join(out_text)
    return result, text[len(result) + 1:]


def split(text: str, separates: Optional[Set[str]] = None):
    """尊重引号与转义的字符串切分

    Args:
        text (str): 要切割的字符串
        separates (Set(str)): 切割符. 默认为 " ".

    Returns:
        List[str]: 切割后的字符串, 可能含有空格
    """
    separates = separates or {" "}
    result = []
    quote = ""
    quoted = False
    cache = ""
    for index, char in enumerate(text):
        if char in {"'", '"'}:
            if not quoted:
                quote = char
                quoted = True
                if index and text[index - 1] == "\\":
                    cache += char
            elif char == quote:
                quote = ""
                quoted = False
                if index and text[index - 1] == "\\":
                    cache += char
        elif char in {"\n", "\r"}:
            result.append(cache)
            cache = ""
        elif not quoted and char in separates and cache:
            result.append(cache)
            cache = ""
        elif char != "\\" and (char not in separates or quoted):
            cache += char
    if cache:
        result.append(cache)
    return result


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
    cache: OrderedDict
    __size: int
    record: Dict[_K, Tuple[datetime, timedelta]]

    __slots__ = ("max_size", "cache", "record", "__size")

    def __init__(self, max_size: int = -1) -> None:
        self.max_size = max_size
        self.cache = OrderedDict()
        self.record = {}
        self.__size = 0

    def __getitem__(self, key: _K) -> _V:
        if key in self.cache:
            self.cache.move_to_end(key)
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
            return
        self.cache[key] = value
        self.__size += 1
        if 0 < self.max_size < self.__size:
            _k = self.cache.popitem(last=False)[0]
            self.record.pop(_k)
            self.__size -= 1
        self.record[key] = (datetime.now(), timedelta(seconds=expiration))

    def delete(self, key: _K) -> None:
        if key in self.cache:
            self.cache.pop(key)
            self.record.pop(key)
        else:
            raise KeyError(key)

    def size(self) -> int:
        return self.__size

    def has(self, key: _K) -> bool:
        return key in self.cache

    def clear(self) -> None:
        self.cache.clear()
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
        key = random.choice(list(self.cache.keys()))
        expire = self.record[key][1]
        if expire.total_seconds() > 0 and now > self.record[key][0] + expire:
            self.delete(key)

    def update_all(self) -> None:
        now = datetime.now()
        for key in self.cache.keys():
            expire = self.record[key][1]
            if expire.total_seconds() > 0 and now > self.record[key][0] + expire:
                self.delete(key)

    @property
    def recent(self) -> Optional[_V]:
        if self.cache:
            try:
                return self.cache[list(self.cache.keys())[-1]]
            except KeyError:
                return None
        return None
