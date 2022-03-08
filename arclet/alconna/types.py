"""Alconna 参数相关"""
import re
import inspect
from functools import lru_cache
from collections.abc import (
    Iterable as ABCIterable,
    Sequence as ABCSequence,
    Set as ABCSet,
    MutableSet as ABCMutableSet,
    MutableSequence as ABCMutableSequence,
    MutableMapping as ABCMutableMapping,
    Mapping as ABCMapping,
)
from enum import Enum
from typing import TypeVar, Type, Callable, Optional, Protocol, Any, runtime_checkable, Pattern, Union, Sequence, \
    List, Dict, get_args, Literal, Tuple, get_origin
from types import LambdaType
from .exceptions import ParamsUnmatched

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
        origin_type: 针对action的类型检查
        alias: 别名, 用于类型检查与参数打印
    """

    re_pattern: Pattern
    pattern: str
    token: PatternToken
    transform_action: Optional[Callable[[str], Any]]
    origin_type: Type
    alias: str

    __slots__ = "re_pattern", "pattern", "token", "origin_type", "transform_action", "alias"

    def __init__(
            self,
            regex_pattern: str,
            token: PatternToken = PatternToken.REGEX_MATCH,
            origin_type: Type = str,
            transform_action: Optional[Callable] = lambda x: eval(x),
            alias: Optional[str] = None
    ):
        self.pattern = regex_pattern
        self.re_pattern = re.compile("^" + regex_pattern + "$")
        self.token = token
        self.origin_type = origin_type
        if self.token == PatternToken.REGEX_TRANSFORM:
            self.transform_action = transform_action
        else:
            self.transform_action = None
        self.alias = alias

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
        type_mark = self.origin_type.__name__
        alias = self.alias
        return {"type": "ArgPattern", "pattern": pattern, "token": token, "origin_type": type_mark, "alias": alias}

    def to_dict(self):
        return self.__getstate__()

    @classmethod
    def from_dict(cls, data: dict):
        pattern = data["pattern"]
        token = PatternToken(data["token"])
        type_mark = eval(data["origin_type"])
        alias = data["alias"]
        return cls(pattern, token, type_mark, alias=alias)

    def __setstate__(self, state):
        self.__init__(state["pattern"], PatternToken(state["token"]), eval(state["origin_type"]), alias=state["alias"])


class Force:
    origin: Any

    def __init__(self, origin):
        if isinstance(origin, (Force, ArgPattern)):
            raise TypeError("Force can not be used to force a Force or ArgPattern")
        self.origin = origin


AnyStr = ArgPattern(r"(.+?)", PatternToken.DIRECT, str)
AnyDigit = ArgPattern(r"(\-?\d+)", PatternToken.REGEX_TRANSFORM, int, lambda x: int(x))
AnyFloat = ArgPattern(r"(\-?\d+\.?\d*)", PatternToken.REGEX_TRANSFORM, float, lambda x: float(x))
Bool = ArgPattern(
    r"(True|False|true|false)", PatternToken.REGEX_TRANSFORM, bool, lambda x: bool(
        x.replace("false", "False").replace("true", "True")
    )
)
Email = ArgPattern(r"([\w\.+-]+)@([\w\.-]+)\.([\w\.-]+)", origin_type=tuple, alias="email")
AnyIP = ArgPattern(r"(\d+)\.(\d+)\.(\d+)\.(\d+):?(\d*)", origin_type=tuple, alias="ip")
AnyUrl = ArgPattern(r"[\w]+://[^/\s?#]+[^\s?#]+(?:\?[^\s#]*)?(?:#[^\s]*)?", origin_type=str, alias="url")
AnyList = ArgPattern(r"(\[.+?\])", token=PatternToken.REGEX_TRANSFORM, origin_type=list)
AnyTuple = ArgPattern(r"(\(.+?\))", token=PatternToken.REGEX_TRANSFORM, origin_type=tuple)
AnySet = ArgPattern(r"(\{.+?\})", token=PatternToken.REGEX_TRANSFORM, origin_type=set)
AnyDict = ArgPattern(r"(\{.+?\})", token=PatternToken.REGEX_TRANSFORM, origin_type=dict)


class MultiArg(ArgPattern):
    """可变参数的匹配"""
    flag: str
    arg_value: Union[ArgPattern, Type[NonTextElement]]

    def __init__(self, arg_value: Union[ArgPattern, Type[NonTextElement]], flag: Literal['args', 'kwargs'] = 'args'):
        if isinstance(arg_value, ArgPattern):
            alias_content = arg_value.alias or arg_value.origin_type.__name__
        else:
            alias_content = arg_value.__name__
        self.flag = flag
        if flag == 'args':
            super().__init__(r"(.+?)", token=PatternToken.DIRECT, origin_type=tuple, alias=f"*{alias_content}")
        else:
            super().__init__(r"(.+?)", token=PatternToken.DIRECT, origin_type=dict, alias=f"**{alias_content}")
        self.arg_value = arg_value

    def __repr__(self):
        if self.flag == 'args':
            return f"({self.arg_value}, ...)"
        return f"{{KEY:{self.arg_value}, ...}}"


class AntiArg(ArgPattern):
    """反向参数的匹配"""
    arg_value: Union[ArgPattern, Type[NonTextElement]]

    def __init__(self, arg_value: Union[ArgPattern, Type[NonTextElement]]):
        self.arg_value = arg_value
        if isinstance(arg_value, ArgPattern):
            alias_content = arg_value.alias or arg_value.origin_type.__name__
        else:
            alias_content = arg_value.__name__
        super().__init__(r"(.+?)", token=PatternToken.REGEX_MATCH, origin_type=str, alias=f"!{alias_content}")

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
        alias_content = ", ".join(
            [a.alias or a.origin_type.__name__ for a in self.for_match] +
            [repr(a) for a in self.for_equal] +
            [a.__name__ for a in self.for_type_check]
        )
        super().__init__(r"(.+?)", token=PatternToken.DIRECT, origin_type=str, alias=f"Union[{alias_content}]")

    def __repr__(self):
        return ("!" if self.anti else "") + (
                "(" + "|".join(
                    [repr(a) for a in self.for_match] +
                    [repr(a) for a in self.for_equal] +
                    [a.__name__ for a in self.for_type_check]
                ) + ")"
        )


class SequenceArg(ArgPattern):
    """匹配列表或者元组或者集合"""
    form: str
    arg_value: ArgPattern

    def __init__(self, arg_value: Union[ArgPattern, _AnyParam], form: str = "list"):
        self.arg_value = arg_value if isinstance(arg_value, ArgPattern) else AnyStr
        self.form = form
        alias_content = self.arg_value.alias or self.arg_value.origin_type.__name__

        def _act(text: str):
            sequence = re.split(r"\s*,\s*", text)
            result = []
            for s in sequence:
                if isinstance(self.arg_value, UnionArg):
                    for pat in self.arg_value.for_match:
                        if arg_find := pat.find(s):
                            s = arg_find
                            if pat.token == PatternToken.REGEX_TRANSFORM:
                                s = pat.transform_action(s)
                            break
                    else:
                        raise ParamsUnmatched(f"{s} is not matched in {self.arg_value}")
                    result.append(s)
                else:
                    if self.arg_value.find(s):
                        if self.arg_value.token == PatternToken.REGEX_TRANSFORM:
                            s = self.arg_value.transform_action(s)
                        result.append(s)
                    else:
                        raise ParamsUnmatched(f"{s} is not matched with {self.arg_value}")
            if self.form == "list":
                return result
            elif self.form == "tuple":
                return tuple(result)
            elif self.form == "set":
                return set(result)

        if form == "list":
            super().__init__(r"\[(.+?)\]", PatternToken.REGEX_TRANSFORM, list, _act, f"List[{alias_content}]")
        elif form == "tuple":
            super().__init__(r"\((.+?)\)", PatternToken.REGEX_TRANSFORM, tuple, _act, f"Tuple[{alias_content}]")
        elif form == "set":
            super().__init__(r"\{(.+?)\}", PatternToken.REGEX_TRANSFORM, set, _act, f"Set[{alias_content}]")
        else:
            raise ValueError(f"invalid form: {form}")

    def __repr__(self):
        return f"{self.form}[{self.arg_value}]"


class MappingArg(ArgPattern):
    """匹配字典或者映射表"""
    form: str
    arg_key: ArgPattern
    arg_value: ArgPattern

    def __init__(self, arg_key: ArgPattern, arg_value: Union[ArgPattern, _AnyParam]):
        self.arg_key = arg_key
        if isinstance(self.arg_key, UnionArg):
            raise TypeError("not support union arg in mapping key")
        self.arg_value = arg_value if isinstance(arg_value, ArgPattern) else AnyStr

        def _act(text: str):
            mapping = re.split(r"\s*,\s*", text)
            result = {}
            for m in mapping:
                k, v = re.split(r"\s*[:=]\s*", m)
                if self.arg_key.find(k):
                    if self.arg_key.token == PatternToken.DIRECT:
                        try:
                            k = eval(k)
                        except NameError:
                            pass
                    if self.arg_key.token == PatternToken.REGEX_TRANSFORM:
                        k = self.arg_key.transform_action(k)
                    real_key = k
                else:
                    raise ParamsUnmatched(f"{k} is not matched with {self.arg_key}")
                if isinstance(self.arg_value, UnionArg):
                    for pat in self.arg_value.for_match:
                        if arg_find := pat.find(v):
                            v = arg_find
                            if pat.token == PatternToken.REGEX_TRANSFORM:
                                v = pat.transform_action(v)
                            break
                    else:
                        raise ParamsUnmatched(f"{v} is not matched in {self.arg_value}")
                    result[real_key] = v
                else:
                    if self.arg_value.find(v):
                        if self.arg_value.token == PatternToken.REGEX_TRANSFORM:
                            v = self.arg_value.transform_action(v)
                        result[real_key] = v
                    else:
                        raise ParamsUnmatched(f"{v} is not matched with {self.arg_value}")
            return result

        alias_content = f"{self.arg_key.alias or self.arg_key.origin_type.__name__}, " \
                        f"{self.arg_value.alias or self.arg_value.origin_type.__name__}"
        super().__init__(r"\{(.+?)\}", PatternToken.REGEX_TRANSFORM, dict, _act, f"Dict[{alias_content}]")

    def __repr__(self):
        return f"dict[{self.arg_key.origin_type.__name__}, {self.arg_value}]"


pattern_map = {
    str: AnyStr,
    int: AnyDigit,
    float: AnyFloat,
    bool: Bool,
    Ellipsis: Empty,
    object: AnyParam,
    list: AnyList,
    tuple: AnyTuple,
    set: AnySet,
    dict: AnyDict,
    Any: AnyParam,
    "url": AnyUrl,
    "ip": AnyIP,
    "email": Email,
    "": Empty,
    "..": AnyParam,
    "...": AllParam
}


def add_check(pattern: ArgPattern):
    return pattern_map.setdefault(pattern.alias or pattern.origin_type, pattern)


def argtype_validator(item: Any, extra: str = "allow") -> Union[ArgPattern, _AnyParam, Type[NonTextElement], Empty]:
    """对 Args 里参数类型的检查， 将一般数据类型转为 Args 使用的类型"""
    if isinstance(item, Force):
        return item.origin if not isinstance(item.origin, str) else ArgPattern(item.origin)
    try:
        if pattern_map.get(item):
            return pattern_map.get(item)
    except TypeError:
        pass
    if item.__class__.__name__ in "_GenericAlias":
        origin = get_origin(item)
        if origin in (Union, Literal):
            args = list(set([argtype_validator(t, extra) for t in get_args(item)]))
            if len(args) < 1:
                return item
            if len(args) < 2:
                args = args[0]
            return args
        elif origin in (dict, ABCMapping, ABCMutableMapping):
            arg_key = argtype_validator(get_args(item)[0], 'ignore')
            arg_value = argtype_validator(get_args(item)[1], 'ignore')
            if isinstance(arg_value, list):
                if len(arg_value) == 2 and Empty in arg_value:
                    arg_value.remove(Empty)
                    arg_value = arg_value[0]
                else:
                    arg_value = UnionArg(arg_value)
            return MappingArg(arg_key=arg_key, arg_value=arg_value)
        elif origin in (ABCMutableSequence, ABCSequence, list, ABCIterable, tuple, ABCMutableSet, ABCSet, set):
            args = argtype_validator(get_args(item)[0], 'ignore')
            if isinstance(args, list):
                if len(args) == 2 and Empty in args:
                    args.remove(Empty)
                    args = args[0]
                else:
                    args = UnionArg(args)
            if origin in (ABCMutableSequence, ABCSequence, list):
                return SequenceArg(args)
            elif origin in (ABCMutableSet, ABCSet, set):
                return SequenceArg(args, form="set")
            elif origin in (ABCIterable, tuple):
                return SequenceArg(args, form="tuple")

    if item is None or type(None) == item:
        return Empty
    if isinstance(item, str):
        return ArgPattern(item)
    if isinstance(item, (ArgPattern, _AnyParam)):
        return item
    if extra == "ignore":
        return AnyParam
    elif extra == "reject":
        raise TypeError(f"{item} is not allowed in Args")
    return item


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
                    pat = pattern_map.get(anno, None)
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
            token=PatternToken.REGEX_MATCH, origin_type=self.origin
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
