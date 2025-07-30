"""Alconna 的基础内容相关"""
from __future__ import annotations

import re
from copy import deepcopy
import warnings
import dataclasses as dc
import typing
from typing import Any, Callable, Generic, Literal, TypeVar, ClassVar, ForwardRef, Final, TYPE_CHECKING, get_origin, get_args, Iterable, Sequence, TypedDict
from typing_extensions import dataclass_transform, ParamSpec, Concatenate, TypeAlias, TypeVarTuple, Unpack

from nepattern import TPattern, NONE, Pattern, RawStr, UnionPattern, parser
from typing_extensions import Self

from tarina import Empty

from .i18n import i18n
from .utils import Unset, UNSET, levenshtein

from ._dcls import safe_dcls_kw, safe_field_kw
from .exceptions import InvalidArgs
from .receiver import Rx
from .utils import TAValue, parent_frame_namespace, merge_cls_and_parent_ns

_T = TypeVar("_T")
_T1 = TypeVar("_T1")


@dc.dataclass
class Trigger:
    """触发器, 用于标识参数单元的触发方式"""

    name: str
    """触发器名称"""
    alias: dc.InitVar[str | Iterable[str] | None] = dc.field(default=None)
    """触发器别名, 可以是字符串或字符串列表"""
    aliases: frozenset[str] = dc.field(init=False)
    """触发器别名"""
    seps: str = " "
    """触发器分隔符, 默认为空格"""
    integrate: bool = False
    """是否为集成触发器, 默认为 False
    
    若为 True, 则触发器的解析结果即为参数单元的输入。
    """

    def __post_init__(self, alias: str | Iterable[str] | None = None):
        aliases = list(alias or [])
        if "|" in self.name:
            _aliases = self.name.split("|")
            _aliases.sort(key=len, reverse=True)
            self.name = _aliases[0]
            aliases.extend(_aliases[1:])
        self.aliases = frozenset([self.name, *aliases])


@dc.dataclass(**safe_dcls_kw(slots=True))
class Field(Generic[_T]):
    """标识参数单元字段"""

    default: _T | type[Empty] = dc.field(default=Empty)
    """参数单元的默认值"""
    default_factory: Callable[[], _T] | type[Empty] = dc.field(default=Empty)
    """参数单元的默认值工厂"""
    trigger: Trigger | None = None
    """参数单元的触发器。若参数单元设置了触发器，则该参数单元需要先满足触发器"""
    show: str | None = dc.field(default=None)
    """参数单元默认值的别名"""
    completion: Callable[[], str | list[str] | None] | None = dc.field(default=None, repr=False)
    """参数单元的补全"""
    unmatch_tips: Callable[[Any], str] | None = dc.field(default=None, repr=False)
    """参数单元的错误提示"""
    missing_tips: Callable[[], str] | None = dc.field(default=None, repr=False)
    """参数单元的缺失提示"""
    help_text: str | None = dc.field(default=None, compare=False, hash=False)
    """参数单元的注释"""
    seps: str = dc.field(default=" ", compare=False, hash=False)
    """参数单元使用的分隔符"""
    optional: bool = dc.field(default=False, compare=False, hash=False)
    """参数单元是否可选"""
    hidden: bool = dc.field(default=False, compare=False, hash=False)
    """参数单元是否隐藏类型"""
    multiple: bool | int | Literal["+", "*", "str"] = dc.field(default=False, compare=False, hash=False)
    """参数单元是否为多值参数, 可以是布尔值, 整数, 或者标识符"""
    wildcard: bool = dc.field(default=False, compare=False, hash=False)
    """参数单元是否为通配符参数, 通常用于匹配任意值"""
    action: Rx[_T] | None = dc.field(default=None, compare=False, hash=False)
    """参数单元的动作, 用于处理参数值"""

    @property
    def display(self):
        """返回参数单元的显示值"""
        return self.show or self.get_default()

    @property
    def no_default(self):
        return self.default is Empty and self.default_factory is Empty

    def get_default(self):
        """返回参数单元的默认值"""
        return self.default_factory() if self.default_factory is not Empty else self.default

    def get_completion(self):
        """返回参数单元的补全"""
        return self.completion() if self.completion else None

    def get_unmatch_tips(self, value: Any, fallback: str):
        """返回参数单元的错误提示"""
        if not self.unmatch_tips:
            return fallback
        gen = self.unmatch_tips(value)
        return gen or fallback

    def get_missing_tips(self, fallback: str):
        """返回参数单元的缺失提示"""
        if not self.missing_tips:
            return fallback
        gen = self.missing_tips()
        return gen or fallback

    def to_dc_field(self):
        if self.default_factory is not Empty:
            return dc.field(default_factory=self.default_factory)
        if self.default is not Empty:
            return dc.field(default=self.default)
        return dc.field()


def arg_field(
    default: Any | type[Empty] = Empty,
    *,
    default_factory: Any | type[Empty] = Empty,
    init: bool = True,
    trigger: Trigger | None = None,
    show: str | None = None,
    completion: Callable[[], str | list[str] | None] | None = None,
    unmatch_tips: Callable[[Any], str] | None = None,
    missing_tips: Callable[[], str] | None = None,
    help_text: str | None = None,
    seps: str = " ",
    action: Rx[Any] | None = None,
    multiple: bool | int | Literal["+", "*", "str"] = False,
    optional: bool = False,
    hidden: bool = False,
    wildcard: bool = False,
) -> "Any":
    return Field(default, default_factory, trigger, show, completion, unmatch_tips, missing_tips, help_text, seps, optional, hidden, multiple, wildcard, action)


@dc.dataclass(**safe_dcls_kw(init=False, eq=True, unsafe_hash=True, slots=True))
class Arg(Generic[_T]):
    """参数单元"""

    name: str = dc.field(compare=True, hash=True)
    """参数单元的名称"""
    type_: Pattern[_T] = dc.field(compare=False, hash=True)
    """参数单元的类型"""
    field: Field[_T] = dc.field(compare=False, hash=False)
    """参数单元的字段"""

    def __init__(
        self,
        name: str,
        type_: TAValue[_T] | None = None,
        field: Field[_T] | _T | type[Empty] = Empty,
        **kwargs,
    ):
        if not isinstance(name, str) or name.startswith("$"):
            raise InvalidArgs(i18n.require("args.name_error"))
        if not name.strip():
            raise InvalidArgs(i18n.require("args.name_empty"))
        self.name = name
        _value = parser(type_ or RawStr(name))
        _field = field if isinstance(field, Field) else Field(field)
        if isinstance(_value, UnionPattern) and _value.optional:
            _field.default = None if _field.default is Empty else _field.default  # type: ignore
        if _value == NONE:
            raise InvalidArgs(i18n.require("args.value_error").format(target=name))
        self.type_ = _value  # type: ignore
        self.field = _field

        if res := re.match(r"^(?P<name>.+?)#(?P<notice>[^;?/#]+)", name):
            self.field.help_text = res["notice"]
            self.name = res["name"]
        if res := re.match(r"^(?P<name>.+?)(;)?(?P<flag>[?/]+)", self.name):
            if "?" in res["flag"]:
                self.field.optional = True
            if "/" in res["flag"]:
                self.field.hidden = True
            self.name = res["name"]

        if kwargs:
            for k, v in kwargs.items():
                if hasattr(self.field, k):
                    warnings.warn(f"Arg(..., {k}={v}) is deprecated, use Field({k}={v}) instead", DeprecationWarning,
                                  stacklevel=2)
                    setattr(self.field, k, v)

        self.__fullname__ = self.name

    def __str__(self):
        if self.field.wildcard:
            v = n = f"...{self.name}"
        else:
            n, v = f"'{self.name_display}'", self.type_display
        return (n if n == v else f"{n}: {v}") + (
            f" = '{self.field.display}'" if self.field.display is not Empty else "")

    def __add__(self, other: Arg[_T1]) -> "_Args[_T, _T1]":
        if isinstance(other, Arg):
            return _Args[()]([]) << self << other
        raise TypeError(f"unsupported operand type(s) for +: 'Arg' and '{other.__class__.__name__}'")

    def __iter__(self):
        return iter((self.name, self.type_, self.field))

    @property
    def separators(self):
        return self.field.seps

    @property
    def name_display(self):
        n = self.name
        if self.field.optional:
            n = f"{n}?"
        if self.field.help_text:
            n = f"{n}#{self.field.help_text}"
        return n

    @property
    def type_display(self):
        if self.field.hidden:
            return "***"
        v = str(self.type_)
        if self.field.multiple is not False:
            if self.field.multiple is True:
                v = f"({v}+)"
            elif self.field.multiple == "str":
                v = f"{v}+"
            elif isinstance(self.field.multiple, int):
                v = f"({v}+)[:{self.field.multiple}]"
            else:
                v = f"({v}{self.field.multiple})"
        return v


_P = ParamSpec("_P")
T = TypeVar("T")
Ts = TypeVarTuple("Ts")
Ts1 = TypeVarTuple("Ts1")


def _arg_init_wrapper(func: Callable[_P, Field[_T]]):
    def _wrapper(builder: "_Args[Unpack[Ts1]]", name: str) -> Callable[Concatenate[TAValue[_T], _P], "_Args[Unpack[Ts1], _T]"]:
        """Wrapper for creating Args with a specific name and type."""
        return lambda type_, *args, **kwargs: builder.__lshift__(Arg(name, type_, func(*args, **kwargs)))
    return _wrapper


wrapper = _arg_init_wrapper(Field)


def _arg_init_wrapper1(func: Callable[_P, Field[_T]]):
    def _wrapper(name: str) -> Callable[Concatenate[TAValue[_T], _P], "_Args[_T]"]:
        return lambda type_, *args, **kwargs: _Args([Arg(name, type_, func(*args, **kwargs))])
    return _wrapper


wrapper1 = _arg_init_wrapper1(Field)


class __ArgsBuilder:
    __slots__ = ()

    def __getattr__(self, item: str):
        return wrapper1(item)

    def __lshift__(self, other: Arg[_T]):
        return _Args[_T]([other])  # type: ignore


Args: Final = __ArgsBuilder()


class _Args(Generic[Unpack[Ts]]):
    __slots__ = ("_optional_count", "_origin", "_data", "_count")

    def __init__(self, args: list[Arg[Any]], origin: type[ArgsBase] | None = None):
        self._origin = origin
        self._optional_count = 0
        normal = []
        vars_positional: list[Arg[Any]] = []
        for arg in args:
            if arg.field.multiple is not False:
                vars_positional.append(arg)
            else:
                normal.append(arg)
            if arg.field.optional:
                self._optional_count += 1
            elif not arg.field.no_default:
                self._optional_count += 1
        normal.extend(vars_positional)
        self._data: list[Arg[Any]] = normal
        self._count = len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __bool__(self):
        return bool(self._data)

    def __str__(self):
        return f"Args({', '.join([f'{arg}' for arg in self._data])})" if self.data else "Empty"

    def __len__(self):
        return self._count

    def __eq__(self, other):
        return self._data == other._data

    def __repr__(self):
        return repr(self._data)

    def __lshift__(self: _Args[Unpack[Ts1]], arg: Arg[T]) -> "_Args[Unpack[Ts1], T]":
        self._data.append(arg)
        return self  # type: ignore

    def __getattr__(self, item: str):
        return wrapper(self, item)


def _is_classvar(a_type):
    # This test uses a typing internal class, but it's the best way to
    # test if this is a ClassVar.
    return a_type is typing.ClassVar or (type(a_type) is typing._GenericAlias and a_type.__origin__ is typing.ClassVar)  # type: ignore


@dataclass_transform(field_specifiers=(arg_field,), kw_only_default=True)
class ArgsMeta(type):
    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        *,
        seps: str | None = None,
        **kwargs,
    ):
        cls: type[ArgsBase] = super().__new__(mcs, name, bases, namespace, **kwargs)  # type: ignore
        data_args = []
        for b in cls.__mro__[-1:0:-1]:
            base_args: _Args | None = b.__dict__.get("__args_data__")
            if base_args is not None:
                data_args.extend(base_args._data)
        data_args = deepcopy(data_args)
        types_namespace = merge_cls_and_parent_ns(cls, parent_frame_namespace())
        cls_annotations = cls.__dict__.get("__annotations__", {})
        cls_args: list[Arg] = []
        for name, typ in cls_annotations.items():
            if isinstance(typ, str):  # future annotations
                typ = ForwardRef(typ, is_class=True)._evaluate(types_namespace, types_namespace, recursive_guard=frozenset())
            if _is_classvar(typ):
                continue
            if name not in cls.__dict__:
                field = Field()
            else:
                field = cls.__dict__[name]
                if not isinstance(field, Field):
                    field = Field(field)
                if field.default is Empty and field.default_factory is Empty:
                    delattr(cls, name)
            if field.multiple is not False:
                # if not field.kw_only:
                if get_origin(typ) is tuple:
                    typ = get_args(typ)[0]
                elif field.multiple != "str" or typ is not str:
                    raise TypeError(f"{name!r} is a varpos but does not have a tuple type annotation")
                # elif get_origin(typ) is not dict:
                #     raise TypeError(f"{name!r} is a varkey but does not have a dict type annotation")
            cls_args.append(Arg(name, typ, field))
        for name, value in cls.__dict__.items():
            if isinstance(value, Field) and name not in cls_annotations:
                raise TypeError(f"{name!r} is a Field but has no type annotation")
        all_args = data_args + cls_args
        for arg in all_args:
            # if kw_only is not None:
            #     arg.field.kw_only = kw_only
            if seps is not None:
                arg.field.seps = seps
        cls.__args_data__ = _Args(all_args, cls)
        try:
            dcls = dc.make_dataclass(
                cls.__name__,
                [(arg.name, arg.type_, arg.field.to_dc_field()) for arg in cls.__args_data__._data],
                namespace=types_namespace,
                repr=True,
                **safe_dcls_kw(kw_only=True)  # type: ignore
            )
        except TypeError as e:
            raise TypeError(f"cannot create Args Model: {e}") from None
        cls.__init__ = dcls.__init__  # type: ignore
        if "__repr__" not in cls.__dict__:
            cls.__repr__ = dcls.__repr__  # type: ignore
        return cls


class ArgsBase(metaclass=ArgsMeta):
    __args_data__: ClassVar[_Args]

    if not TYPE_CHECKING:
        def __init__(self, **kwargs):  # for pycharm type check
            pass

    def dump(self):
        return {arg.name: getattr(self, arg.name) for arg in self.__args_data__._data}

    @classmethod
    def load(cls, data: dict):
        for arg in cls.__args_data__._data:
            if arg.name not in data:
                if not arg.field.optional:
                    raise InvalidArgs(f"missing required argument: {arg.name}")
                data[arg.name] = None
        return cls(**data)


def handle_args(arg: Arg[Any] | list[Arg[Any]] | type[ArgsBase] | _Args | None) -> _Args:
    if arg is None:
        return _Args([])
    if isinstance(arg, _Args):
        return arg
    if isinstance(arg, Arg):
        return _Args([arg])
    if isinstance(arg, list):
        return _Args(arg)
    if issubclass(arg, ArgsBase):
        return arg.__args_data__
    raise TypeError(f"unsupported operand type(s) for +: 'Arg' and '{arg.__class__.__name__}'")


ARGS_PARAM: TypeAlias = "Arg | list[Arg] | type[ArgsBase] | _Args"


class Header:
    """命令头部的匹配表达式"""

    __slots__ = ("origin", "content", "mapping", "compact", "compact_pattern")

    def __init__(
        self,
        origin: tuple[str, list[str]],
        content: set[str],
        compact: bool,
        compact_pattern: TPattern,
    ):
        self.origin = origin  # type: ignore
        self.content = content  # type: ignore
        self.compact = compact
        self.compact_pattern = compact_pattern  # type: ignore

    def __repr__(self):
        if not self.origin[1]:
            return self.origin[0]
        if self.origin[0]:
            return f"[{'│'.join(self.origin[1])}]{self.origin[0]}" if len(
                self.content) > 1 else f"{next(iter(self.content))}"  # noqa: E501
        return '│'.join(self.origin[1])

    def is_intersect(self, header: Header) -> bool:
        """判断是否与另一个头部有交集

        Args:
            header (Header): 另一个头部

        Returns:
            bool: 是否有交集
        """
        return bool(self.content & header.content)

    @classmethod
    def generate(
        cls,
        command: str,
        prefixes: list[str],
        compact: bool,
    ):
        if not prefixes:
            return cls((command, prefixes), {command}, compact, re.compile(f"^{command}"))
        prf = "|".join(re.escape(h) for h in prefixes)
        compp = re.compile(f"^(?:{prf}){command}")
        return cls((command, prefixes), {f"{h}{command}" for h in prefixes}, compact, compp)

    def check_fuzzy(self, source: str, threshold: float):
        command = self.origin[0]
        if not self.origin[1]:
            headers_text = [str(command)]
        else:
            headers_text = []
            for prefix in self.origin[1]:
                if isinstance(prefix, tuple):
                    headers_text.append(f"{prefix[0]} {prefix[1]}{command}")
                elif isinstance(prefix, str):
                    headers_text.append(f"{prefix}{command}")
                else:
                    headers_text.append(f"{prefix} {command}")
        for ht in headers_text:
            if levenshtein(source, ht) >= threshold:
                return i18n.require("fuzzy.matched").format(target=source, source=ht)



class Subcommand:
    """子命令, 次于主命令

    与命令节点不同, 子命令可以包含多个命令选项与相对于自己的子命令
    """

    name: str
    """命令节点名称"""
    aliases: frozenset[str]
    """命令节点别名"""
    dest: str
    """命令节点目标名称"""
    default: Any
    """命令节点默认值"""
    args: _Args
    """命令节点参数"""
    separators: str
    """命令节点分隔符"""
    help_text: str
    """命令节点帮助信息"""
    soft_keyword: bool
    "是否为软关键字"
    forks: list[Subcommand]
    """子命令包含的选项与子命令"""
    _lookup_map: dict[str, Subcommand]
    """子命令选项与子命令的查找表"""

    nargs: int
    _hash: int

    def __init__(
        self,
        name: str,
        *args: Arg | _Args | type[ArgsBase] | Subcommand | list[Subcommand],
        alias: Iterable[str] | None = None,
        dest: str | None = None,
        default: Any = Empty,
        separators: str | Sequence[str] | set[str] | None = None,
        help_text: str | None = None,
        soft_keyword: bool = False
    ):
        """初始化子命令

        Args:
            name (str): 子命令名称
            *args (Arg | _Args | type[ArgsBase] | Option | Subcommand | list[Subcommand]): 参数, 选项或子命令
            dest (str | None, optional): 子命令选项目标名称
            default (Any, optional): 子命令默认值
            action (Action | None, optional): 子命令选项响应动作
            separators (str | Sequence[str] | Set[str] | None, optional): 子命令分隔符
            help_text (str | None, optional): 子命令选项帮助信息
            soft_keyword (bool, optional): 是否为软关键字
        """
        self.forks = [i for i in args if isinstance(i, Subcommand)]
        self.forks.extend(sub for subs in args if isinstance(subs, list) for sub in subs)
        _args = []
        _args_inst = None
        for arg in args:
            if isinstance(arg, (Subcommand, list)):
                continue
            if isinstance(arg, Arg):
                _args.append(arg)
                continue
            data = arg if isinstance(arg, _Args) else arg.__args_data__
            if _args_inst is None:
                _args_inst = data
                _args.extend(data._data)
            else:
                raise TypeError(f"multiple Args parameters found in {name!r}")

        self.separators = " " if separators is None else "".join(separators)
        aliases = list(alias or [])
        name = re.sub(f"[{self.separators}]", "", name)
        if "|" in name:
            _aliases = name.split("|")
            _aliases.sort(key=len, reverse=True)
            name = _aliases[0]
            aliases.extend(_aliases[1:])
        if not name:
            raise InvalidArgs(i18n.require("common.name_empty"))
        self.name = name
        self.aliases = frozenset([name, *aliases])
        self.args = _Args(_args, origin=_args_inst._origin if _args_inst else None)
        self.default = default
        # _handle_default(self)

        self.nargs = len(self.args._data)
        self.dest = dest or self.name
        self.dest = self.dest.lstrip("-") or self.dest
        self.help_text = help_text or self.dest
        self.soft_keyword = soft_keyword
        self._hash = self._calc_hash()
        self._lookup_map = {al: opt for opt in self.forks for al in opt.aliases}

    def __add__(self, other: ARGS_PARAM | Subcommand) -> Self:
        """连接子命令与命令选项或命令节点

        Args:
            other (Arg | list[Arg] | ArgsBuilder | type[ArgsBase] | str): 命令选项或命令节点

        Returns:
            Self: 返回子命令自身

        Raises:
            TypeError: 如果other不是命令选项或命令节点, 则抛出此异常
        """
        if isinstance(other, Subcommand) or (isinstance(other, _Args) and other.slot):
            self.forks.append(other)
            self._hash = self._calc_hash()
            return self
        try:
            _args = handle_args(other)
            if _args.slot:
                self.forks.append(_args)
            else:
                self.args = _Args([*self.args.data, *_args.data])
                self.nargs = len(self.args.data)
            self._hash = self._calc_hash()
            return self
        except TypeError:
            raise TypeError(f"unsupported operand type(s) for +: 'Subcommand' and '{other.__class__.__name__}'") from None

    def __radd__(self, other: str):
        """与字符串连接, 生成 `Alconna` 对象

        Args:
            other (str): 字符串

        Returns:
            Alconna: Alconna 对象

        Raises:
            TypeError: 如果other不是字符串, 则抛出此异常
        """
        if isinstance(other, str):
            from .core import Alconna

            return Alconna(other, self)
        raise TypeError(f"unsupported operand type(s) for +: '{other.__class__.__name__}' and 'Subcommand'")

    add = __add__

    def separate(self, *separator: str) -> Self:
        """设置命令分隔符

        Args:
            *separator(str): 命令分隔符

        Returns:
            Self: 命令节点本身
        """
        self.separators = "".join(separator)
        self._hash = self._calc_hash()
        return self

    def __repr__(self):
        data = {}
        if self.args.data:
            data["args"] = self.args
        if self.default is not Empty:
            data["default"] = self.default
        return f"{self.__class__.__name__}({self.dest!r}, {', '.join(f'{k}={v!r}' for k, v in data.items())})"

    def _calc_hash(self):
        data = vars(self)
        data.pop("_hash", None)
        return hash(repr(data))

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.__hash__() == other.__hash__()


# class Help(Option):
#     def _calc_hash(self):
#         return hash("$ALCONNA_BUILTIN_OPTION_HELP")
#
#
# class Shortcut(Option):
#     def _calc_hash(self):
#         return hash("$ALCONNA_BUILTIN_OPTION_SHORTCUT")
#
#
# class Completion(Option):
#     def _calc_hash(self):
#         return hash("$ALCONNA_BUILTIN_OPTION_COMPLETION")


# SPECIAL_OPTIONS = (Help, Shortcut, Completion)
# """内置选项"""


@dc.dataclass(unsafe_hash=True)
class Metadata:
    """命令元数据"""

    description: str = dc.field(default="Unknown")
    "命令的描述"
    usage: str | None = dc.field(default=None)
    "命令的用法"
    example: str | None = dc.field(default=None)
    "命令的使用样例"
    author: str | None = dc.field(default=None)
    "命令的作者"
    version: str | None = dc.field(default=None)
    "命令的版本"
    extra: dict[str, Any] = dc.field(default_factory=dict, hash=False)
    "命令的自定义额外信息"


class OptionNames(TypedDict):
    help: set[str]
    """帮助选项的名称"""
    shortcut: set[str]
    """快捷选项的名称"""
    completion: set[str]
    """补全选项的名称"""


@dc.dataclass(unsafe_hash=True)
class Config:
    """命令配置"""
    disable_builtin_options: set[str] = dc.field(default_factory=lambda : {"shortcut"})
    """禁用的内置选项"""
    builtin_option_name: OptionNames = dc.field(
        default_factory=lambda: {
            "help": {"--help", "-h"},
            "shortcut": {"--shortcut", "-sct"},
            "completion": {"--comp", "-cp", "?"},
        }
    )
    """内置选项的名称"""
    enable_message_cache: Unset[bool] = dc.field(default=UNSET, metadata={"default": True})
    """默认是否启用消息缓存"""
    fuzzy_match: Unset[bool] = dc.field(default=UNSET, metadata={"default": False})
    "命令是否开启模糊匹配"
    fuzzy_threshold: Unset[float] = dc.field(default=UNSET, metadata={"default": 0.6})
    """模糊匹配阈值"""
    raise_exception: Unset[bool] = dc.field(default=UNSET, metadata={"default": False})
    "命令是否抛出异常"
    hide: Unset[bool] = dc.field(default=UNSET, metadata={"default": False})
    "命令是否对manager隐藏"
    hide_shortcut: Unset[bool] = dc.field(default=UNSET, metadata={"default": False})
    "命令的快捷指令是否在help信息中隐藏"
    keep_crlf: Unset[bool] = dc.field(default=UNSET, metadata={"default": False})
    "命令是否保留换行字符"
    compact: Unset[bool] = dc.field(default=UNSET, metadata={"default": False})
    "命令是否允许第一个参数紧随头部"
    strict: Unset[bool] = dc.field(default=UNSET, metadata={"default": True})
    "命令是否严格匹配，若为 False 则未知参数将作为名为 $extra 的参数"
    context_style: Unset[Literal["bracket", "parentheses"] | None] = dc.field(default=UNSET, metadata={"default": None})
    "命令上下文插值的风格，None 为关闭，bracket 为 {...}，parentheses 为 $(...)"
    extra: dict[str, Any] = dc.field(default_factory=dict, hash=False)
    "命令的自定义额外配置"

    @classmethod
    def merge(cls, self: Config, other: Config) -> Config:
        """合并命令配置

        Args:
            self (Config): 当前命令配置
            other (Config): 另一个命令配置

        Returns:
            Config: 合并后的命令配置
        """
        result = {}
        self_data = dc.asdict(self)
        other_data = dc.asdict(other)
        for fld in dc.fields(Config):
            if fld.name == "extra":
                result[fld.name] = {**other_data[fld.name], **self_data[fld.name]}
                continue
            if fld.name == "disable_builtin_options":
                default = fld.default_factory()  # type: ignore
                if self_data[fld.name] != default and other_data[fld.name] != default:
                    result[fld.name] = self_data[fld.name] | other_data[fld.name]
                else:
                    result[fld.name] = self_data[fld.name] if self_data[fld.name] != default else other_data[fld.name]
                continue
            if fld.name == "builtin_option_name":
                names = {}
                default = fld.default_factory()  # type: ignore
                for k in ("help", "shortcut", "completion"):
                    if self_data[fld.name][k] != default[k] and other_data[fld.name][k] != default[k]:
                        names[k] = self_data[fld.name][k] | other_data[fld.name][k]
                    else:
                        names[k] = self_data[fld.name][k] if self_data[fld.name][k] != default[k] else other_data[fld.name][k]
                result[fld.name] = names
                # result[fld.name] = {k: other_data[fld.name][k] | self_data[fld.name][k] for k in other_data[fld.name]}
                continue
            default = fld.metadata["default"]
            result[fld.name] = self_data[fld.name] if self_data[fld.name] is not UNSET else other_data[fld.name] if other_data[fld.name] is not UNSET else default
        return cls(**result)
