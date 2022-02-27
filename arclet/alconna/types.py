"""Alconna 参数相关"""
import re
import inspect
from functools import lru_cache
from enum import Enum
from typing import TypeVar, Type, Callable, Optional, Protocol, Any, runtime_checkable, Pattern, Union, Iterable

_KT = TypeVar('_KT')
_VT_co = TypeVar("_VT_co", covariant=True)


@runtime_checkable
class Gettable(Protocol):
    """表示拥有 get 方法的对象"""

    def get(self, key: _KT) -> _VT_co:
        ...


NonTextElement = TypeVar("NonTextElement")
MessageChain = TypeVar("MessageChain")


class PatternToken(str, Enum):
    """
    参数表达式类型
    """
    REGEX_TRANSFORM = "regex_transform"
    REGEX_MATCH = "regex_match"
    DIRECT = "direct"


class _AnyParam:
    """单个参数的泛匹配"""

    def __repr__(self):
        return "AnyParam"

    def __getstate__(self):
        return {"type": self.__repr__()}


class _AnyAllParam(_AnyParam):
    """复数参数的泛匹配"""

    def __repr__(self):
        return "AllParam"


AnyParam = _AnyParam()
AllParam = _AnyAllParam()
Empty = inspect.Signature.empty


class ArgPattern:
    """
    对参数类型值的包装

    Attributes:
        re_pattern: 实际的正则表达式
        pattern: 用以正则解析的表达式
        token: 匹配类型
        transform_action: 匹配成功后的转换方法
        type_mark: 针对action的类型检查
    """

    re_pattern: Pattern
    pattern: str
    token: PatternToken
    transform_action: Callable[[str], Any]
    type_mark: Type

    __slots__ = "re_pattern", "pattern", "token", "type_mark", "transform_action"

    def __init__(
            self,
            regex_pattern: str,
            token: PatternToken = PatternToken.REGEX_MATCH,
            type_mark: Type = str,
            transform_action: Optional[Callable] = lambda x: eval(x)
    ):
        self.pattern = regex_pattern
        self.re_pattern = re.compile("^" + regex_pattern + "$")
        self.token = token
        self.type_mark = type_mark
        if self.token == PatternToken.REGEX_TRANSFORM:
            self.transform_action = transform_action

    def __repr__(self):
        return self.pattern

    @lru_cache(maxsize=512)
    def find(self, text: str):
        """
        匹配文本, 返回匹配结果
        """
        if not isinstance(text, str):
            return
        if self.token == PatternToken.DIRECT:
            return text
        r = self.re_pattern.findall(text)
        return r[0] if r else None

    def __getstate__(self):
        pattern = self.pattern
        token = self.token.value
        type_mark = self.type_mark.__name__
        return {"type": "ArgPattern", "pattern": pattern, "token": token, "type_mark": type_mark}

    def to_dict(self):
        return self.__getstate__()

    @classmethod
    def from_dict(cls, data: dict):
        pattern = data["pattern"]
        token = PatternToken(data["token"])
        type_mark = eval(data["type_mark"])
        return cls(pattern, token, type_mark)

    def __setstate__(self, state):
        self.__init__(state["pattern"], PatternToken(state["token"]), eval(state["type_mark"]))


AnyStr = ArgPattern(r"(.+?)", token=PatternToken.DIRECT, type_mark=str)
AnyDigit = ArgPattern(r"(\-?\d+)", token=PatternToken.REGEX_TRANSFORM, type_mark=int)
AnyFloat = ArgPattern(r"(\-?\d+\.?\d*)", token=PatternToken.REGEX_TRANSFORM, type_mark=float)
Bool = ArgPattern(
    r"(True|False|true|false)", token=PatternToken.REGEX_TRANSFORM, type_mark=bool,
    transform_action=lambda x: eval(x, {"true": True, "false": False})
)
Email = ArgPattern(r"([\w\.+-]+)@([\w\.-]+)\.([\w\.-]+)", type_mark=tuple)
AnyIP = ArgPattern(r"(\d+)\.(\d+)\.(\d+)\.(\d+):?(\d*)", type_mark=tuple)
AnyUrl = ArgPattern(r"[\w]+://[^/\s?#]+[^\s?#]+(?:\?[^\s#]*)?(?:#[^\s]*)?", type_mark=str)


class MultiArg(ArgPattern):
    """可变参数的匹配"""
    arg_value: Union[ArgPattern, Type[NonTextElement]]

    def __init__(self, arg_value: Union[ArgPattern, Type[NonTextElement]]):
        super().__init__(r"(.+?)", token=PatternToken.DIRECT, type_mark=list)
        self.arg_value = arg_value

    def __repr__(self):
        return f"[{self.arg_value}, ...]"


class AntiArg(ArgPattern):
    """反向参数的匹配"""
    arg_value: Union[ArgPattern, Type[NonTextElement], Iterable]

    def __init__(self, arg_value: Union[ArgPattern, Type[NonTextElement], Iterable]):
        super().__init__(r"(.+?)", token=PatternToken.REGEX_MATCH, type_mark=str)
        self.arg_value = arg_value

    def __repr__(self):
        return f"!{self.arg_value}"
