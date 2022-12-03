import re
import inspect
from functools import partial
from copy import deepcopy
from enum import Enum
from contextlib import suppress
from typing import Union, Tuple, Dict, Iterable, Callable, Any, Optional, Sequence, List, Set, TypeVar, Generic
from typing_extensions import get_origin
from dataclasses import dataclass, field as dc_field
from nepattern import BasePattern, Empty, AllParam, AnyOne, UnionArg, type_parser, pattern_map

from .config import config
from .exceptions import InvalidParam, NullMessage
from .typing import MultiVar, KeyWordVar

_T = TypeVar("_T")
TAValue = Union[BasePattern, AllParam.__class__, type, str]


class ArgFlag(str, Enum):
    OPTIONAL = '?'
    HIDDEN = "/"
    ANTI = "!"


@dataclass
class Field(Generic[_T]):
    """标识参数单元字段"""
    default: _T = dc_field(default=None)
    default_factory: Callable[[], _T] = dc_field(default=lambda: None)
    alias: Optional[str] = dc_field(default=None)
    completion: Optional[Callable[[], Union[str, List[str]]]] = dc_field(default=None)

    @property
    def display(self):
        return self.alias or self.default_gen

    @property
    def default_gen(self) -> _T:
        return self.default if self.default is not None else self.default_factory()


@dataclass(init=False, eq=True, unsafe_hash=True)
class Arg:
    name: str = dc_field(compare=True, hash=True)
    value: TAValue = dc_field(compare=False, hash=False)
    field: Field[_T] = dc_field(compare=False, hash=False)
    notice: Optional[str] = dc_field(compare=False, hash=False)
    flag: Set[ArgFlag] = dc_field(compare=False, hash=False)
    separators: Tuple[str, ...] = dc_field(compare=False, hash=False)

    def __init__(
        self,
        name: str,
        value: Optional[TAValue] = None,
        field: Optional[Union[Field[_T], _T]] = None,
        seps: Union[str, Iterable[str]] = " ",
        notice: Optional[str] = None,
        flags: Optional[List[ArgFlag]] = None,
    ):
        if not isinstance(name, str) or name.startswith('$'):
            raise InvalidParam(config.lang.args_name_error)
        if not name.strip():
            raise InvalidParam(config.lang.args_name_empty)
        self.name = name
        _value = type_parser(value or name)
        default = field if isinstance(field, Field) else Field(field)
        if isinstance(_value, UnionArg) and _value.optional:
            default.default = Empty if default.default is None else default.default
        if default.default in ("...", Ellipsis):
            default.default = Empty
        if _value is Empty:
            raise InvalidParam(config.lang.args_value_error.format(target=name))
        self.value = _value
        self.field = default
        self.notice = notice
        self.separators = (seps,) if isinstance(seps, str) else tuple(seps)
        flags = flags or []
        if res := re.match(r"^.+?#(?P<notice>[^;?!/#]+)", name):
            self.notice = res["notice"]
            self.name = name.replace(f"#{res['notice']}", "")
        if res := re.match(r"^.+?;(?P<flag>[?!/]+)", name):
            flags.extend(ArgFlag(c) for c in res["flag"])
            self.name = name.replace(f";{res['flag']}", "")
        self.flag = set(flags)

    def __repr__(self):
        return (n if (n := f"'{self.name}'") == (v := str(self.value)) else f"{n}: {v}") + (
            f" = '{self.field.display}'" if self.field.display is not None else ""
        )

    @property
    def optional(self):
        return ArgFlag.OPTIONAL in self.flag

    @property
    def hidden(self):
        return ArgFlag.HIDDEN in self.flag


class ArgsMeta(type):
    """Args 类的元类"""

    def __getattr__(self, name):
        class _Seminal:
            __getitem__ = partial(self.__class__.__getitem__, self, key=name)

        return _Seminal()

    def __getitem__(self, item, key: Optional[str] = None):
        data = item if isinstance(item, tuple) else (item,)
        if isinstance(data[0], Arg):
            return self(*data)
        return self(Arg(key, *data)) if key else self(Arg(*data))


class Args(metaclass=ArgsMeta):  # type: ignore
    argument: List[Arg]
    var_positional: Optional[str]
    var_keyword: Optional[str]
    keyword_only: List[str]
    optional_count: int

    @classmethod
    def from_string_list(cls, args: List[List[str]], custom_types: Dict) -> "Args":
        """
        从处理好的字符串列表中生成Args

        Examples:
            >>> Args.from_string_list([["foo", "str"], ["bar", "digit", "123"]], {"digit":int})
        """
        _args = cls()
        for arg in args:
            if (_le := len(arg)) == 0:
                raise NullMessage
            default = arg[2].strip(" ") if _le > 2 else None
            value = AllParam if arg[0].startswith("...") else (
                AnyOne if arg[0].startswith("..") else (arg[1].strip(" ") if _le > 1 else arg[0].lstrip(".-"))
            )
            name = arg[0].replace("...", "").replace("..", "")
            if value not in (AllParam, AnyOne):
                if custom_types and custom_types.get(value) and not inspect.isclass(custom_types[value]):
                    raise InvalidParam(config.lang.common_custom_type_error.format(target=custom_types[value]))
                with suppress(NameError, ValueError, TypeError):
                    if pattern_map.get(value, None):
                        value = pattern_map[value]
                        if default:
                            default = (get_origin(value.origin) or value.origin)(default)
                    else:
                        value = eval(value, custom_types)  # type: ignore
                        if default:
                            default = value(default)
            _args.add(name, value=value, default=default)
        return _args

    @classmethod
    def from_callable(cls, target: Callable):
        """
        从可调用函数中构造Args

        Examples:
            >>> def test(a: str, b: int, c: float = 0.0, *, d: str, e: int = 0, f: float = 0.0):
            ...     pass
            >>> Args.from_callable(test)

        """
        sig = inspect.signature(target)
        _args = cls()
        method = False
        for param in sig.parameters.values():
            name = param.name
            if name in ["self", "cls"]:
                method = True
                continue
            anno = param.annotation
            de = param.default
            if anno == inspect.Signature.empty:
                anno = type(de) if de not in (inspect.Signature.empty, None) else AnyOne
            if de is inspect.Signature.empty:
                de = None
            elif de is None:
                de = inspect.Signature.empty
            if param.kind == param.KEYWORD_ONLY:
                if anno == bool:
                    anno = BasePattern(f"(?:-*no)?-*{name}", 3, bool, lambda _, x: not x.lstrip("-").startswith('no'))
                else:
                    _args.add(f"_key_{name}", value=f"-*{name}")
                _args.keyword_only.append(name)
            if param.kind == param.VAR_POSITIONAL:
                anno = MultiVar(anno, "*")
            if param.kind == param.VAR_KEYWORD:
                anno = MultiVar(KeyWordVar(anno), "*")
            _args.add(name, value=anno, default=de)
        return _args, method

    def __init__(
        self,
        *args: Arg,
        separators: Optional[Union[str, Iterable[str]]] = None,
        **kwargs: TAValue
    ):
        """
        构造一个Args

        Args:
            args: 应传入 slice|tuple, 代表key、value、default
            extra: 额外类型检查的策略
            separator: 参数分隔符
            kwargs: 其他参数
        """
        self._visit = set()
        self.var_positional = None
        self.var_keyword = None
        self.keyword_only = []
        self.optional_count = 0
        self.argument = list(args)
        self.argument.extend(Arg(k, type_parser(v), Field()) for k, v in kwargs.items())
        self.__check_vars__()
        if separators is not None:
            self.separate(*((separators,) if isinstance(separators, str) else tuple(separators)))

    __slots__ = "var_positional", "var_keyword", "argument", "optional_count", "keyword_only", "_visit"

    def add(self, name: str, *, value: Any, default: Any = None, flags: Optional[Iterable[ArgFlag]] = None):
        """
        添加一个参数
        """
        if next(filter(lambda x: x.name == name, self.argument), False):
            return self
        self.argument.append(Arg(name, value, default, flags=flags))
        self.__check_vars__()
        return self

    def default(self, **kwargs):
        """设置参数的默认值"""
        for arg in self.argument:
            if v := (kwargs.get(arg.name)):
                if isinstance(v, Field):
                    arg.field = v
                else:
                    arg.field.default = v
        return self

    def separate(self, *separator: str):
        """设置参数的分隔符"""
        for arg in self.argument:
            arg.separators = separator
        return self

    def __check_vars__(self):
        _visit = set()
        _tmp = []
        for arg in self.argument:
            if arg.name not in _visit:
                _visit.add(arg.name)
                _tmp.append(arg)
        self.argument.clear()
        self.argument.extend(_tmp)
        del _tmp
        for arg in self.argument:
            if arg.name in self._visit:
                continue
            self._visit.add(arg.name)
            _limit = False
            if ArgFlag.ANTI in arg.flag and arg.value not in (AnyOne, AllParam):
                arg.value = deepcopy(arg.value).reverse()
            if isinstance(arg.value, MultiVar) and not _limit:
                if isinstance(arg.value.base, KeyWordVar):
                    if self.var_keyword:
                        raise InvalidParam(config.lang.args_duplicate_kwargs)
                    self.var_keyword = arg.name
                elif self.var_positional:
                    raise InvalidParam(config.lang.args_duplicate_varargs)
                else:
                    self.var_positional = arg.name
                _limit = True
            if isinstance(arg.value, KeyWordVar):
                if self.var_keyword or self.var_positional:
                    raise InvalidParam(config.lang.args_exclude_mutable_args)
                self.keyword_only.append(arg.name)
            if ArgFlag.OPTIONAL in arg.flag:
                if self.var_keyword or self.var_positional:
                    raise InvalidParam(config.lang.args_exclude_mutable_args)
                self.optional_count += 1

    def __len__(self):
        return len(self.argument)

    def __getitem__(self, item) -> Union["Args", Arg]:
        if isinstance(item, str) and (res := next(filter(lambda x: x.name == item, self.argument), None)):
            return res
        data = item if isinstance(item, tuple) else (item,)
        if isinstance(data[0], Arg):
            self.argument.extend(data)
        else:
            self.argument.append(Arg(*data))
        self.__check_vars__()
        return self

    def __merge__(self, other) -> "Args":
        if isinstance(other, Args):
            self.argument.extend(other.argument)
            self.__check_vars__()
            del other
        elif isinstance(other, Sequence):
            self.__getitem__(tuple(other))
        return self

    def __add__(self, other) -> "Args":
        return self.__merge__(other)

    def __iadd__(self, other) -> "Args":
        return self.__merge__(other)

    def __lshift__(self, other) -> "Args":
        return self.__merge__(other)

    def __truediv__(self, other):
        self.separate(*other if isinstance(other, (list, tuple, set)) else other)
        return self

    def __eq__(self, other):
        return self.argument == other.argument

    def __repr__(self):
        return f"Args({', '.join(f'{arg}' for arg in self.argument)})" if self.argument else "Empty"

    @property
    def empty(self) -> bool:
        return not self.argument
