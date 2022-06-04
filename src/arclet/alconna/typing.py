"""Alconna 参数相关"""
import re
import inspect
from copy import copy
from collections.abc import (
    Iterable as ABCIterable,
    Sequence as ABCSequence,
    Set as ABCSet,
    MutableSet as ABCMutableSet,
    MutableSequence as ABCMutableSequence,
    MutableMapping as ABCMutableMapping,
    Mapping as ABCMapping,
)
from functools import lru_cache
from pathlib import Path
from enum import IntEnum
from typing import TypeVar, Type, Callable, Optional, Protocol, Any, Pattern, Union, Sequence, \
    List, Dict, get_args, Literal, Tuple, get_origin, Iterable, Generic

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

from .exceptions import ParamsUnmatched
from .lang import lang_config
from .util import generic_isinstance

DataUnit = TypeVar("DataUnit")
GenericAlias = type(List[int])
AnnotatedAlias = type(Annotated[int, lambda x: x > 0])


class DataCollection(Protocol[DataUnit]):
    """数据集合协议"""

    def __str__(self) -> str:
        ...

    def __iter__(self) -> DataUnit:
        ...

    def __len__(self) -> int:
        ...


class PatternModel(IntEnum):
    """
    参数表达式匹配模式
    """

    REGEX_CONVERT = 3
    """正则匹配并转换"""

    TYPE_CONVERT = 2
    """传入值直接转换"""

    REGEX_MATCH = 1
    """正则匹配"""

    KEEP = 0
    """保持传入值"""


class _All:
    """泛匹配"""

    __slots__ = ()

    def __repr__(self):
        return "AllParam"

    def __getstate__(self):
        return {"type": self.__repr__()}


AllParam = _All()
Empty = inspect.Signature.empty

TOrigin = TypeVar("TOrigin")


class BasePattern(Generic[TOrigin]):
    """
    对参数类型值的包装
    """

    regex_pattern: Pattern
    pattern: str
    model: PatternModel
    converter: Callable[[Union[str, Any]], TOrigin]
    validator: Callable[[TOrigin], bool]

    anti: bool
    origin_type: Type[TOrigin]
    accepts: Optional[List[Type]]
    alias: Optional[str]
    previous: Optional["BasePattern"]

    __slots__ = (
        "regex_pattern", "pattern", "model", "converter", "anti",
        "origin_type", "accepts", "alias", "previous", "validator"
    )

    def __init__(
            self,
            pattern: str = "(.+?)",
            model: PatternModel = PatternModel.REGEX_MATCH,
            origin_type: Type[TOrigin] = str,
            converter: Optional[Callable[[Union[str, Any]], TOrigin]] = None,
            alias: Optional[str] = None,
            previous: Optional["BasePattern"] = None,
            accepts: Optional[List[Type]] = None,
            validator: Optional[Callable[[TOrigin], bool]] = None,
            anti: bool = False
    ):
        """
        初始化参数匹配表达式
        """
        self.pattern = pattern
        self.regex_pattern = re.compile(f"^{pattern}$")
        self.model = model
        self.origin_type = origin_type
        self.alias = alias
        self.previous = previous
        self.accepts = accepts
        if converter:
            self.converter = converter
        elif model == PatternModel.TYPE_CONVERT:
            self.converter = lambda x: origin_type(x)
        else:
            self.converter = lambda x: eval(x)
        self.validator = validator or (lambda x: True)
        self.anti = anti

    def __repr__(self):
        if self.model == PatternModel.KEEP:
            return ('|'.join(x.__name__ for x in self.accepts)) if self.accepts else 'Any'
        if self.model == PatternModel.REGEX_MATCH:
            text = self.alias or self.pattern
        elif self.model == PatternModel.REGEX_CONVERT:
            text = self.alias or self.origin_type.__name__
        else:
            text = f"{(('|'.join(x.__name__ for x in self.accepts)) + ' -> ') if self.accepts else ''}" \
                   f"{self.alias or self.origin_type.__name__}"
        return f"{(f'{self.previous.__repr__()}, ' if self.previous else '')}{'!' if self.anti else ''}{text}"

    def __hash__(self):
        return hash(self.__repr__())

    def __eq__(self, other):
        return isinstance(other, BasePattern) and self.__repr__() == other.__repr__()

    @classmethod
    def of(cls, unit: Type[DataUnit]):
        """
        提供原来 TAValue 中的 Type[DataUnit] 类型的构造方法
        """
        return cls(origin_type=unit, accepts=[unit], model=PatternModel.KEEP, alias=unit.__name__)

    def reverse(self):
        self.anti = not self.anti
        return self

    def match(self, input_: Union[str, Any]) -> TOrigin:
        """
        对传入的参数进行匹配, 如果匹配成功, 则返回转换后的值, 否则返回None
        """
        if self.model > 1 and generic_isinstance(input_, self.origin_type):
            return input_
        if self.accepts and not isinstance(input_, tuple(self.accepts)):
            if not self.previous:
                raise ParamsUnmatched(lang_config.args_type_error.format(target=input_.__class__))
            input_ = self.previous.match(input_)
        if self.model == PatternModel.KEEP:
            return input_
        if self.model == PatternModel.TYPE_CONVERT:
            res = self.converter(input_)
            if not generic_isinstance(res, self.origin_type):
                raise ParamsUnmatched(lang_config.args_error.format(target=input_))
            return res
        if not isinstance(input_, str):
            raise ParamsUnmatched(lang_config.args_type_error.format(target=type(input_)))
        if r := self.regex_pattern.findall(input_):
            return self.converter(r[0]) if self.model == PatternModel.REGEX_CONVERT else r[0]
        raise ParamsUnmatched(lang_config.args_error.format(target=input_))

    def validate(self, input_: Union[str, Any], default: Optional[Any] = None) -> Tuple[Any, Literal["V", "E", "D"]]:
        if not self.anti:
            try:
                res = self.match(input_)
                if self.validator(res):
                    return res, "V"
                raise ParamsUnmatched(lang_config.args_error.format(target=input_))
            except Exception as e:
                if default is None:
                    return e, "E"
                return None if default is Empty else default, "D"
        try:
            res = self.match(input_)
        except ParamsUnmatched:
            return input_, "V"
        else:
            if not self.validator(res):
                return input_, "E"
            if default is None:
                return ParamsUnmatched(lang_config.args_error.format(target=input_)), "E"
            return None if default is Empty else default, "D"


AnyOne = BasePattern(r".+", PatternModel.KEEP, Any, alias="any")
_String = BasePattern(r"(.+?)", PatternModel.KEEP, str, alias="str", accepts=[str])
_Email = BasePattern(r"(?:[\w\.+-]+)@(?:[\w\.-]+)\.(?:[\w\.-]+)", alias="email")
_IP = BasePattern(
    r'(?:(?:[01]{0,1}\d{0,1}\d|2[0-4]\d|25[0-5])\.){3}(?:[01]{0,1}\d{0,1}\d|2[0-4]\d|25[0-5]):?(?:\d+)?', alias="ip"
)
_Url = BasePattern(r"[\w]+://[^/\s?#]+[^\s?#]+(?:\?[^\s#]*)?(?:#[^\s]*)?", alias="url")
_HexLike = BasePattern(r"((?:0x)?[0-9a-fA-F]+)", PatternModel.REGEX_CONVERT, int, lambda x: int(x, 16), "hex")
_HexColor = BasePattern(r"(#[0-9a-fA-F]{6})", PatternModel.REGEX_CONVERT, str, lambda x: x[1:], "color")


class MultiArg(BasePattern):
    """对可变参数的匹配"""
    flag: str
    array_length: Optional[int]

    def __init__(
            self,
            base: BasePattern,
            flag: Literal['args', 'kwargs'] = 'args',
            array_length: Optional[int] = None,
    ):
        alias_content = base.alias or base.origin_type.__name__
        self.flag = flag
        self.array_length = array_length
        if flag == 'args':
            _t = Tuple[base.origin_type, ...]
            alias = f"*{alias_content}[:{array_length}]" if array_length else f"*{alias_content}"
        else:
            _t = Dict[str, base.origin_type]
            alias = f"**{alias_content}[:{array_length}]" if array_length else f"**{alias_content}"
        super().__init__(
            base.pattern, base.model, _t,
            alias=alias, converter=base.converter, previous=base.previous, accepts=base.accepts
        )

    def __repr__(self):
        ctn = super().__repr__()
        if self.flag == 'args':
            return f"{ctn}[{self.array_length}]" if self.array_length else f"({ctn}, ...)"
        elif self.flag == 'kwargs':
            return f"{{KEY={ctn}, ...}}"


class UnionArg(BasePattern):
    """多类型参数的匹配"""
    optional: bool
    arg_value: Sequence[Union[BasePattern, object, str]]
    for_validate: List[BasePattern]
    for_equal: List[Union[str, object]]

    def __init__(self, base: Sequence[Union[BasePattern, object, str]], anti: bool = False):
        self.arg_value = base
        self.optional = False

        self.for_validate = []
        self.for_equal = []

        for arg in self.arg_value:
            if arg == Empty:
                self.optional = True
                self.for_equal.append(None)
            elif isinstance(arg, BasePattern):
                self.for_validate.append(arg)
            else:
                self.for_equal.append(arg)
        alias_content = "|".join(
            [repr(a) for a in self.for_validate] +
            [repr(a) for a in self.for_equal]
        )
        super().__init__(
            r"(.+?)", PatternModel.KEEP, str, alias=alias_content, anti=anti
        )

    def match(self, text: Union[str, Any]):
        if not text:
            text = None
        if self.anti:
            validate = False
            equal = text in self.for_equal
            for pat in self.for_validate:
                try:
                    pat.match(text)
                    validate = True
                    break
                except ParamsUnmatched:
                    continue
            if validate or equal:
                raise ParamsUnmatched(lang_config.args_error.format(target=text))
            return text
        not_match = True
        not_equal = text not in self.for_equal
        if not_equal:
            for pat in self.for_validate:
                try:
                    text = pat.match(text)
                    not_match = False
                    break
                except (ParamsUnmatched, TypeError):
                    continue
        if not_match and not_equal:
            raise ParamsUnmatched(lang_config.args_error.format(target=text))
        return text

    def __repr__(self):
        return ("!" if self.anti else "") + ("|".join(
            [repr(a) for a in self.for_validate] + [repr(a) for a in self.for_equal]
        ))


class SequenceArg(BasePattern):
    """匹配列表或者元组或者集合"""
    form: str
    arg_value: BasePattern

    def __init__(self, base: BasePattern, form: str = "list"):
        if base is AnyOne:
            base = _String
        self.form = form
        alias_content = base.alias or base.origin_type.__name__
        self.arg_value = base
        if form == "list":
            super().__init__(r"\[(.+?)\]", PatternModel.REGEX_MATCH, list, alias=f"List[{alias_content}]")
        elif form == "tuple":
            super().__init__(r"\((.+?)\)", PatternModel.REGEX_MATCH, tuple, alias=f"Tuple[{alias_content}]")
        elif form == "set":
            super().__init__(r"\{(.+?)\}", PatternModel.REGEX_MATCH, set, alias=f"Set[{alias_content}]")
        else:
            raise ValueError(lang_config.types_sequence_form_error.format(target=form))

    def match(self, text: Union[str, Any]):
        _res = super().match(text)
        sequence = re.split(r"\s*,\s*", _res) if isinstance(_res, str) else _res
        result = []
        for s in sequence:
            try:
                result.append(self.arg_value.match(s))
            except ParamsUnmatched:
                raise ParamsUnmatched(f"{s} is not matched with {self.arg_value}")
        return self.origin_type(result)

    def __repr__(self):
        return f"{self.form}[{self.arg_value}]"


class MappingArg(BasePattern):
    """匹配字典或者映射表"""
    arg_key: BasePattern
    arg_value: BasePattern

    def __init__(self, arg_key: BasePattern, arg_value: BasePattern):
        self.arg_key = arg_key
        self.arg_value = arg_value

        alias_content = f"{self.arg_key.alias or self.arg_key.origin_type.__name__}, " \
                        f"{self.arg_value.alias or self.arg_value.origin_type.__name__}"
        super().__init__(r"\{(.+?)\}", PatternModel.REGEX_MATCH, dict, alias=f"Dict[{alias_content}]")

    def match(self, text: Union[str, Any]):
        _res = super().match(text)
        result = {}

        def _generator_items(res: Union[str, Dict]):
            if isinstance(res, dict):
                return res.items()
            for m in re.split(r"\s*,\s*", res):
                _k, _v = re.split(r"\s*[:=]\s*", m)
                yield _k, _v

        for k, v in _generator_items(_res):
            try:
                real_key = self.arg_key.match(k)
            except ParamsUnmatched:
                raise ParamsUnmatched(f"{k} is not matched with {self.arg_key}")
            try:
                arg_find = self.arg_value.match(v)
            except ParamsUnmatched:
                raise ParamsUnmatched(f"{v} is not matched with {self.arg_value}")
            result[real_key] = arg_find

        return result

    def __repr__(self):
        return f"dict[{self.arg_key.origin_type.__name__}, {self.arg_value}]"


pattern_map = {
    Any: AnyOne, Ellipsis: AnyOne, object: AnyOne, "email": _Email, "color": _HexColor,
    "hex": _HexLike, "ip": _IP, "url": _Url, "...": AnyOne, "*": AllParam, "": Empty
}


def set_converter(
        target: BasePattern,
        alias: Optional[str] = None,
        cover: bool = False
):
    """
    增加 Alconna 内使用的类型转换器

    Args:
        target: 设置的表达式
        alias: 目标类型的别名
        cover: 是否覆盖已有的转换器
    """
    for k in (alias, target.alias, target.origin_type):
        if k not in pattern_map or cover:
            pattern_map[k] = target
        else:
            al_pat = pattern_map[k]
            if isinstance(al_pat, UnionArg):
                pattern_map[k] = UnionArg([*al_pat.arg_value, target])
            else:
                pattern_map[k] = UnionArg([al_pat, target])


def set_converters(
        patterns: Union[Iterable[BasePattern], Dict[str, BasePattern]],
        cover: bool = False
):
    for arg_pattern in patterns:
        if isinstance(patterns, Dict):
            set_converter(patterns[arg_pattern], alias=arg_pattern, cover=cover)  # type: ignore
        else:
            set_converter(arg_pattern, cover=cover)  # type: ignore


def remove_converter(origin_type: type, alias: Optional[str] = None):
    """

    :param origin_type:
    :param alias:
    :return:
    """
    if alias and (al_pat := pattern_map.get(alias)):
        if isinstance(al_pat, UnionArg):
            pattern_map[alias] = UnionArg(list(filter(lambda x: x.alias != alias, al_pat.arg_value)))  # type: ignore
        else:
            del pattern_map[alias]
    elif al_pat := pattern_map.get(origin_type):
        if isinstance(al_pat, UnionArg):
            pattern_map[origin_type] = UnionArg(
                list(filter(lambda x: x.origin_type != origin_type, al_pat.arg_value))  # type: ignore
            )
        else:
            del pattern_map[origin_type]


StrPath = BasePattern(model=PatternModel.TYPE_CONVERT, origin_type=Path, alias="path", accepts=[str])
AnyPathFile = BasePattern(
    model=PatternModel.TYPE_CONVERT, origin_type=bytes, alias="file", accepts=[Path], previous=StrPath,
    converter=lambda x: x.read_bytes() if x.exists() and x.is_file() else None
)

_Digit = BasePattern(r"(\-?\d+)", PatternModel.REGEX_CONVERT, int, lambda x: int(x), "int")
_Float = BasePattern(r"(\-?\d+\.?\d*)", PatternModel.REGEX_CONVERT, float, lambda x: float(x), "float")
_Bool = BasePattern(r"(True|False|true|false)", PatternModel.REGEX_CONVERT, bool, lambda x: x.lower() == "true", "bool")
_List = BasePattern(r"(\[.+?\])", PatternModel.REGEX_CONVERT, list, alias="list")
_Tuple = BasePattern(r"(\(.+?\))", PatternModel.REGEX_CONVERT, tuple, alias="tuple")
_Set = BasePattern(r"(\{.+?\})", PatternModel.REGEX_CONVERT, set, alias="set")
_Dict = BasePattern(r"(\{.+?\})", PatternModel.REGEX_CONVERT, dict, alias="dict")

set_converters([AnyPathFile, _String, _Digit, _Float, _Bool, _List, _Tuple, _Set, _Dict])


def pattern_gen(name: str, re_pattern: str):
    """便捷地设置转换器"""

    def __wrapper(func):
        return BasePattern(re_pattern, PatternModel.REGEX_CONVERT, converter=func, alias=name)

    return __wrapper


def argument_type_validator(item: Any, extra: str = "allow"):
    """对 Args 里参数类型的检查， 将一般数据类型转为 Args 使用的类型"""
    if isinstance(item, (BasePattern, _All)):
        return item
    try:
        if pat := pattern_map.get(item, None):
            return pat
    except TypeError:
        pass
    if not inspect.isclass(item) and isinstance(item, GenericAlias):
        if isinstance(item, AnnotatedAlias):
            _o = argument_type_validator(item.__origin__, extra)  # type: ignore
            if not isinstance(_o, BasePattern):
                return _o
            _arg = copy(_o)
            _arg.validator = lambda x: all(i(x) for i in item.__metadata__)
            return _arg
        origin = get_origin(item)
        if origin in (Union, Literal):
            _args = list({argument_type_validator(t, extra) for t in get_args(item)})
            return (_args[0] if len(_args) == 1 else UnionArg(_args)) if _args else item
        if origin in (dict, ABCMapping, ABCMutableMapping):
            arg_key = argument_type_validator(get_args(item)[0], 'ignore')
            arg_value = argument_type_validator(get_args(item)[1], 'allow')
            if isinstance(arg_value, list):
                arg_value = UnionArg(arg_value)
            return MappingArg(arg_key=arg_key, arg_value=arg_value)
        args = argument_type_validator(get_args(item)[0], 'allow')
        if isinstance(args, list):
            args = UnionArg(args)
        if origin in (ABCMutableSequence, list):
            return SequenceArg(args)
        if origin in (ABCSequence, ABCIterable, tuple):
            return SequenceArg(args, form="tuple")
        if origin in (ABCMutableSet, ABCSet, set):
            return SequenceArg(args, form="set")
        return BasePattern("", PatternModel.KEEP, origin, alias=f"{repr(item).split('.')[-1]}", accepts=[origin])

    if isinstance(item, (list, tuple, set)):
        return UnionArg(list(map(argument_type_validator, item)))
    if isinstance(item, dict):
        return MappingArg(
            arg_key=argument_type_validator(list(item.keys())[0], 'ignore'),
            arg_value=argument_type_validator(list(item.values())[0], 'allow')
        )
    if item is None or type(None) == item:
        return Empty
    if isinstance(item, str):
        return BasePattern(item, alias=f"\'{item}\'")
    if extra == "ignore":
        return AnyOne
    elif extra == "reject":
        raise TypeError(lang_config.types_validate_reject.format(target=item))
    if inspect.isclass(item):
        return BasePattern.of(item)
    return item


class Bind:
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise TypeError("Type Bind cannot be instantiated.")

    @classmethod
    @lru_cache(maxsize=None)
    def __class_getitem__(cls, params):
        if not isinstance(params, tuple) or len(params) != 2:
            raise TypeError(
                "Bind[...] should be used with only two arguments (a type and an annotation)."
            )
        if not (pattern := pattern_map.get(params[0]) if not isinstance(params[0], BasePattern) else params[0]):
            raise ValueError(
                "Bind[...] first argument should be a BasePattern."
            )
        if not callable(params[1]):
            raise TypeError(
                "Bind[...] second argument should be a callable."
            )
        pattern = copy(pattern)
        pattern.validator = params[1]
        return pattern


__all__ = [
    "DataUnit", "DataCollection", "Empty", "AnyOne", "AllParam", "_All", "PatternModel",
    "BasePattern", "MultiArg", "SequenceArg", "UnionArg", "MappingArg", "Bind",
    "pattern_gen", "pattern_map", "set_converter", "set_converters", "remove_converter", "argument_type_validator"
]
