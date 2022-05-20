"""Alconna 参数相关"""
import re
import inspect
from collections.abc import (
    Iterable as ABCIterable,
    Sequence as ABCSequence,
    Set as ABCSet,
    MutableSet as ABCMutableSet,
    MutableSequence as ABCMutableSequence,
    MutableMapping as ABCMutableMapping,
    Mapping as ABCMapping,
)
from enum import IntEnum
from typing import TypeVar, Type, Callable, Optional, Protocol, Any, Pattern, Union, Sequence, \
    List, Dict, get_args, Literal, Tuple, get_origin, Iterable, Generic
from types import LambdaType
from pathlib import Path

from .exceptions import ParamsUnmatched
from .lang import lang_config
from .util import generic_isinstance

DataUnit = TypeVar("DataUnit")


class DataCollection(Protocol[DataUnit]):
    """数据集合协议"""

    def __str__(self) -> str:
        ...

    def __iter__(self) -> DataUnit:
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

    anti: bool
    origin_type: Type[TOrigin]
    accepts: Optional[List[Type]]
    alias: Optional[str]
    previous: Optional["BasePattern"]

    __slots__ = "regex_pattern", "pattern", "model", "converter", "origin_type", "accepts", "alias", "previous", "anti"

    def __init__(
        self,
        pattern: str = "(.+?)",
        model: PatternModel = PatternModel.REGEX_MATCH,
        origin_type: Type[TOrigin] = str,
        converter: Optional[Callable[[Union[str, Any]], TOrigin]] = None,
        alias: Optional[str] = None,
        previous: Optional["BasePattern"] = None,
        accepts: Optional[List[Type]] = None,
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
        self.anti = anti

    def __repr__(self):
        if self.model == PatternModel.KEEP:
            return ('|'.join(x.__name__ for x in self.accepts)) if self.accepts else 'Any'
        if self.model == PatternModel.REGEX_MATCH:
            text = self.alias or self.pattern
        elif self.model == PatternModel.REGEX_CONVERT:
            text = self.alias or self.origin_type.__name__
        else:
            text = f"{(('|'.join(x.__name__ for x in self.accepts)) + ' -> ') if self.accepts else '' }" \
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
            return self.converter(input_)
        if not isinstance(input_, str):
            raise ParamsUnmatched(lang_config.args_type_error.format(target=type(input_)))
        if r := self.regex_pattern.findall(input_):
            return self.converter(r[0]) if self.model == PatternModel.REGEX_CONVERT else r[0]
        raise ParamsUnmatched(lang_config.args_error.format(target=input_))

    def validate(self, input_: Union[str, Any], default: Optional[Any] = None) -> Tuple[Any, Literal["V", "E", "D"]]:
        if not self.anti:
            try:
                return self.match(input_), "V"
            except Exception as e:
                if default is None:
                    return e, "E"
                return None if default is Empty else default, "D"
        try:
            self.match(input_)
        except ParamsUnmatched:
            return input_, "V"
        else:
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
    arg_value: Sequence[Union[BasePattern, object, str]]
    for_validate: List[BasePattern]
    for_equal: List[Union[str, object]]

    __validator__: Callable = lambda x: x if isinstance(x, Sequence) else [x]

    def __init__(self, base: Sequence[Union[BasePattern, object, str]], anti: bool = False):
        self.arg_value = base

        self.for_validate = []
        self.for_equal = []

        for arg in self.arg_value:
            if arg == Empty:
                continue
            if isinstance(arg, BasePattern):
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
                except ParamsUnmatched:
                    continue
        if not_match and not_equal:
            raise ParamsUnmatched(lang_config.args_error.format(target=text))
        return text

    def __repr__(self):
        return ("!" if self.anti else "") + ("|".join(
            [repr(a) for a in self.for_validate] + [repr(a) for a in self.for_equal]
        ))

    def __class_getitem__(cls, item):
        return cls(cls.__validator__(item))


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
_Bool = BasePattern(
    r"(True|False|true|false)",
    PatternModel.REGEX_CONVERT,
    bool,
    lambda x: x.lower() == "true",
    "bool",
)

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
    if not inspect.isclass(item) and item.__class__.__name__ in "_GenericAlias":
        origin = get_origin(item)
        if origin in (Union, Literal):
            _args = list({argument_type_validator(t, extra) for t in get_args(item)})
            return (_args[0] if len(_args) == 1 else _args) if _args else item
        if origin in (dict, ABCMapping, ABCMutableMapping):
            arg_key = argument_type_validator(get_args(item)[0], 'ignore')
            arg_value = argument_type_validator(get_args(item)[1], 'ignore')
            if isinstance(arg_value, list):
                arg_value = UnionArg(arg_value)
            return MappingArg(arg_key=arg_key, arg_value=arg_value)
        args = argument_type_validator(get_args(item)[0], 'ignore')
        if isinstance(args, list):
            args = UnionArg(args)
        if origin in (ABCMutableSequence, list):
            return SequenceArg(args)
        if origin in (ABCSequence, ABCIterable, tuple):
            return SequenceArg(args, form="tuple")
        if origin in (ABCMutableSet, ABCSet, set):
            return SequenceArg(args, form="set")

    if isinstance(item, (list, tuple, set)):
        return UnionArg(list(map(argument_type_validator, item)))
    if isinstance(item, dict):
        return MappingArg(
            arg_key=argument_type_validator(list(item.keys())[0], 'ignore'),
            arg_value=argument_type_validator(list(item.values())[0], 'ignore')
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


UnionArg.__validator__ = lambda x: [
    argument_type_validator(t, "allow") for t in (x if isinstance(x, Sequence) else [x])
]


class ObjectPattern(BasePattern):

    def __init__(
            self,
            origin: Type[TOrigin],
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
            if name in ("self", "cls"):
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
                            len(_s_sig.parameters) == 1 and inspect.ismethod(suppliers[name])
                    ):
                        self._supplement_map[name] = suppliers[name]
                    elif len(_s_sig.parameters) == 1 or (
                            len(_s_sig.parameters) == 2 and inspect.ismethod(suppliers[name])
                    ):
                        self._require_map[name] = suppliers[name]
                        if flag == "http":
                            _re_patterns.append(f"{name}=(?P<{name}>.+?)")  # &
                        elif flag == "json":
                            _re_patterns.append(f"\\'{name}\\':\\'(?P<{name}>.+?)\\'")  # ,
                        elif flag == "part":
                            _re_patterns.append(f"(?P<{name}>.+?)")  # ;
                    else:
                        raise TypeError(
                            lang_config.types_supplier_params_error.format(target=name, origin=origin.__name__)
                        )
                elif isinstance(suppliers[name], LambdaType):
                    if len(_s_sig.parameters) == 0:
                        self._supplement_map[name] = suppliers[name]
                    elif len(_s_sig.parameters) == 1:
                        self._require_map[name] = suppliers[name]
                        if flag == "http":
                            _re_patterns.append(f"{name}=(?P<{name}>.+?)")  # &
                        elif flag == "json":
                            _re_patterns.append(f"\\'{name}\\':\\'(?P<{name}>.+?)\\'")  # ,
                        elif flag == "part":
                            _re_patterns.append(f"(?P<{name}>.+?)")  # ;
                    else:
                        raise TypeError(
                            lang_config.types_supplier_params_error.format(target=name, origin=origin.__name__)
                        )
                else:
                    raise TypeError(lang_config.types_supplier_return_error.format(
                        target=name, origin=origin.__name__, source=param.annotation
                    ))
            elif param.default not in (Empty, None, Ellipsis):
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
                        pat = _String
                    elif inspect.isclass(param.annotation) and issubclass(param.annotation, str):
                        pat = _String
                    elif inspect.isclass(param.annotation) and issubclass(param.annotation, int):
                        pat = _Digit
                    elif pat is None:
                        raise TypeError(lang_config.types_supplier_missing.format(target=name, origin=origin.__name__))

                if isinstance(pat, ObjectPattern):
                    raise TypeError(lang_config.types_type_error.format(target=pat))
                self._require_map[name] = pat.match
                if pat.model == PatternModel.REGEX_CONVERT:
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
            elif flag == "json":
                _re_pattern = (f"{head}:" if head else "") + "{" + ",".join(_re_patterns) + "}"
            elif flag == "part":
                _re_pattern = (f"{head};" if head else "") + ";".join(_re_patterns)
        else:
            _re_pattern = f"{head}" if head else f"{self.origin.__name__}"

        super().__init__(
            _re_pattern,
            model=PatternModel.REGEX_MATCH, origin_type=self.origin, alias=head or self.origin.__name__,
        )
        set_converter(self)

    def match(self, text: str):
        if matched := self.regex_pattern.fullmatch(text):
            args = matched.groupdict()
            for k in self._require_map:
                if k in args:
                    self._params[k] = self._require_map[k](args[k])
                    if self._transform_map.get(k, None):
                        self._params[k] = self._transform_map[k](self._params[k])
            for k in self._supplement_map:
                self._params[k] = self._supplement_map[k]()
            return self.origin(**self._params)
        raise ParamsUnmatched(lang_config.args_error.format(target=text))

    def __call__(self, *args, **kwargs):
        return self.origin(*args, **kwargs)

    def __eq__(self, other):
        return isinstance(other, ObjectPattern) and self.origin == other.origin


__all__ = [
    "DataUnit", "DataCollection", "Empty", "AnyOne", "AllParam", "_All", "PatternModel",
    "BasePattern", "MultiArg", "SequenceArg", "UnionArg", "MappingArg", "ObjectPattern",
    "pattern_gen", "pattern_map", "set_converter", "set_converters", "remove_converter", "argument_type_validator"
]
