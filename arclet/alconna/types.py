"""Alconna 参数相关"""
import re
import inspect
from functools import lru_cache
from enum import Enum
from typing import TypeVar, Type, Callable, Optional, Protocol, Any, runtime_checkable, Pattern, Union, Sequence, \
    List, Dict, get_args, Literal, Tuple
from types import LambdaType

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
    transform_action: Optional[Callable[[str], Any]]
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
        else:
            self.transform_action = None

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

check_list = {
    str: AnyStr,
    int: AnyDigit,
    float: AnyFloat,
    bool: Bool,
    Ellipsis: Empty,
    "url": AnyUrl,
    "ip": AnyIP,
    "email": Email,
    "": Empty,
    "..": AnyParam,
    "...": AllParam
}


def add_check(pattern: ArgPattern):
    return check_list.setdefault(pattern.type_mark, pattern)


class ObjectPattern(ArgPattern):

    def __init__(
            self,
            origin: Type,
            limit: Tuple[str, ...] = (),
            head: str = "",
            flag: Literal["http", "part", "json"] = "part",
            **suppliers: Callable
    ):
        """
        讲传入的对象转换为参数化的对象

        Args:
            origin: 原始对象
            headless: 是否只匹配对象的属性
            flag: 匹配类型
            suppliers: 对象属性的匹配方法
        """
        self.origin = origin
        self._require_map: Dict[str, Callable] = {}
        self._supplement_map: Dict[str, Callable] = {}
        self._transform_map: Dict[str, Callable] = {}
        self._params: Dict[str, Any] = {}
        _re_pattern = ""
        sig = inspect.signature(origin.__init__)
        for param in sig.parameters.values():
            name = param.name
            if name in ("self", "args", "kwargs"):
                continue
            if limit and name not in limit:
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            self._params[name] = None
            if name in suppliers:
                _s_sig = inspect.signature(suppliers[name])
                if _s_sig.return_annotation in get_args(param.annotation):
                    if len(_s_sig.parameters) == 0 or (
                            len(_s_sig.parameters) == 1 and
                            list(_s_sig.parameters.values())[0].name in {"self", "cls"}
                    ):
                        self._supplement_map[name] = suppliers[name]
                    elif len(_s_sig.parameters) == 1 or (
                            len(_s_sig.parameters) == 2 and
                            list(_s_sig.parameters.values())[0].name in {"self", "cls"}
                    ):
                        self._require_map[name] = suppliers[name]
                        if flag == "http":
                            _re_pattern += f"{name}=(?P<{name}>.+?)&"
                        elif flag == "part":
                            _re_pattern += f"(?P<{name}>.+?);"
                        elif flag == "json":
                            _re_pattern += f"\\'{name}\\':\\'(?P<{name}>.+?)\\',"
                    else:
                        raise TypeError(
                            f"{name} in {origin.__name__} init function should have 0 or 1 parameter"
                        )
                else:
                    if isinstance(suppliers[name], LambdaType):
                        if len(_s_sig.parameters) == 0:
                            self._supplement_map[name] = suppliers[name]
                        elif len(_s_sig.parameters) == 1:
                            self._require_map[name] = suppliers[name]
                            if flag == "http":
                                _re_pattern += f"{name}=(?P<{name}>.+?)&"
                            elif flag == "part":
                                _re_pattern += f"(?P<{name}>.+?);"
                            elif flag == "json":
                                _re_pattern += f"\\'{name}\\':\\'(?P<{name}>.+?)\\',"
                        else:
                            raise TypeError(
                                f"{name} in {origin.__name__} init function should have 0 or 1 parameter"
                            )
                    else:
                        raise TypeError(f"{name}'s supplier of {origin.__name__} must return {param.annotation}")
            elif param.default is not Empty and param.default is not None and param.default != Ellipsis:
                self._params[name] = param.default
            else:
                pat = param.annotation
                if not (args := get_args(param.annotation)):
                    args = (pat,)
                for anno in args:
                    pat = check_list.get(anno, None)
                    if pat is not None:
                        break
                else:
                    if param.annotation is Empty:
                        pat = AnyStr
                    elif inspect.isclass(param.annotation) and issubclass(param.annotation, str):
                        pat = AnyStr
                    elif inspect.isclass(param.annotation) and issubclass(param.annotation, int):
                        pat = AnyDigit
                    elif pat is None:
                        raise TypeError(f"{name} in {origin.__name__} init function should give a supplier")

                if isinstance(pat, ObjectPattern):
                    raise NotImplementedError(f"{pat} is not supported")
                self._require_map[name] = pat.find
                self._transform_map[name] = pat.transform_action
                if flag == "http":
                    _re_pattern += f"{name}=(?P<{name}>{pat.pattern.strip('()')})&"
                elif flag == "part":
                    _re_pattern += f"(?P<{name}>{pat.pattern.strip('()')});"
                elif flag == "json":
                    _re_pattern += f"\\'{name}\\':\\'(?P<{name}>{pat.pattern.strip('()')})\\',"
        if _re_pattern != "":
            if head:
                if flag == "http":
                    _re_pattern = rf"(?P<self>{head})\?{_re_pattern}"[:-1]
                elif flag == "part":
                    _re_pattern = rf"(?P<self>{head});{_re_pattern}"[:-1]
                elif flag == "json":
                    _re_pattern = f"{head}:{{{_re_pattern}"[:-1] + "}"
            elif flag == "json":
                _re_pattern = rf"{{{_re_pattern}"[:-1] + "}"
            else:
                _re_pattern = f"{_re_pattern}"[:-1]
        else:
            _re_pattern = rf"(?P<self>{head})" if head else rf"(?P<self>{self.origin.__name__})"
        super().__init__(
            _re_pattern,
            token=PatternToken.REGEX_MATCH, type_mark=self.origin
        )
        add_check(self)

    def find(self, text: str):
        if matched := self.re_pattern.fullmatch(text):
            args = matched.groupdict()
            for k in self._require_map:
                if k in args:
                    self._params[k] = self._require_map[k](args[k])
                    if self._transform_map.get(k, None):
                        self._params[k] = self._transform_map[k](self._params[k])
            for k in self._supplement_map:
                self._params[k] = self._supplement_map[k]()
            return self.origin(**self._params)


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
    arg_value: Union[ArgPattern, Type[NonTextElement]]

    def __init__(self, arg_value: Union[ArgPattern, Type[NonTextElement]]):
        super().__init__(r"(.+?)", token=PatternToken.REGEX_MATCH, type_mark=str)
        self.arg_value = arg_value

    def __repr__(self):
        return f"!{self.arg_value}"


class UnionArg(ArgPattern):
    """多项参数的匹配"""
    anti: bool
    arg_value: Sequence[Union[Type, ArgPattern, NonTextElement, str]]
    for_type_check: List[Type]
    for_match: List[ArgPattern]
    for_equal: List[Union[str, NonTextElement]]

    def __init__(self, arg_value: Sequence[Union[Type, ArgPattern, NonTextElement, str]], anti: bool = False):
        super().__init__(r"(.+?)", token=PatternToken.DIRECT, type_mark=list)
        self.anti = anti
        self.arg_value = arg_value

        self.for_type_check = []
        self.for_match = []
        self.for_equal = []

        for arg in arg_value:
            if isinstance(arg, ArgPattern):
                self.for_match.append(arg)
            elif isinstance(arg, str):
                self.for_equal.append(arg)
            elif isinstance(arg, type):
                self.for_type_check.append(arg)
            else:
                self.for_equal.append(arg)

    def __repr__(self):
        return "(" + "|".join([repr(a) for a in self.arg_value]) + ")"
