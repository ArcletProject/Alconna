"""杂物堆"""


from typing import Any, Union, Type

from .exceptions import UnexpectedElement, NullTextMessage
from .types import ArgPattern, _AnyParam, NonTextElement, Empty, AnyStr, AnyDigit, AnyFloat, Bool, \
    AnyUrl, AnyIP, AnyParam


chain_texts = ["Plain", "Text"]
elements_blacklist = ["Source", "File", "Quote"]
elements_whitelist = []


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
    out_text = ""
    quotation_stack = []
    is_split = True
    for char in text:
        if char in "'\"":  # 遇到引号括起来的部分跳过分隔
            if not quotation_stack:
                is_split = False
                quotation_stack.append(char)
            else:
                is_split = True
                quotation_stack.pop(-1)
        if separate == char and is_split:
            break
        out_text += char
    return out_text, text.replace(out_text, "", 1).replace(separate, "", 1)


def split(text: str, separate: str = " ", max_split: int = -1):
    """类似于shlex中的split, 但保留引号"""
    text_list = []
    quotation_stack = []
    is_split = True
    while all([text, max_split]):
        out_text = ""
        for char in text:
            if char in "'\"":  # 遇到引号括起来的部分跳过分隔
                if not quotation_stack:
                    is_split = False
                    quotation_stack.append(char)
                else:
                    is_split = True
                    quotation_stack.pop(-1)
            if separate == char and is_split:
                break
            out_text += char
        if out_text:
            text_list.append(out_text)
        text = text.replace(out_text, "", 1).replace(separate, "", 1)
        max_split -= 1
    if text:
        text_list.append(text)
    return text_list


def arg_check(item: Any) -> Union[ArgPattern, _AnyParam, Type[NonTextElement], Empty]:
    """对 Args 里参数类型的检查， 将一般数据类型转为 Args 使用的类型"""
    _check_list = {
        str: AnyStr,
        int: AnyDigit,
        float: AnyFloat,
        bool: Bool,
        Ellipsis: Empty,
        "url": AnyUrl,
        "ip": AnyIP,
        "": AnyParam,
        "...": Empty
    }
    if _check_list.get(item):
        return _check_list.get(item)
    if item is None:
        return Empty
    if isinstance(item, str):
        return ArgPattern(item)
    return item


def chain_filter(
        self,
        message,
):
    """消息链过滤方法, 优先度 texts > white_elements > black_elements"""
    i, _tc = 0, 0
    raw_data = {}
    for ele in message:
        try:
            if ele.__class__.__name__ in chain_texts:
                raw_data[i] = split(ele.text.lstrip(' '), self.separator)
                _tc += 1
            elif elements_whitelist and ele.__class__.__name__ not in elements_whitelist:
                raise UnexpectedElement(f"{ele.__class__.__name__}({ele})")
            elif ele.__class__.__name__ in elements_blacklist:
                raise UnexpectedElement(f"{ele.__class__.__name__}({ele})")
            else:
                raw_data[i] = ele
            i += 1
        except UnexpectedElement:
            if self.exception_in_time:
                raise
            continue
    if _tc == 0:
        if self.exception_in_time:
            raise NullTextMessage
        return
    return raw_data
