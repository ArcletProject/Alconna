"""Alconna 参数相关"""

import inspect
from typing import TypeVar, Type

NonTextElement = TypeVar("NonTextElement")
MessageChain = TypeVar("MessageChain")


class _AnyParam:
    """单个参数的泛匹配"""
    def __repr__(self):
        return "AnyParam"


class _AnyAllParam(_AnyParam):
    """复数参数的泛匹配"""
    def __repr__(self):
        return "AllParam"


AnyParam = _AnyParam()
AllParam = _AnyAllParam()
Empty = inspect.Signature.empty


class ArgPattern:
    """对参数类型值的包装"""
    pattern: str
    transform: bool
    type_mark: Type

    __slots__ = "pattern", "transform", "type_mark"

    def __init__(self, regex_pattern: str, need_transform: bool = False, type_mark: Type = str):
        self.pattern = regex_pattern
        self.transform = need_transform
        self.type_mark = type_mark

    def __repr__(self):
        return self.pattern


AnyStr = ArgPattern(r"(.+)", type_mark=str)
AnyDigit = ArgPattern(r"(\-?\d+)", need_transform=True, type_mark=int)
AnyFloat = ArgPattern(r"(\-?\d+\.?\d*)", need_transform=True, type_mark=float)
Bool = ArgPattern(r"(True|False|true|false)", need_transform=True, type_mark=bool)
AnyIP = ArgPattern(r"(\d+)\.(\d+)\.(\d+)\.(\d+):?(\d*)", type_mark=tuple)
AnyUrl = ArgPattern(r"(http[s]?://.+)", type_mark=str)
