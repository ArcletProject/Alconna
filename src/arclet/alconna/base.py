"""Alconna 的基础内容相关"""

import re
import inspect
from functools import partial
from copy import deepcopy
from enum import Enum
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Union, Tuple, Dict, Iterable, Callable, Any, Optional, Sequence, List, Literal, TypedDict, \
    Set, FrozenSet

from .exceptions import InvalidParam, NullMessage
from .typing import BasePattern, Empty, AllParam, AnyOne, MultiArg, UnionArg, args_type_parser, pattern_map
from .config import config
from .components.action import ArgAction

TAValue = Union[BasePattern, AllParam.__class__, type]
TADefault = Union[Any, object, Empty]


class ArgFlag(str, Enum):
    """
    参数标记
    """
    VAR_POSITIONAL = "S"
    VAR_KEYWORD = "W"
    OPTIONAL = 'O'
    KWONLY = 'K'
    HIDDEN = "H"
    FORCE = "F"
    ANTI = "A"


class ArgUnit(TypedDict):
    """参数单元 """
    value: TAValue
    """参数值"""
    default: TADefault
    """默认值"""
    notice: Optional[str]
    """参数提示"""
    optional: bool
    """是否可选"""
    kwonly: bool
    """是否键值对参数"""
    hidden: bool
    """是否隐藏类型参数"""


class ArgsMeta(type):
    """Args 类的元类"""

    def __getattr__(self, name):
        class _Seminal:
            __class_getitem__ = partial(self.__class__.__getitem__, self, key=name)
        return _Seminal

    def __getitem__(self, item, key: Optional[str] = None):
        if isinstance(item, slice) or isinstance(item, tuple) and list(filter(lambda x: isinstance(x, slice), item)):
            raise InvalidParam(f"{self.__name__} 现在不支持切片; 应从 Args[a:b:c, x:y:z] 变为 Args[a,b,c][x,y,z]")
        if not isinstance(item, tuple):
            return self(args=[(key, item)]) if key else self(args=[(str(item), item)])
        arg = list(filter(lambda x: not isinstance(x, slice), item))
        if key:
            return self(args=[(key, *arg[:2])])
        return self(args=[arg[:3]])


class Args(metaclass=ArgsMeta):  # type: ignore
    """
    对命令参数的封装

    Attributes:
        argument: 存放参数内容的容器
    """
    extra: Literal["allow", "ignore", "reject"]
    argument: Dict[str, ArgUnit]
    var_positional: Optional[str]
    var_keyword: Optional[str]
    keyword_only: List[str]
    optional_count: int
    separators: Set[str]

    @classmethod
    def from_string_list(cls, args: List[List[str]], custom_types: Dict) -> "Args":
        """
        从处理好的字符串列表中生成Args

        Args:
            args: 字符串列表
            custom_types: 自定义的类型

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
                            default = value.origin(default)
                    else:
                        value = eval(value, custom_types)  # type: ignore
                        if default:
                            default = value(default)
            _args.add_argument(name, value=value, default=default)
        return _args

    @classmethod
    def from_callable(cls, target: Callable, extra: Literal["allow", "ignore", "reject"] = "allow"):
        """
        从可调用函数中构造Args

        Args:
            target: 可调用函数
            extra: 额外类型检查的策略

        Examples:
            >>> def test(a: str, b: int, c: float = 0.0, *, d: str, e: int = 0, f: float = 0.0):
            ...     pass
            >>> Args.from_callable(test)

        """
        sig = inspect.signature(target)
        _args = cls(extra=extra)
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
                    anno = BasePattern(f"(?:-*no)?-*{name}", 3, bool, lambda x: not x.lstrip("-").startswith('no'))
                else:
                    _args.add_argument(f"${name}_key", value=f"-*{name}")
                _args.keyword_only.append(name)
            if param.kind == param.VAR_POSITIONAL:
                name += ";S"
            if param.kind == param.VAR_KEYWORD:
                name += ";W"
            _args.add_argument(name, value=anno, default=de)
        return _args, method

    def __init__(
            self,
            args: Optional[Iterable[Sequence]] = None,
            extra: Literal["allow", "ignore", "reject"] = "allow",
            separators: Union[str, Iterable[str]] = " ",
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
        self.extra = extra
        self.var_positional = None
        self.var_keyword = None
        self.keyword_only = []
        self.optional_count = 0
        self.separators = {separators} if isinstance(separators, str) else set(separators)
        self.argument = {  # type: ignore
            k: {"value": args_type_parser(v), "default": None, 'notice': None,
                'optional': False, 'hidden': False, 'kwonly': False}
            for k, v in kwargs.items()
        }
        for arg in (args or []):
            self.__check_var__(arg)

    __slots__ = "extra", "var_positional", "var_keyword", "argument", "optional_count", "separators", "keyword_only"

    def add_argument(self, name: str, *, value: Any, default: Any = None, flags: Optional[Iterable[ArgFlag]] = None):
        """
        添加一个参数
        """
        if name in self.argument:
            return self
        if flags:
            name += ";" + "".join(flags)
        self.__check_var__([name, value, default])
        return self

    def default(self, **kwargs: TADefault):
        """设置参数的默认值"""
        for k, v in kwargs.items():
            if self.argument.get(k):
                self.argument[k]['default'] = v
        return self

    def separate(self, *separator: str):
        """设置参数的分隔符"""
        self.separators = set(separator)
        return self

    def __check_var__(self, val: Sequence):
        if not val:
            raise InvalidParam(config.lang.args_name_empty)
        name, value, default = val[0], val[1] if len(val) > 1 else val[0], val[2] if len(val) > 2 else None
        if not isinstance(name, str):
            raise InvalidParam(config.lang.args_name_error)
        if not name.strip():
            raise InvalidParam(config.lang.args_name_empty)
        _value = args_type_parser(value, self.extra)
        if isinstance(_value, UnionArg) and _value.optional:
            default = Empty if default is None else default
        if default in ("...", Ellipsis):
            default = Empty
        if _value is Empty:
            raise InvalidParam(config.lang.args_value_error.format(target=name))
        slot: ArgUnit = {
            'value': _value, 'default': default, 'notice': None,
            'optional': False, 'hidden': False, 'kwonly': False
        }
        if res := re.match(r"^.+?#(?P<notice>[^;#]+)", name):
            slot['notice'] = res.group("notice")
            name = name.replace(f"#{res.group('notice')}", "")
        if res := re.match(r"^.+?;(?P<flag>[^;#]+)", name):
            flags = res.group("flag")
            name = name.replace(f";{res.group('flag')}", "")
            _limit = False
            for flag in flags:
                if flag == ArgFlag.FORCE and not _limit:
                    self.__handle_force__(slot, value)
                    _limit = True
                if flag == ArgFlag.ANTI and not _limit:
                    if slot['value'] not in (AnyOne, AllParam):
                        slot['value'] = deepcopy(_value).reverse()  # type: ignore
                    _limit = True
                if flag == ArgFlag.VAR_KEYWORD and not _limit:
                    if self.var_keyword:
                        raise InvalidParam(config.lang.args_duplicate_kwargs)
                    if _value is not AllParam:
                        slot['value'] = MultiArg(_value, flag='kwargs')  # type: ignore
                        self.var_keyword = name
                    _limit = True
                if flag == ArgFlag.VAR_POSITIONAL and not _limit:
                    if self.var_positional:
                        raise InvalidParam(config.lang.args_duplicate_varargs)
                    if _value is not AllParam:
                        slot['value'] = MultiArg(_value)  # type: ignore
                        self.var_positional = name
                if flag.isdigit() and not _limit:
                    if self.var_positional:
                        raise InvalidParam(config.lang.args_duplicate_varargs)
                    if _value is not AllParam:
                        slot['value'] = MultiArg(_value, length=int(flag))  # type: ignore
                        self.var_positional = name
                if flag == ArgFlag.OPTIONAL:
                    if self.var_keyword or self.var_positional:
                        raise InvalidParam(config.lang.args_exclude_mutable_args)
                    slot['optional'] = True
                    self.optional_count += 1
                if flag == ArgFlag.HIDDEN:
                    slot['hidden'] = True
                if flag == ArgFlag.KWONLY:
                    if self.var_keyword or self.var_positional:
                        raise InvalidParam(config.lang.args_exclude_mutable_args)
                    slot['kwonly'] = True
        self.argument[name] = slot

    @staticmethod
    def __handle_force__(slot: ArgUnit, value):
        slot['value'] = (BasePattern(value, alias=f"\'{value}\'") if isinstance(value, str) else BasePattern.of(value))

    def __len__(self):
        return len(self.argument)

    def __setitem__(self, key, value):
        return self.__setattr__(key, value)

    def __setattr__(self, key, value):
        if key in self.__slots__:
            super().__setattr__(key, value)
        elif isinstance(value, Sequence):
            values = list(value)
            self.__check_var__([key, values[0], values[1]])
        else:
            self.__check_var__([key, value])
        return self

    def __getitem__(self, item) -> Union["Args", Tuple[TAValue, TADefault]]:
        if isinstance(item, str) and self.argument.get(item):
            return self.argument[item]['value'], self.argument[item]['default']
        if isinstance(item, slice) or isinstance(item, tuple) and list(filter(lambda x: isinstance(x, slice), item)):
            raise InvalidParam(f"{self.__name__} 现在不支持切片; 应从 Args[a:b:c, x:y:z] 变为 Args[a,b,c][x,y,z]")
        if not isinstance(item, tuple):
            self.__check_var__([str(item), item])
        else:
            arg = list(filter(lambda x: not isinstance(x, slice), item))
            self.__check_var__(arg[:3])
        return self

    def __merge__(self, other) -> "Args":
        if isinstance(other, Args):
            self.argument.update(other.argument)
            del other
        elif isinstance(other, Sequence):
            self.__check_var__(other)
        return self

    def __add__(self, other) -> "Args":
        return self.__merge__(other)

    def __lshift__(self, other) -> "Args":
        return self.__merge__(other)

    def __truediv__(self, other):
        self.separate(*other if isinstance(other, (list, tuple, set)) else other)
        return self

    def __eq__(self, other):
        return self.argument == other.argument

    def __repr__(self):
        if not self.argument:
            return "Empty"
        repr_string = "Args({0})"
        repr_args = ", ".join(
            f"'{name}': {arg['value']}" + (f" = '{arg['default']}'" if arg['default'] is not None else "")
            for name, arg in self.argument.items()
        )
        return repr_string.format(repr_args)


class CommandNode:
    """
    命令体基类, 规定基础命令的参数

    Attributes:
        name: 命令名称
        dest: 自定义命令名称
        args: 命令参数
        separators: 命令分隔符组
        action: 命令动作
        help_text: 命令帮助信息
    """
    name: str
    dest: str
    args: Args
    separators: Set[str]
    action: Optional[ArgAction]
    help_text: str
    requires: Union[Sequence[str], Set[str]]

    def __init__(
            self, name: str, args: Union[Args, str, None] = None,
            dest: Optional[str] = None,
            action: Optional[Union[ArgAction, Callable]] = None,
            separators: Optional[Union[str, Sequence[str], Set[str]]] = None,
            help_text: Optional[str] = None,
            requires: Optional[Union[str, Sequence[str], Set[str]]] = None
    ):
        """
        初始化命令节点

        Args:
            name(str): 命令节点名称
            args(Args): 命令节点参数
            action(ArgAction): 命令节点响应动作
            separators(Set[str]): 命令分隔符
            help_text(str): 命令帮助信息
        """
        if not name:
            raise InvalidParam(config.lang.node_name_empty)
        if re.match(r"^[`~?/.,<>;\':\"|!@#$%^&*()_+=\[\]}{]+.*$", name):
            raise InvalidParam(config.lang.node_name_error)
        _parts = name.split(" ")
        self.name = _parts[-1]
        self.requires = (requires if isinstance(requires, (list, tuple, set)) else (requires,)) \
            if requires else _parts[:-1]
        self.args = (args if isinstance(args, Args) else Args.from_string_list(
            [re.split("[:=]", p) for p in re.split(r"\s*,\s*", args)], {}
        )) if args else Args()
        self.action = ArgAction.__validator__(action, self.args)
        self.separators = {' '} if separators is None else (
            {separators} if isinstance(separators, str) else set(separators)
        )
        self.nargs = len(self.args.argument)
        self.is_compact = self.separators == {''}
        self.dest = (dest or (("_".join(self.requires) + "_") if self.requires else "") + self.name).lstrip('-')
        self.help_text = help_text or self.dest
        self.__hash = self._hash()

    is_compact: bool
    nargs: int
    __hash: int

    def separate(self, *separator: str):
        self.separators = set(separator)
        self.__hash = self._hash()
        return self

    def __repr__(self):
        return f"<{self.name} args={self.args}>"

    def _hash(self):
        data = vars(self)
        data.pop('_CommandNode__hash', None)
        return hash(str(data))

    def __hash__(self):
        return self.__hash

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.__hash__() == other.__hash__()


class Option(CommandNode):
    """命令选项, 可以使用别名"""
    aliases: FrozenSet[str]
    priority: int

    def __init__(
            self,
            name: str, args: Union[Args, str, None] = None,
            alias: Optional[List[str]] = None,
            dest: Optional[str] = None,
            action: Optional[Union[ArgAction, Callable]] = None,
            separators: Optional[Union[str, Sequence[str], Set[str]]] = None,
            help_text: Optional[str] = None,
            requires: Optional[Union[str, Sequence[str], Set[str]]] = None,
            priority: int = 0
    ):
        aliases = alias or []
        parts = name.split(" ")
        name, rest = parts[-1], parts[:-1]
        if "|" in name:
            aliases = name.split('|')
            aliases.sort(key=len, reverse=True)
            name = aliases[0]
            aliases.extend(aliases[1:])
        aliases.insert(0, name)
        self.aliases = frozenset(aliases)
        self.priority = priority
        super().__init__(
            " ".join(rest) + (" " if rest else "") + name, args, dest, action, separators, help_text, requires
        )


class Subcommand(CommandNode):
    """子命令, 次于主命令, 可解析 SubOption"""
    options: List[Option]
    sub_params: Dict[str, Union[List[Option], 'Sentence']]
    sub_part_len: range

    def __init__(
            self,
            name: str, options: Optional[List[Option]] = None, args: Union[Args, str, None] = None,
            dest: Optional[str] = None,
            action: Optional[Union[ArgAction, Callable]] = None,
            separators: Optional[Union[str, Sequence[str], Set[str]]] = None,
            help_text: Optional[str] = None,
            requires: Optional[Union[str, Sequence[str], Set[str]]] = None
    ):
        self.options = options or []
        super().__init__(name, args, dest, action, separators, help_text, requires)
        self.sub_params = {}
        self.sub_part_len = range(self.nargs)


@dataclass
class Sentence:
    name: str
    separators: Set[str] = field(default_factory=lambda: {' '})


class OptionResult(TypedDict):
    value: Any
    args: Dict[str, Any]


class SubcommandResult(TypedDict):
    value: Any
    args: Dict[str, Any]
    options: Dict[str, OptionResult]


class StrMounter(List[str]):
    pass


HelpOption = Option("--help|-h", help_text="显示帮助信息")
ShortcutOption = Option(
    '--shortcut|-SCT', Args["delete;O", "delete"]["name", str]["command", str, "_"]["expiration;K", int, 0],
    help_text='设置快捷命令'
)
