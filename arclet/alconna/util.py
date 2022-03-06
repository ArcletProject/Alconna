"""杂物堆"""
import functools
import warnings
import logging
from inspect import stack
from typing import Union, Type, Callable, TypeVar
from .exceptions import UnexpectedElement, NullTextMessage
from .types import NonTextElement, Gettable

R = TypeVar('R')
raw_type = ["str", "dict", "Arpamar"]
chain_texts = ["Plain", "Text"]
elements_blacklist = ["Source", "File", "Quote"]
elements_whitelist = []


def get_module_name() -> str:
    """获取当前模块名"""
    for frame in stack():
        if name := frame.frame.f_locals.get("__name__"):
            return name


def get_module_filename() -> str:
    """获取当前模块的文件名"""
    for frame in stack():
        if frame.frame.f_locals.get("__name__"):
            return frame.filename.split("/")[-1].split(".")[0]


def get_module_filepath() -> str:
    """获取当前模块的路径"""
    for frame in stack():
        if frame.frame.f_locals.get("__name__"):
            return ".".join(frame.filename.split("/")[1:]).replace('.py', '')


def set_chain_texts(*text: Union[str, Type[NonTextElement]]):
    """设置文本类元素的集合"""
    global chain_texts
    chain_texts = [t if isinstance(t, str) else t.__name__ for t in text]


def set_black_elements(*element: Union[str, Type[NonTextElement]]):
    """设置消息元素的黑名单"""
    global elements_blacklist
    elements_blacklist = [ele if isinstance(ele, str) else ele.__name__ for ele in element]


def set_white_elements(*element: Union[str, Type[NonTextElement]]):
    """设置消息元素的白名单"""
    global elements_whitelist
    elements_whitelist = [ele if isinstance(ele, str) else ele.__name__ for ele in element]


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
        elif char in ("\n", "\r"):
            continue
        elif not quote and char == separate and cache:
            result.append("".join(cache))
            cache = []
        elif char != "\\" and (char != separate or quote):
            cache.append(char)
    if cache:
        result.append("".join(cache))
    return result


def chain_filter(
        message,
        separate: str = " ",
        exception_in_time: bool = False,
):
    """消息链过滤方法, 优先度 texts > white_elements > black_elements"""
    i, _tc = 0, 0
    raw_data = {}
    for ele in message:
        try:
            if ele.__class__.__name__ in chain_texts:
                raw_data[i] = split(ele.text.lstrip(' '), separate)
                _tc += 1
            elif ele.__class__.__name__ in elements_whitelist or ele.__class__.__name__ not in (
                    *elements_blacklist, *raw_type
            ):
                raw_data[i] = ele
            else:
                if isinstance(ele, Gettable):
                    if ele.get('type') in chain_texts:
                        raw_data[i] = split(ele.get('text').lstrip(' '), separate)
                        _tc += 1
                    elif ele.get('type') in elements_whitelist or ele.get('type') not in elements_blacklist:
                        raw_data[i] = ele
                elif ele.__class__.__name__ == "str":
                    raw_data[i] = split(ele.lstrip(' '), separate)
                    _tc += 1
                else:
                    raise UnexpectedElement(f"{ele.__class__.__name__}({ele})")
            i += 1
        except UnexpectedElement:
            if exception_in_time:
                raise
            continue
    if _tc == 0:
        if exception_in_time:
            raise NullTextMessage("传入了一个无法获取文本的消息链")
        return
    return raw_data


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
