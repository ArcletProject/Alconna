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
from typing import TypeVar, Type, Callable, Optional, Protocol, Any, Pattern, Union, Sequence, \
    List, Dict, get_args, Literal, Tuple, get_origin
from types import LambdaType
from pathlib import Path
from .exceptions import ParamsUnmatched
from .lang_config import lang_config

DataUnit = TypeVar("DataUnit")


class DataCollection(Protocol[DataUnit]):
    """数据集合协议"""

    def __str__(self) -> str:
        ...

    def __iter__(self) -> DataUnit:
        ...


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
        converter: 匹配成功后的转换方法
        origin_type: 转换后的类型
        alias: 别名, 用于类型检查与参数打印
    """

    re_pattern: Pattern
    pattern: str
    token: PatternToken
    converter: Callable[[str], Any]
    origin_type: Type
    alias: Optional[str]

    __slots__ = "re_pattern", "pattern", "token", "origin_type", "converter", "alias"

    def __init__(
            self,
            regex_pattern: str,
            token: PatternToken = PatternToken.REGEX_MATCH,
            origin_type: Type = str,
            converter: Optional[Callable] = None,
            alias: Optional[str] = None
    ):
        """
        初始化参数匹配表达式

        Args:
            regex_pattern: 用以正则解析的表达式
            token: 匹配类型
            origin_type: 转换后的参数类型
            converter: 匹配成功后的转换方法
            alias: 别名, 用于类型检查与参数打印
        """
        self.pattern = regex_pattern
        self.re_pattern = re.compile("^" + regex_pattern + "$")
        self.token = token
        self.origin_type = origin_type
        self.converter = converter or (lambda x: eval(x))
        self.alias = alias

    def __repr__(self):
        return self.pattern

    @lru_cache(maxsize=None)
    def match(self, text: Union[str, Any]):
        """
        对传入的参数进行匹配, 如果匹配成功, 则返回转换后的值, 否则返回None
        """
        if not isinstance(text, str):
            if isinstance(text, self.origin_type):
                return text
            return
        if self.token == PatternToken.DIRECT:
            return text
        r = self.re_pattern.findall(text)
        return r[0] if r else None

    def __getstate__(self):
        re_pattern = self.pattern
        token = self.token.value
        type_mark = self.origin_type.__name__
        alias = self.alias
        return {"type": "ArgPattern", "pattern": re_pattern, "token": token, "origin_type": type_mark, "alias": alias}

    def to_dict(self):
        return self.__getstate__()

    @classmethod
    def from_dict(cls, data: dict):
        re_pattern = data["pattern"]
        token = PatternToken(data["token"])
        type_mark = eval(data["origin_type"])
        alias = data["alias"]
        return cls(re_pattern, token, type_mark, alias=alias)

    def __setstate__(self, state):
        self.__init__(state["pattern"], PatternToken(state["token"]), eval(state["origin_type"]), alias=state["alias"])


class Force:
    """
    强制类型, 用于在特定的参数类型下跳过类型检查
    """
    origin: Any

    def __init__(self, origin):
        if isinstance(origin, (Force, ArgPattern)):
            raise TypeError(lang_config.types_force_type_error.format(target=origin))
        self.origin = origin

    def __repr__(self):
        return f"Force:{self.origin.__repr__()}"


AnyStr = ArgPattern(r"(.+?)", PatternToken.DIRECT, str)
Email = ArgPattern(r"([\w\.+-]+)@([\w\.-]+)\.([\w\.-]+)", origin_type=tuple, alias="email")
AnyIP = ArgPattern(r"(\d+)\.(\d+)\.(\d+)\.(\d+):?(\d*)", origin_type=tuple, alias="ip")
AnyUrl = ArgPattern(r"[\w]+://[^/\s?#]+[^\s?#]+(?:\?[^\s#]*)?(?:#[^\s]*)?", origin_type=str, alias="url")


T_Target = TypeVar("T_Target")
T_Origin = TypeVar("T_Origin")


class TypePattern:
    """
    对参数类型值的包装, 但不涉及正则匹配

    Attributes:
        target_types: 可接受的多个参数类型
        origin_type: 转换后的参数类型
        converter: 转换方法
        alias: 别名, 用于类型检查与参数打印
        previous: 该类型表达式需要的前置表达, 其解析结果会作为参数传入该表达式
    """

    def __init__(
            self,
            target_types: List[Type[T_Target]],
            origin_type: Type[T_Origin],
            converter: Optional[Callable] = None,
            alias: Optional[str] = None,
            previous: Optional["TypePattern"] = None
    ):
        """
        构造类型表达式

        Args:
            target_types: 可接受的多个参数类型
            origin_type: 转换后的参数类型
            converter: 转换方法
            alias: 别名, 用于类型检查与参数打印
            previous: 该类型表达式需要的前置表达, 其解析结果会作为参数传入该表达式
        """
        self.origin_type = origin_type
        self.target_types = target_types
        self.action: Callable[[Union[T_Target, ...]], T_Origin] = converter or (lambda x: origin_type(x))
        self.alias = alias
        self.previous = previous

    @lru_cache(maxsize=None)
    def find(self, obj: Any) -> T_Origin:
        """
        对传入的参数进行匹配, 如果匹配成功, 则返回转换后的值, 否则返回None
        """
        if not isinstance(obj, tuple(self.target_types)):
            if isinstance(obj, self.origin_type):
                return obj
            if self.previous:
                obj = self.previous.find(obj)
            else:
                return
        return self.action(obj)

    def __repr__(self):
        if self.previous:
            return (
                    self.previous.__repr__() + ", " +
                    '|'.join([x.__name__ for x in self.target_types]) +
                    " -> " + self.origin_type.__name__
            )
        return f"{'|'.join([x.__name__ for x in self.target_types])} -> {self.origin_type.__name__}"


class MultiArg(ArgPattern):
    """对可变参数的匹配"""
    flag: str
    arg_value: Any
    array_length: Optional[int]

    def __init__(
            self,
            arg_value: Union[ArgPattern, Type],
            flag: Literal['args', 'kwargs'] = 'args',
            array_length: Optional[int] = None,
    ):
        if isinstance(arg_value, ArgPattern):
            alias_content = arg_value.alias or arg_value.origin_type.__name__
        else:
            alias_content = arg_value.__name__
        self.flag = flag
        self.array_length = array_length
        if flag == 'args':
            super().__init__(
                r"(.+?)", PatternToken.DIRECT, tuple,
                alias=(f"*{alias_content}" if array_length is None else f"{alias_content}*{array_length}")
            )
        elif flag == 'kwargs':
            super().__init__(r"(.+?)", PatternToken.DIRECT, dict, alias=f"**{alias_content}")
        self.arg_value = arg_value

    def __repr__(self):
        if self.flag == 'args':
            if self.array_length:
                return f"{self.arg_value}[{self.array_length}]"
            return f"({self.arg_value}, ...)"
        elif self.flag == 'kwargs':
            return f"{{KEY={self.arg_value}, ...}}"


class AntiArg(ArgPattern):
    """反向参数的匹配"""
    arg_value: Any

    def __init__(self, arg_value: Union[ArgPattern, Type]):
        self.arg_value = arg_value
        if isinstance(arg_value, ArgPattern):
            alias_content = arg_value.alias or arg_value.origin_type.__name__
        else:
            alias_content = arg_value.__name__
        super().__init__(r"(.+?)", PatternToken.REGEX_MATCH, str, alias=f"!{alias_content}")

    def __repr__(self):
        return f"!{self.arg_value}"


class UnionArg(ArgPattern):
    """多类型参数的匹配"""
    anti: bool
    arg_value: Sequence[Union[Type, ArgPattern, TypePattern, object, str]]
    for_type_check: List[Type]
    for_match: List[Union[ArgPattern, TypePattern]]
    for_equal: List[Union[str, object]]

    __validator__: Callable = lambda x: x if isinstance(x, Sequence) else [x]

    def __init__(self, arg_value: Sequence[Union[Type, TypePattern, ArgPattern, object, str]], anti: bool = False):
        self.anti = anti
        self.arg_value = arg_value

        self.for_type_check = []
        self.for_match = []
        self.for_equal = []

        for arg in arg_value:
            if isinstance(arg, (ArgPattern, TypePattern)):
                self.for_match.append(arg)
            elif isinstance(arg, type):
                self.for_type_check.append(arg)
            else:
                self.for_equal.append(arg)
        alias_content = ", ".join(
            [a.alias or a.origin_type.__name__ for a in self.for_match] +
            [repr(a) for a in self.for_equal] +
            [a.__name__ for a in self.for_type_check]
        )
        super().__init__(
            r"(.+?)",
            PatternToken.DIRECT,
            str,
            alias=f"{'!' if self.anti else ''}Union[{alias_content}]"
        )

    def match(self, text: Union[str, Any]):
        if self.anti:
            equal, match, type_check = False, False, False
            if text in self.for_equal:
                equal = True
            for pat in self.for_match:
                if pat.match(text):
                    match = True
                    break
            for t in self.for_type_check:
                if isinstance(text, t):
                    type_check = True
                    break

            if any([equal, match, type_check]):
                return None
            return text
        not_equal, not_match, not_check = True, True, True
        if text in self.for_equal:
            not_equal = False

        if not_equal:
            for pat in self.for_match:
                if arg_find := pat.match(text):
                    not_match = False
                    text = arg_find
                    if isinstance(pat, TypePattern):
                        break
                    if pat.token == PatternToken.REGEX_TRANSFORM and isinstance(text, str):
                        text = pat.converter(text)
                    if text == pat.pattern:
                        text = Ellipsis  # type: ignore
                    break
        if not_match:
            for t in self.for_type_check:
                if isinstance(text, t):
                    not_check = False
                    break
        if all([not_equal, not_match, not_check]):
            return None
        return text

    def __repr__(self):
        return ("!" if self.anti else "") + ("(" + "|".join(
            [repr(a) for a in self.for_match] +
            [repr(a) for a in self.for_equal] +
            [a.__name__ for a in self.for_type_check]
        ) + ")")

    def __class_getitem__(cls, item):
        return cls(cls.__validator__(item))


class SequenceArg(ArgPattern):
    """匹配列表或者元组或者集合"""
    form: str
    arg_value: ArgPattern

    def __init__(self, arg_value: Union[ArgPattern, _AnyParam], form: str = "list"):
        self.arg_value = arg_value if isinstance(arg_value, ArgPattern) else AnyStr
        self.form = form
        alias_content = self.arg_value.alias or self.arg_value.origin_type.__name__

        if form == "list":
            super().__init__(r"\[(.+?)\]", PatternToken.REGEX_MATCH, list, alias=f"List[{alias_content}]")
        elif form == "tuple":
            super().__init__(r"\((.+?)\)", PatternToken.REGEX_MATCH, tuple, alias=f"Tuple[{alias_content}]")
        elif form == "set":
            super().__init__(r"\{(.+?)\}", PatternToken.REGEX_MATCH, set, alias=f"Set[{alias_content}]")
        else:
            raise ValueError(lang_config.types_sequence_form_error.format(target=form))

    def match(self, text: Union[str, Any]):
        _res = super().match(text)
        if not _res:
            return
        sequence = re.split(r"\s*,\s*", _res) if isinstance(_res, str) else _res
        result = []
        for s in sequence:
            if not (arg_find := self.arg_value.match(s)):
                raise ParamsUnmatched(f"{s} is not matched with {self.arg_value}")
            if self.arg_value.token == PatternToken.REGEX_TRANSFORM and isinstance(arg_find, str):
                arg_find = self.arg_value.converter(arg_find)
            result.append(arg_find)
        if self.form == "list":
            return result
        elif self.form == "tuple":
            return tuple(result)
        elif self.form == "set":
            return set(result)

    def __repr__(self):
        return f"{self.form}[{self.arg_value}]"


class MappingArg(ArgPattern):
    """匹配字典或者映射表"""
    form: str
    arg_key: ArgPattern
    arg_value: ArgPattern

    def __init__(self, arg_key: ArgPattern, arg_value: Union[ArgPattern, _AnyParam]):
        self.arg_key = arg_key
        self.arg_value = arg_value if isinstance(arg_value, ArgPattern) else AnyStr

        alias_content = f"{self.arg_key.alias or self.arg_key.origin_type.__name__}, " \
                        f"{self.arg_value.alias or self.arg_value.origin_type.__name__}"
        super().__init__(r"\{(.+?)\}", PatternToken.REGEX_MATCH, dict, alias=f"Dict[{alias_content}]")

    def match(self, text: Union[str, Any]):
        _res: Union[str, Dict, None] = super().match(text)
        if not _res:
            return
        result = {}

        def _generator_items(res):
            if isinstance(res, str):
                _mapping = re.split(r"\s*,\s*", res)
                for m in _mapping:
                    _k, _v = re.split(r"\s*[:=]\s*", m)
                    yield _k, _v
            else:
                for _k, _v in res.items():
                    yield _k, _v

        for k, v in _generator_items(_res):
            if not (real_key := self.arg_key.match(k)):
                raise ParamsUnmatched(f"{k} is not matched with {self.arg_key}")
            if self.arg_key.token == PatternToken.REGEX_TRANSFORM and isinstance(real_key, str):
                real_key = self.arg_key.converter(real_key)
            if not (arg_find := self.arg_value.match(v)):
                raise ParamsUnmatched(f"{v} is not matched with {self.arg_value}")
            if self.arg_value.token == PatternToken.REGEX_TRANSFORM and isinstance(arg_find, str):
                arg_find = self.arg_value.converter(arg_find)
            result[real_key] = arg_find

        return result

    def __repr__(self):
        return f"dict[{self.arg_key.origin_type.__name__}, {self.arg_value}]"


pattern_map = {
    Any: AnyParam,
    Ellipsis: AnyParam,
    object: AnyParam,
    "email": Email,
    "ip": AnyIP,
    "url": AnyUrl,
    "...": AnyParam,
    "": Empty
}


def set_converter(
        alc_pattern: Union[ArgPattern, TypePattern],
        origin_type: Optional[type] = None,
        alias: Optional[str] = None,
        cover: bool = False
):
    """
    增加Alconna内使用的类型转换器

    Args:
        alc_pattern: 设置的表达式
        origin_type: 目标检查类型
        alias: 目标类型的别名
        cover: 是否覆盖已有的转换器
    """
    if cover:
        if alias:
            pattern_map[alias] = alc_pattern
        if alc_pattern.alias:
            pattern_map[alc_pattern.alias] = alc_pattern
        if origin_type:
            pattern_map[origin_type] = alc_pattern
        else:
            pattern_map[alc_pattern.origin_type] = alc_pattern
    else:
        if origin_type:
            if al_pat := pattern_map.get(origin_type):
                if isinstance(al_pat, UnionArg):
                    pattern_map[origin_type] = UnionArg([*al_pat.arg_value, alc_pattern])
                else:
                    pattern_map[origin_type] = UnionArg([al_pat, alc_pattern])
            else:
                pattern_map[origin_type] = alc_pattern
        else:
            if al_pat := pattern_map.get(alc_pattern.origin_type):
                if isinstance(al_pat, UnionArg):
                    pattern_map[alc_pattern.origin_type] = UnionArg([*al_pat.arg_value, alc_pattern])
                else:
                    pattern_map[alc_pattern.origin_type] = UnionArg([al_pat, alc_pattern])
            else:
                pattern_map[alc_pattern.origin_type] = alc_pattern
        if alias:
            if al_pat := pattern_map.get(alias):
                if isinstance(al_pat, UnionArg):
                    pattern_map[alias] = UnionArg([*al_pat.arg_value, alc_pattern])
                else:
                    pattern_map[alias] = UnionArg([al_pat, alc_pattern])
            else:
                pattern_map[alias] = alc_pattern
        if alc_pattern.alias:
            if al_pat := pattern_map.get(alc_pattern.alias):
                if isinstance(al_pat, UnionArg):
                    pattern_map[alc_pattern.alias] = UnionArg([*al_pat.arg_value, alc_pattern])
                else:
                    pattern_map[alc_pattern.alias] = UnionArg([al_pat, alc_pattern])
            else:
                pattern_map[alc_pattern.alias] = alc_pattern


StrPath = TypePattern([str], Path, lambda v: Path(v), "path")
AnyPathFile = TypePattern(
    [Path], bytes, lambda x: x.read_bytes() if x.exists() and x.is_file() else None, 'file', previous=StrPath
)
set_converter(AnyPathFile)

AnyDigit = ArgPattern(r"(\-?\d+)", PatternToken.REGEX_TRANSFORM, int, lambda x: int(x))
AnyFloat = ArgPattern(r"(\-?\d+\.?\d*)", PatternToken.REGEX_TRANSFORM, float, lambda x: float(x))
Bool = ArgPattern(
    r"(True|False|true|false)", PatternToken.REGEX_TRANSFORM, bool, lambda x: bool(
        x.replace("false", "False").replace("true", "True")
    )
)
AnyList = ArgPattern(r"(\[.+?\])", PatternToken.REGEX_TRANSFORM, list)
AnyTuple = ArgPattern(r"(\(.+?\))", PatternToken.REGEX_TRANSFORM, tuple)
AnySet = ArgPattern(r"(\{.+?\})", PatternToken.REGEX_TRANSFORM, set)
AnyDict = ArgPattern(r"(\{.+?\})", PatternToken.REGEX_TRANSFORM, dict)

set_converter(AnyStr, alias="str")
set_converter(AnyDigit, alias="int")
set_converter(AnyFloat, alias="float")
set_converter(Bool, alias="bool")
set_converter(AnyList, alias="list")
set_converter(AnyTuple, alias="tuple")
set_converter(AnySet, alias="set")
set_converter(AnyDict, alias="dict")


def pattern(name: str, re_pattern: str):
    """便捷地设置转换器"""

    def __wrapper(func):
        return ArgPattern(re_pattern, token=PatternToken.REGEX_TRANSFORM, converter=func, alias=name)

    return __wrapper


def argument_type_validator(item: Any, extra: str = "allow"):
    """对 Args 里参数类型的检查， 将一般数据类型转为 Args 使用的类型"""
    if isinstance(item, Force):
        return item.origin if not isinstance(item.origin, str) else ArgPattern(item.origin)
    if isinstance(item, (ArgPattern, _AnyParam, TypePattern)):
        return item
    try:
        if pat := pattern_map.get(item, None):
            return pat
    except TypeError:
        pass
    if not inspect.isclass(item) and item.__class__.__name__ in "_GenericAlias":
        origin = get_origin(item)
        if origin in (Union, Literal):
            _args = list(set([argument_type_validator(t, extra) for t in get_args(item)]))
            if len(_args) < 1:
                return item
            if len(_args) < 2:
                _args = _args[0]
            return _args
        if origin in (dict, ABCMapping, ABCMutableMapping):
            arg_key = argument_type_validator(get_args(item)[0], 'ignore')
            arg_value = argument_type_validator(get_args(item)[1], 'ignore')
            if isinstance(arg_value, list):
                if len(arg_value) == 2 and Empty in arg_value:
                    arg_value.remove(Empty)
                    arg_value = arg_value[0]
                else:
                    arg_value = UnionArg(arg_value)
            return MappingArg(arg_key=arg_key, arg_value=arg_value)
        args = argument_type_validator(get_args(item)[0], 'ignore')
        if isinstance(args, list):
            if len(args) == 2 and Empty in args:
                args.remove(Empty)
                args = args[0]
            else:
                args = UnionArg(args)
        if origin in (ABCMutableSequence, list):
            return SequenceArg(args)
        if origin in (ABCSequence, ABCIterable, tuple):
            return SequenceArg(args, form="tuple")
        if origin in (ABCMutableSet, ABCSet, set):
            return SequenceArg(args, form="set")

    if item is None or type(None) == item:
        return Empty
    if isinstance(item, str):
        return ArgPattern(item)
    if extra == "ignore":
        return AnyParam
    elif extra == "reject":
        raise TypeError(lang_config.types_validate_reject.format(target=item))
    return item


UnionArg.__validator__ = lambda x: [
    argument_type_validator(t, "ignore") for t in (x if isinstance(x, Sequence) else [x])
]


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
        将传入的对象类型转换为接收序列号参数解析后实例化的对象

        Args:
            origin: 原始对象
            limit: 指定该对象初始化时需要的参数
            head: 是否需要匹配一个头部
            flag: 匹配类型
            suppliers: 对象属性的匹配方法
        """
        self.origin = origin
        self._require_map: Dict[str, Callable] = {}
        self._supplement_map: Dict[str, Callable] = {}
        self._transform_map: Dict[str, Callable] = {}
        self._params: Dict[str, Any] = {}
        _re_pattern = ""
        _re_patterns = []
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
                            inspect.ismethod(suppliers[name])
                    ):
                        self._supplement_map[name] = suppliers[name]
                    elif len(_s_sig.parameters) == 1 or (
                            len(_s_sig.parameters) == 2 and
                            inspect.ismethod(suppliers[name])
                    ):
                        self._require_map[name] = suppliers[name]
                        if flag == "http":
                            _re_patterns.append(f"{name}=(?P<{name}>.+?)")  # &
                        elif flag == "part":
                            _re_patterns.append(f"(?P<{name}>.+?)")  # ;
                        elif flag == "json":
                            _re_patterns.append(f"\\'{name}\\':\\'(?P<{name}>.+?)\\'")  # ,
                    else:
                        raise TypeError(lang_config.types_supplier_params_error.format(target=name, origin=origin.__name__))
                else:
                    if isinstance(suppliers[name], LambdaType):
                        if len(_s_sig.parameters) == 0:
                            self._supplement_map[name] = suppliers[name]
                        elif len(_s_sig.parameters) == 1:
                            self._require_map[name] = suppliers[name]
                            if flag == "http":
                                _re_patterns.append(f"{name}=(?P<{name}>.+?)")  # &
                            elif flag == "part":
                                _re_patterns.append(f"(?P<{name}>.+?)")  # ;
                            elif flag == "json":
                                _re_patterns.append(f"\\'{name}\\':\\'(?P<{name}>.+?)\\'")  # ,
                        else:
                            raise TypeError(lang_config.types_supplier_params_error.format(target=name, origin=origin.__name__))
                    else:
                        raise TypeError(lang_config.types_supplier_return_error.format(
                            target=name, origin=origin.__name__, source=param.annotation
                        ))
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
                        raise TypeError(lang_config.types_supplier_missing.format(target=name, origin=origin.__name__))

                if isinstance(pat, ObjectPattern):
                    raise TypeError(lang_config.types_type_error.format(target=pat))
                self._require_map[name] = pat.match
                if pat.token == PatternToken.REGEX_TRANSFORM:
                    self._transform_map[name] = pat.converter
                if flag == "http":
                    _re_patterns.append(f"{name}=(?P<{name}>{pat.pattern.strip('()')})")  # &
                elif flag == "part":
                    _re_patterns.append(f"(?P<{name}>{pat.pattern.strip('()')})")  # ;
                elif flag == "json":
                    _re_patterns.append(f"\\'{name}\\':\\'(?P<{name}>{pat.pattern.strip('()')})\\'")  # ,
        if _re_patterns:
            if flag == "http":
                _re_pattern = (rf"{head}\?" if head else "") + "&".join(_re_patterns)
            elif flag == "part":
                _re_pattern = (f"{head};" if head else "") + ";".join(_re_patterns)
            elif flag == "json":
                _re_pattern = (f"{head}:" if head else "") + "{" + ",".join(_re_patterns) + "}"
        else:
            _re_pattern = f"{head}" if head else f"{self.origin.__name__}"

        super().__init__(
            _re_pattern,
            token=PatternToken.REGEX_MATCH, origin_type=self.origin, alias=head or self.origin.__name__,
        )
        set_converter(self)

    def match(self, text: str):
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
