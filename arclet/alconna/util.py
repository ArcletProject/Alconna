"""杂物堆"""


from typing import Any, Union, Type
from arclet.alconna.types import ArgPattern, _AnyParam, NonTextElement, Empty, AnyStr, AnyDigit, AnyFloat, Bool, \
    AnyUrl, AnyIP, AnyParam


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
