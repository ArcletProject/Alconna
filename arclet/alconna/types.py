"""Alconna 参数相关"""

import inspect
from typing import TypeVar, Type, Callable, Optional, Any

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
    pattern: str  # 用以正则解析的表达式
    transform: bool  # 是否需要类型转换
    transform_action: Callable[[str], Any]  # 类型转换的函数
    type_mark: Type  # 针对action的类型检查

    __slots__ = "pattern", "transform", "type_mark", "transform_action"

    def __init__(
            self,
            regex_pattern: str,
            need_transform: bool = False,
            type_mark: Type = str,
            transform_action: Optional[Callable] = lambda x: eval(x)
    ):
        self.pattern = regex_pattern
        self.transform = need_transform
        self.type_mark = type_mark
        if self.transform:
            self.transform_action = transform_action

    def __repr__(self):
        return self.pattern


AnyStr = ArgPattern(r"(.+?)", type_mark=str)
AnyDigit = ArgPattern(r"(\-?\d+)", need_transform=True, type_mark=int)
AnyFloat = ArgPattern(r"(\-?\d+\.?\d*)", need_transform=True, type_mark=float)
Bool = ArgPattern(
    r"(True|False|true|false)", need_transform=True, type_mark=bool,
    transform_action=lambda x: eval(x, {"true": True, "false": False})
)
Email = ArgPattern(r"([\w\.+-]+)@([\w\.-]+)\.([\w\.-]+)", type_mark=tuple)
AnyIP = ArgPattern(r"(\d+)\.(\d+)\.(\d+)\.(\d+):?(\d*)", type_mark=tuple)
AnyUrl = ArgPattern(r"[\w]+://[^/\s?#]+[^\s?#]+(?:\?[^\s#]*)?(?:#[^\s]*)?", type_mark=str)
