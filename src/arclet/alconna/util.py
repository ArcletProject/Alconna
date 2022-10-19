"""杂物堆"""
import inspect
from functools import lru_cache
from typing import TypeVar, Optional, Any, Tuple, Union

R = TypeVar('R')


@lru_cache(4096)
def is_async(o: Any):
    return inspect.iscoroutinefunction(o) or inspect.isawaitable(o)


@lru_cache(4096)
def split_once(text: str, separates: Union[str, Tuple[str, ...]], crlf: bool = True):
    """单次分隔字符串"""
    out_text = ""
    quotation = ""
    separates = tuple(separates)
    for index, char in enumerate(text):
        if char in {"'", '"'}:  # 遇到引号括起来的部分跳过分隔
            if not quotation:
                quotation = char
                if index and text[index - 1] == "\\":
                    out_text += char
            elif char == quotation:
                quotation = ""
                if index and text[index - 1] == "\\":
                    out_text += char
        if (char in separates and not quotation) or (crlf and char in {"\n", "\r"}):
            break
        out_text += char
    return out_text, text[len(out_text) + 1:]


@lru_cache(4096)
def split(text: str, separates: Optional[Tuple[str, ...]] = None, crlf: bool = True):
    """尊重引号与转义的字符串切分

    Args:
        text (str): 要切割的字符串
        separates (Set(str)): 切割符. 默认为 " ".
        crlf (bool): 是否去除 \n 与 \r，默认为 True

    Returns:
        List[str]: 切割后的字符串, 可能含有空格
    """
    separates = separates or (" ",)
    result = ""
    quotation = ""
    for index, char in enumerate(text):
        if char in {"'", '"'}:
            if not quotation:
                quotation = char
                if index and text[index - 1] == "\\":
                    result += char
            elif char == quotation:
                quotation = ""
                if index and text[index - 1] == "\\":
                    result += char
        elif (not quotation and char in separates) or (crlf and char in {"\n", "\r"}):
            if result and result[-1] != "\0":
                result += "\0"
        elif char != "\\":
            result += char
    return result.split('\0') if result else []