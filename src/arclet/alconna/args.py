from __future__ import annotations

from copy import deepcopy
import warnings
import dataclasses as dc
import re
import typing
from typing import Any, Callable, Generic, Literal, TypeVar, ClassVar, ForwardRef, Final, TYPE_CHECKING, get_origin, get_args
from typing_extensions import dataclass_transform, ParamSpec, Concatenate, TypeAlias

from nepattern import NONE, Pattern, RawStr, UnionPattern, parser
from tarina import Empty

from .i18n import i18n
from ._dcls import safe_dcls_kw, safe_field_kw
from .exceptions import InvalidArgs
from .utils import TAValue, parent_frame_namespace, merge_cls_and_parent_ns

_T = TypeVar("_T")


@dc.dataclass(**safe_dcls_kw(slots=True))
class Field(Generic[_T]):
    """标识参数单元字段"""

    default: _T | type[Empty] = dc.field(default=Empty)
    """参数单元的默认值"""
    default_factory: Callable[[], _T] | type[Empty] = dc.field(default=Empty)
    """参数单元的默认值工厂"""
    alias: str | None = dc.field(default=None)
    """参数单元默认值的别名"""
    completion: Callable[[], str | list[str] | None] | None = dc.field(default=None, repr=False)
    """参数单元的补全"""
    unmatch_tips: Callable[[Any], str] | None = dc.field(default=None, repr=False)
    """参数单元的错误提示"""
    missing_tips: Callable[[], str] | None = dc.field(default=None, repr=False)
    """参数单元的缺失提示"""
    notice: str | None = dc.field(default=None, compare=False, hash=False)
    """参数单元的注释"""
    seps: str = dc.field(default=" ", compare=False, hash=False)
    """参数单元使用的分隔符"""
    optional: bool = dc.field(default=False, compare=False, hash=False)
    hidden: bool = dc.field(default=False, compare=False, hash=False)
    # kw_only: bool = dc.field(default=False, compare=False, hash=False)
    multiple: bool | int | Literal["+", "*", "str"] = dc.field(default=False, compare=False, hash=False)
    # kw_sep: str = dc.field(default="=", compare=False, hash=False)
    wildcard: bool = dc.field(default=False, compare=False, hash=False)

    @property
    def display(self):
        """返回参数单元的显示值"""
        return self.alias or self.get_default()

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
    alias: str | None = None,
    completion: Callable[[], str | list[str] | None] | None = None,
    unmatch_tips: Callable[[Any], str] | None = None,
    missing_tips: Callable[[], str] | None = None,
    notice: str | None = None,
    seps: str = " ",
    multiple: bool | int | Literal["+", "*", "str"] = False,
    optional: bool = False,
    hidden: bool = False,
    wildcard: bool = False,
) -> "Any":
    return Field(default, default_factory, alias, completion, unmatch_tips, missing_tips, notice, seps, optional, hidden, multiple, wildcard)


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
        default = field if isinstance(field, Field) else Field(field)
        if isinstance(_value, UnionPattern) and _value.optional:
            default.default = None if default.default is Empty else default.default  # type: ignore
        if _value == NONE:
            raise InvalidArgs(i18n.require("args.value_error").format(target=name))
        self.type_ = _value  # type: ignore
        self.field = default

        if res := re.match(r"^(?P<name>.+?)#(?P<notice>[^;?/#]+)", name):
            self.field.notice = res["notice"]
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
                    warnings.warn(f"Arg(..., {k}={v}) is deprecated, use Field({k}={v}) instead", DeprecationWarning, stacklevel=2)
                    setattr(self.field, k, v)

    def __str__(self):
        if self.field.wildcard:
            v = n = f"...{self.name}"
        else:
            n, v = f"'{self.name_display}'", self.type_display
        return (n if n == v else f"{n}: {v}") + (f" = '{self.field.display}'" if self.field.display is not Empty else "")

    def __add__(self, other) -> "ArgsBuilder":
        if isinstance(other, Arg):
            return ArgsBuilder() << self << other
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
        if self.field.notice:
            n = f"{n}#{self.field.notice}"
        return n

    @property
    def type_display(self):
        if self.field.hidden:
            return "***"
        v = str(self.type_)
        # if self.field.kw_only:
        #     v = f"{self.field.kw_sep}{v}"
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


class _Args:
    __slots__ = ("optional_count", "origin", "data", "count")

    def __init__(self, args: list[Arg[Any]], origin: type[ArgsBase] | None = None):
        self.origin = origin
        self.optional_count = 0
        normal = []
        vars_positional: list[Arg[Any]] = []
        for arg in args:
            if arg.field.multiple is not False:
                # if arg.field.kw_only:
                #     for a in vars_positional:
                #         if arg.field.kw_sep in a.field.seps:
                #             raise InvalidArgs("varkey cannot use the same sep as varpos's Arg")
                #     vars_keyword.append(arg)
                # elif self.keyword_only:
                #     raise InvalidArgs(i18n.require("args.exclude_mutable_args"))
                vars_positional.append(arg)
            # elif arg.field.kw_only:
            #     # if self.vars_keyword:
            #     #     raise InvalidArgs(i18n.require("args.exclude_mutable_args"))
            #     keyword.append(arg)
            else:
                normal.append(arg)
            if arg.field.optional:
                self.optional_count += 1
            elif not arg.field.no_default:
                self.optional_count += 1
        normal.extend(vars_positional)
        self.data: list[Arg[Any]] = normal
        self.count = len(self.data)

    def __iter__(self):
        return iter(self.data)

    def __bool__(self):
        return bool(self.data)

    def __str__(self):
        return f"Args({', '.join([f'{arg}' for arg in self.data])})" if self.data else "Empty"

    def __len__(self):
        return self.count

    def __eq__(self, other):
        return self.data == other.data

    def __repr__(self):
        return repr(self.data)


_P = ParamSpec("_P")
_T1 = TypeVar("_T1", bound="ArgsBuilder")


def _arg_init_wrapper(func: Callable[_P, Field[_T]]) -> Callable[[_T1, str], Callable[Concatenate[TAValue[_T], _P], _T1]]:
    return lambda builder, name: lambda type_, *args, **kwargs: builder.__lshift__(Arg(name, type_, func(*args, **kwargs)))


wrapper = _arg_init_wrapper(Field)


class ArgsBuilder:
    def __init__(self, *origin: Arg):
        self._args = list(origin)

    def __lshift__(self, arg: Arg):
        self._args.append(arg)
        return self

    def __getattr__(self, item: str):
        return wrapper(self, item)

    def build(self):
        return _Args(self._args)

    def __iter__(self):
        return iter(self._args)

    def __len__(self):
        return len(self._args)


class __ArgsBuilderInstance:
    __slots__ = ()

    def __getattr__(self, item: str):
        return ArgsBuilder().__getattr__(item)

    def __lshift__(self, other):
        return ArgsBuilder() << other


Args: Final = __ArgsBuilderInstance()


def _is_classvar(a_type):
    # This test uses a typing internal class, but it's the best way to
    # test if this is a ClassVar.
    return (a_type is typing.ClassVar
            or (type(a_type) is typing._GenericAlias  # type: ignore
                and a_type.__origin__ is typing.ClassVar))


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
                data_args.extend(base_args.data)
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
                [(arg.name, arg.type_, arg.field.to_dc_field()) for arg in cls.__args_data__.data],
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
        return {arg.name: getattr(self, arg.name) for arg in self.__args_data__.data}

    @classmethod
    def load(cls, data: dict):
        for arg in cls.__args_data__.data:
            if arg.name not in data:
                if not arg.field.optional:
                    raise InvalidArgs(f"missing required argument: {arg.name}")
                data[arg.name] = None
        return cls(**data)


def handle_args(arg: Arg[Any] | list[Arg[Any]] | ArgsBuilder | type[ArgsBase] | _Args | None) -> _Args:
    if arg is None:
        return _Args([])
    if isinstance(arg, _Args):
        return arg
    if isinstance(arg, Arg):
        arg = [arg]
    if isinstance(arg, list):
        arg = ArgsBuilder(*arg)
    if isinstance(arg, ArgsBuilder):
        return arg.build()
    if issubclass(arg, ArgsBase):
        return arg.__args_data__
    raise TypeError(f"unsupported operand type(s) for +: 'Arg' and '{arg.__class__.__name__}'")


ARGS_PARAM: TypeAlias = "Arg | list[Arg] | ArgsBuilder | type[ArgsBase] | _Args"
