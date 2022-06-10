"""Alconna 参数相关"""
import re
import inspect
from copy import copy
from collections.abc import Sequence as ABCSeq, Set as ABCSet, \
    MutableSet as ABCMuSet, MutableSequence as ABCMuSeq, MutableMapping as ABCMuMap, Mapping as ABCMap
from contextlib import suppress
from functools import lru_cache
from pathlib import Path
from enum import IntEnum
from typing import TypeVar, Type, Callable, Optional, Protocol, Any, Pattern, Union, List, Dict, \
    get_args, Literal, Tuple, get_origin, Iterable, Generic, Iterator, runtime_checkable

try:
    from typing import Annotated  # type: ignore
except ImportError:
    from typing_extensions import Annotated

from .exceptions import ParamsUnmatched
from .config import config
from .util import generic_isinstance

DataUnit = TypeVar("DataUnit", covariant=True)
GenericAlias = type(List[int])
AnnotatedAlias = type(Annotated[int, lambda x: x > 0])


@runtime_checkable
class DataCollection(Protocol[DataUnit]):
    """数据集合协议"""
    def __str__(self) -> str: ...
    def __iter__(self) -> Iterator[DataUnit]: ...
    def __len__(self) -> int: ...


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
    def __repr__(self):
        return "AllParam"


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
    validators: List[Callable[[TOrigin], bool]]

    anti: bool
    origin: Type[TOrigin]
    accepts: Optional[List[Type]]
    alias: Optional[str]
    previous: Optional["BasePattern"]

    __slots__ = (
        "regex_pattern", "pattern", "model", "converter", "anti", "origin", "accepts", "alias", "previous", "validators"
    )

    def __init__(
            self,
            pattern: str = "(.+?)",
            model: PatternModel = PatternModel.REGEX_MATCH,
            origin: Type[TOrigin] = str,
            converter: Optional[Callable[[Union[str, Any]], TOrigin]] = None,
            alias: Optional[str] = None,
            previous: Optional["BasePattern"] = None,
            accepts: Optional[List[Type]] = None,
            validators: Optional[List[Callable[[TOrigin], bool]]] = None,
            anti: bool = False
    ):
        """
        初始化参数匹配表达式
        """
        self.pattern = pattern
        self.regex_pattern = re.compile(f"^{pattern}$")
        self.model = model
        self.origin = origin
        self.alias = alias
        self.previous = previous
        self.accepts = accepts
        self.converter = converter or (lambda x: origin(x) if model == PatternModel.TYPE_CONVERT else eval(x))
        self.validators = validators or [(lambda x: True)]
        self.anti = anti

    def __repr__(self):
        if self.model == PatternModel.KEEP:
            return self.alias or (('|'.join(x.__name__ for x in self.accepts)) if self.accepts else 'Any')
        name = self.alias or self.origin.__name__
        if self.model == PatternModel.REGEX_MATCH:
            text = self.alias or self.pattern
        elif self.model == PatternModel.REGEX_CONVERT:
            text = name
        else:
            text = (('|'.join(x.__name__ for x in self.accepts) + ' -> ') if self.accepts else '') + name
        return f"{(f'{self.previous.__repr__()}, ' if self.previous else '')}{'!' if self.anti else ''}{text}"

    def __str__(self):
        return self.__repr__()

    def __hash__(self):
        return hash(self.__repr__())

    def __eq__(self, other):
        return isinstance(other, BasePattern) and self.__repr__() == other.__repr__()

    @classmethod
    def of(cls, unit: Type[TOrigin]):
        """提供原来 TAValue 中的 Type[DataUnit] 类型的构造方法"""
        return cls('', PatternModel.KEEP, unit, alias=unit.__name__, accepts=[unit])

    @classmethod
    def on(cls, obj: TOrigin):
        """提供原来 TAValue 中的 DataUnit 类型的构造方法"""
        return cls('', PatternModel.KEEP, type(obj), alias=str(obj), validators=[lambda x: x == obj])

    def reverse(self):
        self.anti = not self.anti
        return self

    def match(self, input_: Union[str, Any]) -> TOrigin:
        """
        对传入的参数进行匹配, 如果匹配成功, 则返回转换后的值, 否则返回None
        """
        if self.model > 1 and self.origin != Any and generic_isinstance(input_, self.origin):
            return input_  # type: ignore
        if self.accepts and not isinstance(input_, tuple(self.accepts)):
            if not self.previous or not isinstance(input_ := self.previous.match(input_), tuple(self.accepts)):
                raise ParamsUnmatched(config.lang.args_type_error.format(target=input_.__class__))
        if self.model == PatternModel.KEEP:
            return input_  # type: ignore
        if self.model == PatternModel.TYPE_CONVERT:
            res = self.converter(input_)
            if not generic_isinstance(res, self.origin) or (not res and self.origin == Any):
                raise ParamsUnmatched(config.lang.args_error.format(target=input_))
            return res
        if not isinstance(input_, str):
            if not self.previous or not isinstance(input_ := self.previous.match(input_), str):
                raise ParamsUnmatched(config.lang.args_type_error.format(target=type(input_)))
        if r := self.regex_pattern.findall(input_):
            return self.converter(r[0]) if self.model == PatternModel.REGEX_CONVERT else r[0]
        raise ParamsUnmatched(config.lang.args_error.format(target=input_))

    def validate(self, input_: Union[str, Any], default: Optional[Any] = None) -> Tuple[Any, Literal["V", "E", "D"]]:
        try:
            res = self.match(input_)
            if all(i(res) for i in self.validators):
                return res, "V"
            raise ParamsUnmatched(config.lang.args_error.format(target=input_))
        except Exception as e:
            if default is None:
                return e, "E"
            return None if default is Empty else default, "D"

    def invalidate(self, input_: Union[str, Any], default: Optional[Any] = None) -> Tuple[Any, Literal["V", "E", "D"]]:
        try:
            res = self.match(input_)
        except ParamsUnmatched:
            return input_, "V"
        else:
            if any((not i(res)) for i in self.validators):
                return input_, "E"
            if default is None:
                return ParamsUnmatched(config.lang.args_error.format(target=input_)), "E"
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

    def __init__(self, base: BasePattern, flag: Literal['args', 'kwargs'] = 'args', length: Optional[int] = None):
        self.flag = flag
        self.array_length = length
        if flag == 'args':
            _t = Tuple[base.origin, ...]
            alias = f"*{base}[:{length}]" if length else f"*{base}"
        else:
            _t = Dict[str, base.origin]
            alias = f"**{base}[:{length}]" if length else f"**{base}"
        super().__init__(
            base.pattern, base.model, _t, base.converter, alias, base.previous, base.accepts, base.validators
        )

    def __repr__(self):
        ctn = super().__repr__()
        if self.flag == 'args':
            return f"{ctn}[{self.array_length}]" if self.array_length else f"({ctn}, ...)"
        elif self.flag == 'kwargs':
            return f"{{${ctn}, ...}}"


class UnionArg(BasePattern):
    """多类型参数的匹配"""
    optional: bool
    arg_value: List[Union[BasePattern, object, str]]
    for_validate: List[BasePattern]
    for_equal: List[Union[str, object]]

    def __init__(self, base: Iterable[Union[BasePattern, object, str]], anti: bool = False):
        self.arg_value = list(base)
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
        alias_content = "|".join([repr(a) for a in self.for_validate] + [repr(a) for a in self.for_equal])
        super().__init__(r"(.+?)", PatternModel.KEEP, str, alias=alias_content, anti=anti)

    def match(self, text: Union[str, Any]):
        if not text:
            text = None
        if text not in self.for_equal:
            for pat in self.for_validate:
                with suppress(ParamsUnmatched, TypeError):
                    text = pat.match(text)
                    break
            else:
                raise ParamsUnmatched(config.lang.args_error.format(target=text))
        return text

    def __repr__(self):
        return ("!" if self.anti else "") + ("|".join(repr(a) for a in (*self.for_validate, *self.for_equal)))


class SequenceArg(BasePattern):
    """匹配列表或者元组或者集合"""
    form: str
    arg_value: BasePattern

    def __init__(self, base: BasePattern, form: str = "list"):
        if base is AnyOne:
            base = _String
        self.form = form
        self.arg_value = base
        if form == "list":
            super().__init__(r"\[(.+?)\]", PatternModel.REGEX_MATCH, list, alias=f"List[{base}]")
        elif form == "tuple":
            super().__init__(r"\((.+?)\)", PatternModel.REGEX_MATCH, tuple, alias=f"Tuple[{base}]")
        elif form == "set":
            super().__init__(r"\{(.+?)\}", PatternModel.REGEX_MATCH, set, alias=f"Set[{base}]")
        else:
            raise ValueError(config.lang.types_sequence_form_error.format(target=form))

    def match(self, text: Union[str, Any]):
        _res = super().match(text)
        result = []
        for s in (re.split(r"\s*,\s*", _res) if isinstance(_res, str) else _res):
            try:
                result.append(self.arg_value.match(s))
            except ParamsUnmatched as e:
                raise ParamsUnmatched(f"{s} is not matched with {self.arg_value}") from e
        return self.origin(result)

    def __repr__(self):
        return f"{self.form}[{self.arg_value}]"


class MappingArg(BasePattern):
    """匹配字典或者映射表"""
    arg_key: BasePattern
    arg_value: BasePattern

    def __init__(self, arg_key: BasePattern, arg_value: BasePattern):
        self.arg_key = arg_key
        self.arg_value = arg_value
        super().__init__(r"\{(.+?)\}", PatternModel.REGEX_MATCH, dict, alias=f"Dict[{self.arg_key}, {self.arg_value}]")

    def match(self, text: Union[str, Any]):
        _res = super().match(text)
        result = {}

        def _generator_items(res: Union[str, Dict]):
            if isinstance(res, dict):
                return res.items()
            for m in re.split(r"\s*,\s*", res):
                yield re.split(r"\s*[:=]\s*", m)

        for k, v in _generator_items(_res):
            try:
                real_key = self.arg_key.match(k)
            except ParamsUnmatched as e:
                raise ParamsUnmatched(f"{k} is not matched with {self.arg_key}") from e
            try:
                arg_find = self.arg_value.match(v)
            except ParamsUnmatched as e:
                raise ParamsUnmatched(f"{v} is not matched with {self.arg_value}") from e
            result[real_key] = arg_find

        return result

    def __repr__(self):
        return f"dict[{self.arg_key.origin.__name__}, {self.arg_value}]"


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
    for k in (alias, target.alias, target.origin):
        if k not in pattern_map or cover:
            pattern_map[k] = target
        else:
            al_pat = pattern_map[k]
            pattern_map[k] = UnionArg([*al_pat.arg_value, target]) if isinstance(al_pat, UnionArg) else (
                UnionArg([al_pat, target])
            )


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
    if alias and (al_pat := pattern_map.get(alias)):
        if isinstance(al_pat, UnionArg):
            pattern_map[alias] = UnionArg(filter(lambda x: x.alias != alias, al_pat.arg_value))  # type: ignore
        else:
            del pattern_map[alias]
    elif al_pat := pattern_map.get(origin_type):
        if isinstance(al_pat, UnionArg):
            pattern_map[origin_type] = UnionArg(filter(lambda x: x.origin != origin_type, al_pat.arg_value))
        else:
            del pattern_map[origin_type]


StrPath = BasePattern(model=PatternModel.TYPE_CONVERT, origin=Path, alias="path", accepts=[str])
AnyPathFile = BasePattern(
    model=PatternModel.TYPE_CONVERT, origin=bytes, alias="file", accepts=[Path], previous=StrPath,
    converter=lambda x: x.read_bytes() if x.exists() and x.is_file() else None  # type: ignore
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


def args_type_parser(item: Any, extra: str = "allow"):
    """对 Args 里参数类型的检查， 将一般数据类型转为 Args 使用的类型"""
    if isinstance(item, (BasePattern, _All)):
        return item
    with suppress(TypeError):
        if pat := pattern_map.get(item, None):
            return pat
    if not inspect.isclass(item) and isinstance(item, GenericAlias):
        if isinstance(item, AnnotatedAlias):
            if not isinstance(_o := args_type_parser(item.__origin__, extra), BasePattern):  # type: ignore
                return _o
            _arg = copy(_o)
            _arg.validators.extend(item.__metadata__)    # type: ignore
            return _arg
        origin = get_origin(item)
        if origin in (Union, Literal):
            _args = {args_type_parser(t, extra) for t in get_args(item)}
            return (_args.pop() if len(_args) == 1 else UnionArg(_args)) if _args else item
        if origin in (dict, ABCMap, ABCMuMap):
            arg_key = args_type_parser(get_args(item)[0], 'ignore')
            arg_value = args_type_parser(get_args(item)[1], 'allow')
            if isinstance(arg_value, list):
                arg_value = UnionArg(arg_value)
            return MappingArg(arg_key=arg_key, arg_value=arg_value)
        args = args_type_parser(get_args(item)[0], 'allow')
        if isinstance(args, list):
            args = UnionArg(args)
        if origin in (ABCMuSeq, list):
            return SequenceArg(args)
        if origin in (ABCSeq, tuple):
            return SequenceArg(args, form="tuple")
        if origin in (ABCMuSet, ABCSet, set):
            return SequenceArg(args, form="set")
        return BasePattern("", PatternModel.KEEP, origin, alias=f"{repr(item).split('.')[-1]}", accepts=[origin])

    if isinstance(item, str):
        return BasePattern(item, alias=f"\'{item}\'")
    if isinstance(item, (list, tuple, set, ABCSeq, ABCMuSeq, ABCSet, ABCMuSet)):  # Args[foo, [123, int]]
        return UnionArg(map(args_type_parser, item))
    if isinstance(item, (dict, ABCMap, ABCMuMap)):  # Args[foo, {'foo': 'bar'}]
        return BasePattern(model=PatternModel.TYPE_CONVERT, origin=Any, converter=lambda x: item.get(x, None))
    if item is None or type(None) == item:
        return Empty
    if extra == "ignore":
        return AnyOne
    elif extra == "reject":
        raise TypeError(config.lang.types_validate_reject.format(target=item))
    if inspect.isclass(item):
        return BasePattern.of(item)
    return BasePattern.on(item)


class Bind:
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise TypeError("Type Bind cannot be instantiated.")

    @classmethod
    @lru_cache(maxsize=None)
    def __class_getitem__(cls, params):
        if not isinstance(params, tuple) or len(params) < 2:
            raise TypeError("Bind[...] should be used with only two arguments (a type and an annotation).")
        if not (pattern := params[0] if isinstance(params[0], BasePattern) else pattern_map.get(params[0])):
            raise ValueError("Bind[...] first argument should be a BasePattern.")
        if not all(callable(i) for i in params[1:]):
            raise TypeError("Bind[...] second argument should be a callable.")
        pattern = copy(pattern)
        pattern.validators.extend(params[1:])
        return pattern


__all__ = [
    "DataCollection", "Empty", "AnyOne", "AllParam", "PatternModel", "BasePattern", "MultiArg", "UnionArg", "Bind",
    "pattern_gen", "pattern_map", "set_converter", "set_converters", "remove_converter", "args_type_parser"
]
