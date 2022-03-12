"""杂物堆"""
import functools
import warnings
import logging
from inspect import stack
from typing import Callable, TypeVar, Optional

R = TypeVar('R')


class Singleton(type):
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
