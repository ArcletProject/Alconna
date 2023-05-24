"""Alconna 的基础内容相关"""
from __future__ import annotations

import dataclasses as dc
import re
import sys
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from functools import partial, reduce
from typing import Any, Callable, Generic, Iterable, Sequence, TypeVar, Union

from nepattern import AllParam, AnyOne, BasePattern, RawStr, UnionPattern, all_patterns, type_parser
from tarina import Empty, lang, get_signature
from typing_extensions import Self

from .typing import TDC

_repr_ = lambda self: "(" + " ".join([f"{k}={getattr(self, k, ...)!r}" for k in self.__slots__]) + ")"


@dataclass(init=False, eq=True)
class OptionResult:
    __slots__ = ("value", "args")
    __repr__ = _repr_
    def __init__(self, value=Ellipsis, args=None):
        self.value = value
        self.args = args or {}


@dataclass(init=False, eq=True)
class SubcommandResult:
    __slots__ = ("value", "args", "options", "subcommands")
    __repr__ = _repr_
    def __init__(self, value=Ellipsis, args=None, options=None, subcommands=None):
        self.value = value
        self.args = args or {}
        self.options = options or {}
        self.subcommands = subcommands or {}


@dataclass(init=False, eq=True)
class HeadResult:
    __slots__ = ("origin", "result", "matched", "groups")
    __repr__ = _repr_
    def __init__(self, origin=None, result=None, matched=False, groups=None, fixes=None):
        self.origin = origin
        self.result = result
        self.matched = matched
        self.groups = groups or {}
        if fixes:
            self.groups.update(
                {k: v.exec(self.groups[k]).value for k, v in fixes.items() if k in self.groups}  # noqa
            )


class ParamsUnmatched(Exception):
    """一个 text 没有被任何参数匹配成功"""


class ArgumentMissing(Exception):
    """组件内的 Args 参数未能解析到任何内容"""


class InvalidParam(Exception):
    """构造 alconna 时某个传入的参数不正确"""


class NullMessage(Exception):
    """传入了无法解析的消息"""



class CommandNode:
    """命令节点基类, 规定基础组件所含属性"""

    name: str
    """命令节点名称"""
    dest: str
    """命令节点目标名称"""
    default: Any
    """命令节点默认值"""
    args: Args
    """命令节点参数"""
    separators: tuple[str, ...]
    """命令节点分隔符"""

    def __init__(
        self, name: str, args: Arg | Args | None = None,
        dest: str | None = None, default: Any = None,
        separators: str | Sequence[str] | set[str] | None = None,
    ):
        """
        初始化命令节点

        Args:
            name (str): 命令节点名称
            args (Arg | Args | None, optional): 命令节点参数
            dest (str | None, optional): 命令节点目标名称
            separators (str | Sequence[str] | Set[str] | None, optional): 命令分隔符
        """
        if not name:
            raise InvalidParam(lang.require("common", "name_empty"))
        self.name = name
        self.args = Args() + args
        self.default = default
        self.separators = (' ',) if separators is None else (
            (separators,) if isinstance(separators, str) else tuple(separators)
        )
        self.nargs = len(self.args.argument)
        self.dest = (dest or self.name).lstrip('-')
        self._hash = self._calc_hash()

    nargs: int
    _hash: int

    def separate(self, *separator: str) -> Self:
        """设置命令分隔符

        Args:
            *separator(str): 命令分隔符

        Returns:
            Self: 命令节点本身
        """
        self.separators = separator
        self._hash = self._calc_hash()
        return self

    def __repr__(self):
        data = {}
        if not self.args.empty:
            data["args"] = self.args
        if self.default is not None:
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


class Option(CommandNode):
    """命令选项

    相比命令节点, 命令选项可以设置别名, 优先级, 允许名称与后随参数之间无分隔符
    """

    default: OptionResult | None
    """命令选项默认值"""
    aliases: frozenset[str]
    """命令选项别名"""
    compact: bool
    "是否允许名称与后随参数之间无分隔符"

    def __init__(
        self,
        name: str, args: Arg | Args | None = None, alias: Iterable[str] | None = None,
        dest: str | None = None, default: Any = None,
        separators: str | Sequence[str] | set[str] | None = None,
        compact: bool = False,
    ):
        """初始化命令选项

        Args:
            name (str): 命令选项名称
            args (Arg | Args | None, optional): 命令选项参数
            alias (Iterable[str] | None, optional): 命令选项别名
            dest (str | None, optional): 命令选项目标名称
            default (Any, optional): 命令选项默认值
            separators (str | Sequence[str] | Set[str] | None, optional): 命令分隔符
            compact (bool, optional): 是否允许名称与后随参数之间无分隔符
        """
        aliases = list(alias or [])
        _name = name.split(" ")[-1]
        if "|" in _name:
            _aliases = _name.split("|")
            _aliases.sort(key=len, reverse=True)
            name = name.replace(_name, _aliases[0])
            _name = _aliases[0]
            aliases.extend(_aliases[1:])
        aliases.insert(0, _name)
        self.aliases = frozenset(aliases)
        self.compact = compact
        default = (
            None if default is None else
            default if isinstance(default, OptionResult) else OptionResult(default)
        )
        super().__init__(name, args, dest, default, separators)
        if self.separators == ("",):
            self.compact = True
            self.separators = (" ",)


class Subcommand(CommandNode):
    """子命令, 次于主命令

    与命令节点不同, 子命令可以包含多个命令选项与相对于自己的子命令
    """
    default: SubcommandResult | None
    """子命令默认值"""
    options: list[Option | Subcommand]
    """子命令包含的选项与子命令"""

    def __init__(
        self,
        name: str,
        *args: Args | Arg | Option | Subcommand | list[Option | Subcommand],
        dest: str | None = None, default: Any = None,
        separators: str | Sequence[str] | set[str] | None = None,
    ):
        """初始化子命令

        Args:
            name (str): 子命令名称
            *args (Args | Arg | Option | Subcommand | list[Option | Subcommand]): 参数, 选项或子命令
            dest (str | None, optional): 子命令选项目标名称
            default (Any, optional): 子命令默认值
            separators (str | Sequence[str] | Set[str] | None, optional): 子命令分隔符
        """
        self.options = [i for i in args if isinstance(i, (Option, Subcommand))]
        for li in filter(lambda x: isinstance(x, list), args):
            self.options.extend(li)
        default = (
            None if default is None else
            default if isinstance(default, SubcommandResult) else SubcommandResult(default)
        )
        super().__init__(
            name,
            reduce(lambda x, y: x + y, [Args()] + [i for i in args if isinstance(i, (Arg, Args))]),  # type: ignore
            dest, default, separators
        )


def safe_dcls_kw(**kwargs):
    if sys.version_info < (3, 10):  # pragma: no cover
        kwargs.pop('slots')
    return kwargs


_T = TypeVar("_T")
TAValue = Union[BasePattern, AllParam.__class__, type, str]
STRING = all_patterns()[str]


class ArgFlag(str, Enum):
    """标识参数单元的特殊属性"""
    OPTIONAL = '?'
    HIDDEN = "/"
    ANTI = "!"


@dc.dataclass(**safe_dcls_kw(slots=True))
class Field(Generic[_T]):
    """标识参数单元字段"""

    default: _T | None = dc.field(default=None)
    """参数单元的默认值"""
    alias: str | None = dc.field(default=None)
    """参数单元默认值的别名"""
    completion: Callable[[], str | list[str]] | None = dc.field(default=None)
    """参数单元的补全"""

    @property
    def display(self):
        """返回参数单元的显示值"""
        return self.alias or self.default


@dc.dataclass(**safe_dcls_kw(init=False, eq=True, unsafe_hash=True, slots=True))
class Arg:
    """参数单元"""

    name: str = dc.field(compare=True, hash=True)
    """参数单元的名称"""
    value: BasePattern = dc.field(compare=False, hash=True)
    """参数单元的值"""
    field: Field[Any] = dc.field(compare=False, hash=False)
    """参数单元的字段"""
    notice: str | None = dc.field(compare=False, hash=False)
    """参数单元的注释"""
    flag: set[ArgFlag] = dc.field(compare=False, hash=False)
    """参数单元的标识"""
    separators: tuple[str, ...] = dc.field(compare=False, hash=False)
    """参数单元使用的分隔符"""
    optional: bool = dc.field(compare=False, hash=False)
    hidden: bool = dc.field(compare=False, hash=False)
    anonymous: bool = dc.field(compare=False, hash=False)

    def __init__(
        self,
        name: str,
        value: TAValue | None = None,
        field: Field[_T] | _T | None = None,
        seps: str | Iterable[str] = " ",
        notice: str | None = None,
        flags: list[ArgFlag] | None = None,
    ):
        """构造参数单元

        Args:
            name (str): 参数单元的名称
            value (TAValue, optional): 参数单元的值. Defaults to None.
            field (Field[_T], optional): 参数单元的字段. Defaults to None.
            seps (str | Iterable[str], optional): 参数单元使用的分隔符. Defaults to " ".
            notice (str, optional): 参数单元的注释. Defaults to None.
            flags (list[ArgFlag], optional): 参数单元的标识. Defaults to None.
        """
        if not isinstance(name, str) or name.startswith('$'):
            raise InvalidParam(lang.require("args", "name_error"))
        if not name.strip():
            raise InvalidParam(lang.require("args", "name_empty"))
        self.name = name
        _value = type_parser(value or RawStr(name))
        default = field if isinstance(field, Field) else Field(field)
        if isinstance(_value, UnionPattern) and _value.optional:
            default.default = Empty if default.default is None else default.default
        if default.default == "...":
            default.default = Empty
        if _value is Empty:
            raise InvalidParam(lang.require("args", "value_error").format(target=name))
        self.value = _value
        self.field = default
        self.notice = notice
        self.separators = (seps,) if isinstance(seps, str) else tuple(seps)
        flags = flags or []
        if res := re.match(r"^(?P<name>.+?)#(?P<notice>[^;?!/#]+)", name):
            self.notice = res["notice"]
            self.name = res["name"]
        if res := re.match(r"^(?P<name>.+?)(;)?(?P<flag>[?!/]+)", self.name):
            flags.extend(ArgFlag(c) for c in res["flag"])
            self.name = res["name"]
        self.flag = set(flags)
        self.optional = ArgFlag.OPTIONAL in self.flag
        self.hidden = ArgFlag.HIDDEN in self.flag
        self.anonymous = self.name.startswith("_key_")
        if ArgFlag.ANTI in self.flag and self.value not in (AnyOne, AllParam):
            self.value = deepcopy(self.value).reverse()

    def __repr__(self):
        n, v = f"'{self.name}'", str(self.value)
        return (n if n == v else f"{n}: {v}") + (f" = '{self.field.display}'" if self.field.display is not None else "")


class ArgsMeta(type):
    """`Args` 类的元类"""

    def __getattr__(self, name: str):
        return type("_S", (), {"__getitem__": partial(self.__class__.__getitem__, self, key=name), "__call__": None})()

    def __getitem__(self, item: Union[Arg, tuple[Arg, ...], str, tuple[Any, ...]], key: str | None = None):
        """构造参数集合

        Args:
            item (Union[Arg, tuple[Arg, ...], str, Any]): 参数单元或参数单元组或构建参数单元的值
            key (str, optional): 参数单元的名称. Defaults to None.

        Returns:
            Args: 参数集合
        """
        data: tuple[Arg, ...] | tuple[Any, ...] = item if isinstance(item, tuple) else (item,)
        if isinstance(data[0], Arg):
            return self(*data)
        return self(Arg(key, *data)) if key else self(Arg(*data))  # type: ignore


class Args(metaclass=ArgsMeta):
    """参数集合

    用于代表命令节点需求的一系列参数

    一般而言, 使用特殊方法 `__getitem__` 来构造参数集合, 例如:

        >>> Args["name", str]["age", int]
        Args('name': str, 'age': int)

    也可以使用特殊方法 `__getattr__` 来构造参数集合, 例如:

        >>> Args.name[str]
        Args('name': str)
    """
    argument: list[Arg]
    """参数单元组"""
    optional_count: int
    """可选参数的数量"""

    def __init__(self, *args: Arg, separators: str | Iterable[str] | None = None):
        """
        构造一个 `Args`

        Args:
            *args (Arg): 参数单元
            separators (str | Iterable[str] | None, optional): 可选的为所有参数单元指定分隔符
        """
        self._visit = set()
        self.optional_count = 0
        self.argument = list(args)
        self.__check_vars__()
        if separators is not None:
            self.separate(*((separators,) if isinstance(separators, str) else tuple(separators)))

    __slots__ = "argument", "optional_count", "_visit"

    def separate(self, *separator: str) -> Self:
        """设置参数的分隔符

        Args:
            *separator (str): 分隔符

        Returns:
            Self: 参数集合自身
        """
        for arg in self.argument:
            arg.separators = separator
        return self

    def __check_vars__(self):
        """检查当前所有参数单元

        Raises:
            InvalidParam: 当检查到参数单元不符合要求时
        """
        _tmp = []
        _visit = set()
        for arg in self.argument:
            if arg.name in _visit:
                continue
            _tmp.append(arg)
            _visit.add(arg.name)
            if arg.name in self._visit:
                continue
            self._visit.add(arg.name)
            if ArgFlag.OPTIONAL in arg.flag:
                self.optional_count += 1
        self.argument.clear()
        self.argument.extend(_tmp)
        del _tmp
        del _visit

    def __len__(self):
        return len(self.argument)

    def __getitem__(self, item: Union[Arg, tuple[Arg, ...], str, tuple[Any, ...]]) -> Self | Arg:
        """获取或添加一个参数单元

        Args:
            item (Union[Arg, tuple[Arg, ...], str, Any]): 参数单元或参数单元名称或参数单元值

        Returns:
            Self | Arg: 参数集合自身或需要的参数单元
        """
        if isinstance(item, str) and (res := next(filter(lambda x: x.name == item, self.argument), None)):
            return res
        data: tuple[Arg, ...] | tuple[Any, ...] = item if isinstance(item, tuple) else (item,)
        if isinstance(data[0], Arg):
            self.argument.extend(data)  # type: ignore
        else:
            self.argument.append(Arg(*data))  # type: ignore
        self.__check_vars__()
        return self

    def __merge__(self, other: Args | Arg | Sequence | None) -> Self:
        """合并另一个参数集合

        Args:
            other (Args | Arg | Sequence): 另一个参数集合

        Returns:
            Self: 参数集合自身
        """
        if isinstance(other, Args):
            self.argument.extend(other.argument)
            self.__check_vars__()
            del other
        elif isinstance(other, Arg):
            self.argument.append(other)
            self.__check_vars__()
        elif isinstance(other, Sequence):
            self.__getitem__(tuple(other))
        return self

    __add__ = __merge__
    __iadd__ = __merge__
    __lshift__ = __merge__
    __iter__ = lambda self: iter(self.argument)

    def __truediv__(self, other) -> Self:
        self.separate(*other if isinstance(other, (list, tuple, set)) else other)
        return self

    def __eq__(self, other):
        return self.argument == other.argument

    def __repr__(self):
        return (
            f"Args({', '.join([f'{arg}' for arg in self.argument if not arg.anonymous])})"
            if self.argument else "Empty"
        )

    @property
    def empty(self) -> bool:
        """判断当前参数集合是否为空"""
        return not self.argument


class Arparma(Generic[TDC]):
    """承载解析结果与操作数据的接口类

    Attributes:
        origin (TDC): 原始数据
        matched (bool): 是否匹配
        header_match (HeadResult): 命令头匹配结果
        error_info (type[BaseException] | BaseException | str): 错误信息
        error_data (list[str | Any]): 错误数据
        main_args (dict[str, Any]): 主参数匹配结果
        other_args (dict[str, Any]): 其他参数匹配结果
        options (dict[str, OptionResult]): 选项匹配结果
        subcommands (dict[str, SubcommandResult]): 子命令匹配结果
    """
    header_match: HeadResult
    options: dict[str, OptionResult]
    subcommands: dict[str, SubcommandResult]

    def __init__(
        self,
        origin: TDC,
        matched: bool = False,
        header_match: HeadResult | None = None,
        error_info: type[BaseException] | BaseException | str = '',
        error_data: list[str | Any] | None = None,
        main_args: dict[str, Any] | None = None,
        options: dict[str, OptionResult] | None = None,
        subcommands: dict[str, SubcommandResult] | None = None,
    ):
        """初始化 `Arparma`
        Args:
            origin (TDC): 原始数据
            matched (bool, optional): 是否匹配
            header_match (HeadResult | None, optional): 命令头匹配结果
            error_info (type[BaseException] | BaseException | str, optional): 错误信息
            error_data (list[str | Any] | None, optional): 错误数据
            main_args (dict[str, Any] | None, optional): 主参数匹配结果
            options (dict[str, OptionResult] | None, optional): 选项匹配结果
            subcommands (dict[str, SubcommandResult] | None, optional): 子命令匹配结果
        """
        self.origin = origin
        self.matched = matched
        self.header_match = header_match or HeadResult()
        self.error_info = error_info
        self.error_data = error_data or []
        self.main_args = main_args or {}
        self.other_args = {}
        self.options = options or {}
        self.subcommands = subcommands or {}

    def _clr(self):
        ks = list(self.__dict__.keys())
        for k in ks:
            delattr(self, k)

    @property
    def head_matched(self):
        """返回命令头是否匹配"""
        return self.header_match.matched

    @property
    def non_component(self) -> bool:
        """返回是否没有解析到任何组件"""
        return not self.subcommands and not self.options

    @property
    def components(self) -> dict[str, OptionResult | SubcommandResult]:
        """返回解析到的组件"""
        return {**self.options, **self.subcommands}

    @property
    def all_matched_args(self) -> dict[str, Any]:
        """返回 Alconna 中所有 Args 解析到的值"""
        return {**self.main_args, **self.other_args}

    def _unpack_opts(self, _data):
        for _v in _data.values():
            self.other_args = {**self.other_args, **_v.args}

    def _unpack_subs(self, _data):
        for _v in _data.values():
            self.other_args = {**self.other_args, **_v.args}
            if _v.options:
                self._unpack_opts(_v.options)
            if _v.subcommands:
                self._unpack_subs(_v.subcommands)

    def unpack(self) -> None:
        """处理 `Arparma` 中的数据"""
        self._unpack_opts(self.options)
        self._unpack_subs(self.subcommands)

    def call(self, target: Callable[..., _T], **additional) -> _T:
        """依据 `Arparma` 中的数据调用函数

        Args:
            target (Callable[..., T]): 要调用的函数
            **additional (Any): 附加参数
        Returns:
            T: 函数返回值
        Raises:
            RuntimeError: 如果 Arparma 未匹配, 则抛出 RuntimeError
        """
        if self.matched:
            names = {p.name for p in get_signature(target)}
            return target(**{k: v for k, v in {**self.all_matched_args, **additional}.items() if k in names})
        raise RuntimeError

    def fail(self, exc: type[BaseException] | BaseException | str):
        """生成一个失败的 `Arparma`"""
        return Arparma(self.origin, False, self.header_match, error_info=exc)

    def __repr__(self):
        if self.error_info:
            attrs = ((s, getattr(self, s, None)) for s in ("matched", "header_match", "error_data", "error_info"))
            return ", ".join([f"{a}={v}" for a, v in attrs if v is not None])
        else:
            attrs = {
                "matched": self.matched, "header_match": self.header_match,
                "options": self.options, "subcommands": self.subcommands,
                "main_args": self.main_args, "other_args": self.other_args
            }
            return ", ".join([f"{a}={v}" for a, v in attrs.items() if v])
