"""Alconna 的基础内容相关"""

import re
import inspect
from copy import copy
from enum import Enum
from typing import Union, Tuple, Dict, Iterable, Callable, Any, Optional, Sequence, List, Literal, \
    MutableSequence, TypedDict, Set

from .exceptions import InvalidParam, NullTextMessage
from .typing import (
    BasePattern, _All, Empty, DataUnit, AllParam, AnyOne, MultiArg, UnionArg, argument_type_validator
)
from .lang import lang_config
from .components.action import ArgAction


TAValue = Union[BasePattern, _All, type]
TADefault = Union[Any, DataUnit, Empty]


class ArgFlag(str, Enum):
    """
    参数标记
    """

    VAR_POSITIONAL = "S"  # '*'
    VAR_KEYWORD = "W"  # '**'
    OPTIONAL = 'O'  # '?'
    KWONLY = 'K'  # '@'
    HIDDEN = "H"  # '_'
    FORCE = "F"  # '#'
    ANTI = "A"  # '!'


class ArgUnit(TypedDict):
    """
    参数单元
    """

    value: TAValue
    """参数值"""

    default: TADefault
    """默认值"""

    optional: bool
    """是否可选"""

    kwonly: bool
    """是否键值对参数"""

    hidden: bool
    """是否隐藏类型参数"""


class ArgsMeta(type):
    """Args 类的元类"""

    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        cls.last_key = ''
        cls.selecting = False

    def __getattr__(cls, name):
        if name == 'shape':
            return super().__getattribute__(name)
        cls.last_key = name
        cls.selecting = True
        return cls

    def __getitem__(self, item):
        if isinstance(item, slice):
            return self(args=[item])
        elif isinstance(item, str):
            if self.selecting:
                self.selecting = False
                return self(args=[(self.last_key, item)])
            return self(args=[(item, item)])
        elif not isinstance(item, tuple):
            if self.selecting:
                self.selecting = False
                return self(args=[(self.last_key, item)])
            return self(args=[(item,)])
        args: "Args" = self(args=filter(lambda x: isinstance(x, slice), item))
        iters = list(filter(lambda x: isinstance(x, (list, tuple)), item))
        items = list(filter(lambda x: not isinstance(x, slice), item))
        iters += list(map(lambda x: (x,), filter(lambda x: isinstance(x, str), item)))
        if items:
            if self.selecting:
                args.__setitem__(self.last_key, items)
                self.selecting = False
            else:
                list(filter(args.__check_var__, iters))
        return args


class Args(metaclass=ArgsMeta):  # type: ignore
    """
    对命令参数的封装

    Attributes:
        argument: 存放参数内容的容器
    """
    extra: Literal["allow", "ignore", "reject"]
    argument: Dict[str, ArgUnit]
    var_positional: Optional[Tuple[str, MultiArg]]
    var_keyword: Optional[Tuple[str, MultiArg]]
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
            _le = len(arg)
            if _le == 0:
                raise NullTextMessage

            default = arg[2].strip(" ") if _le > 2 else None
            value = AllParam if arg[0].startswith("...") else (
                AnyOne if arg[0].startswith("..") else (
                    arg[1].strip(" ") if _le > 1 else arg[0].lstrip(".-"))
            )
            name = arg[0].replace("...", "").replace("..", "")

            if value not in (AllParam, AnyOne):
                if custom_types and custom_types.get(value) and not inspect.isclass(custom_types[value]):
                    raise InvalidParam(lang_config.common_custom_type_error.format(target=custom_types[value]))
                try:
                    value = eval(value, custom_types)
                except NameError:
                    pass
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
            if param.kind == param.VAR_POSITIONAL:
                name += ";S"
            if param.kind == param.VAR_KEYWORD:
                name += ";W"
            _args.add_argument(name, value=anno, default=de)
        return _args, method

    def __init__(
            self,
            args: Optional[Iterable[Union[slice, Sequence]]] = None,
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
        self.optional_count = 0
        if isinstance(separators, str):
            self.separators = {separators}
        else:
            self.separators = set(separators)
        self.argument = {  # type: ignore
            k: {
                "value": argument_type_validator(v),
                "default": None, 'optional': False, 'hidden': False, 'kwonly': False
            } for k, v in kwargs.items()
        }
        for arg in (args or []):
            self.__check_var__(arg)

    __ignore__ = "extra", "var_positional", "var_keyword", "argument", "optional_count", "separators"

    def add_argument(
            self,
            name: str,
            *,
            value: Any,
            default: Optional[Any] = None,
            flags: Optional[Iterable[ArgFlag]] = None
    ):
        """
        添加一个参数
        """
        if name in self.argument:
            return  # raise InvalidParam(lang_config.common_argument_exist_error.format(target=name))
        if flags:
            name += ";" + "|".join(flags)
        self.__check_var__([name, value, default])

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

    def __check_var__(self, val: Union[slice, Sequence]):
        if isinstance(val, slice):
            name, value, default = val.start, val.stop, val.step
        else:
            name, value, default = val[0], val[1] if len(val) > 1 else val[0], val[2] if len(val) > 2 else None
        if not isinstance(name, str):
            raise InvalidParam(lang_config.args_name_error)
        if not name.strip():
            raise InvalidParam(lang_config.args_name_empty)
        _value = argument_type_validator(value, self.extra)
        if isinstance(_value, (Sequence, MutableSequence)):
            if len(_value) == 2 and Empty in _value:
                _value.remove(Empty)
                _value = _value[0]
                default = Empty if default is None else default
            else:
                _value = UnionArg(_value)
        if default in ("...", Ellipsis):
            default = Empty
        if _value is Empty:
            raise InvalidParam(lang_config.args_value_error.format(target=name))
        _addition = {'optional': False, 'hidden': False, 'kwonly': False}
        if res := re.match(r"^.+?;(?P<flag>.+?)$", name):
            flags = res.group("flag").split("|")
            name = name.replace(f";{res.group('flag')}", "")
            _limit = False
            for flag in flags:
                if flag == ArgFlag.FORCE and not _limit:
                    _value = (
                        BasePattern(value)
                        if isinstance(value, str)
                        else BasePattern.of(value)
                    )

                    _limit = True
                if flag == ArgFlag.ANTI and not _limit:
                    if isinstance(_value, UnionArg):
                        _value.reverse()
                    elif _value not in (AnyOne, AllParam):
                        _value = copy(_value)
                        _value.reverse()
                    _limit = True
                if flag == ArgFlag.VAR_KEYWORD and not _limit:
                    if self.var_keyword:
                        raise InvalidParam(lang_config.args_duplicate_kwargs)
                    if _value not in (AnyOne, AllParam):
                        _value = MultiArg(_value, flag='kwargs')
                        self.var_keyword = (name, _value)
                    _limit = True
                if flag == ArgFlag.VAR_POSITIONAL and not _limit:
                    if self.var_positional:
                        raise InvalidParam(lang_config.args_duplicate_varargs)
                    if _value not in (AnyOne, AllParam):
                        _value = MultiArg(_value)
                        self.var_positional = (name, _value)
                if flag.isdigit() and not _limit:
                    if self.var_positional:
                        raise InvalidParam(lang_config.args_duplicate_varargs)
                    if _value not in (AnyOne, AllParam):
                        _value = MultiArg(_value, array_length=int(flag))
                        self.var_positional = (name, _value)
                if flag == ArgFlag.OPTIONAL:
                    if self.var_keyword or self.var_positional:
                        raise InvalidParam(lang_config.args_exclude_mutable_args)
                    _addition['optional'] = True
                    self.optional_count += 1
                if flag == ArgFlag.HIDDEN:
                    _addition['hidden'] = True
                if flag == ArgFlag.KWONLY:
                    if self.var_keyword or self.var_positional:
                        raise InvalidParam(lang_config.args_exclude_mutable_args)
                    _addition['kwonly'] = True
        self.argument[name] = {"value": _value, "default": default}  # type: ignore
        self.argument[name].update(_addition)  # type: ignore

    def __len__(self):
        return len(self.argument)

    def __setitem__(self, key, value):
        return self.__setattr__(key, value)

    def __setattr__(self, key, value):
        if key in self.__ignore__:
            super().__setattr__(key, value)
        elif isinstance(value, Iterable):
            values = list(value)
            self.__check_var__([key, values[0], values[1]])
        else:
            self.__check_var__([key, value])
        return self

    def __getitem__(self, item) -> Union["Args", Tuple[TAValue, TADefault]]:
        if isinstance(item, str):
            if self.argument.get(item):
                return self.argument[item]['value'], self.argument[item]['default']
            else:
                raise KeyError(lang_config.args_key_not_found)
        if isinstance(item, slice):
            self.__check_var__(item)
        elif isinstance(item, Iterable):
            slices = list(filter(lambda x: isinstance(x, slice), item))
            items = list(filter(lambda x: isinstance(x, Sequence), item))
            items += list(map(lambda x: (x,), filter(lambda x: isinstance(x, str), item)))
            list(filter(self.__check_var__, items))
            list(filter(self.__check_var__, slices))
        return self

    def __merge__(self, other) -> "Args":
        if isinstance(other, Args):
            self.argument.update(other.argument)
            del other
        elif isinstance(other, Sequence):
            self.__getitem__([other])
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
            [
                f"'{name}': '{arg['value']}'" + (f" = '{arg['default']}'" if arg['default'] is not None else "")
                for name, arg in self.argument.items()
            ]
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

    def __init__(
            self, name: str,
            args: Union[Args, str, None] = None,
            dest: Optional[str] = None,
            action: Optional[Union[ArgAction, Callable]] = None,
            separators: Optional[Union[str, Iterable[str]]] = None,
            help_text: Optional[str] = None,
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
        if not name.lstrip():
            raise InvalidParam(lang_config.node_name_empty)
        if re.match(r"^[`~?/.,<>;\':\"|!@#$%^&*()_+=\[\]}{]+.*$", name):
            raise InvalidParam(lang_config.node_name_error)
        self.name = name
        if args is None:
            self.args = Args()
        elif isinstance(args, str):
            self.args = Args.from_string_list([re.split("[:=]", p) for p in re.split(r"\s*,\s*", args)], {})
        else:
            self.args = args
        self.dest = (dest or name).lstrip('-')
        self.action = ArgAction.__validator__(action, self.args)
        if separators is None:
            self.separators = {' '}
        elif isinstance(separators, str):
            self.separators = {separators}
        else:
            self.separators = set(separators)
        self.help_text = help_text or self.dest
        self.nargs = len(self.args.argument)
        self.is_compact = self.separators == {''}

    is_compact: bool
    nargs: int

    def separate(self, *separator: str):
        self.separators = set(separator)
        return self

    def __repr__(self):
        return f"<{self.name} args={self.args}>"


class Option(CommandNode):
    """命令选项, 可以使用别名"""
    aliases: List[str]

    def __init__(
            self,
            name: str,
            args: Union[Args, str, None] = None,
            alias: Optional[List[str]] = None,
            dest: Optional[str] = None,
            action: Optional[Union[ArgAction, Callable]] = None,
            separator: Optional[Union[str, Iterable[str]]] = None,
            help_text: Optional[str] = None,

    ):
        self.aliases = alias or []
        if "|" in name:
            aliases = name.replace(' ', '').split('|')
            aliases.sort(key=len, reverse=True)
            name = aliases[0]
            self.aliases.extend(aliases[1:])
        self.aliases.insert(0, name)
        super().__init__(name, args, dest, action, separator, help_text)


class Subcommand(CommandNode):
    """子命令, 次于主命令, 可解析 SubOption"""
    options: List[Option]
    sub_params: Dict[str, Option]
    sub_part_len: range

    def __init__(
            self,
            name: str,
            options: Optional[List[Option]] = None,
            args: Union[Args, str, None] = None,
            dest: Optional[str] = None,
            action: Optional[Union[ArgAction, Callable]] = None,
            separator: Optional[Union[str, Iterable[str]]] = None,
            help_text: Optional[str] = None,
    ):
        self.options = options or []
        super().__init__(name, args, dest, action, separator, help_text)
        self.sub_params = {}
        self.sub_part_len = range(self.nargs)


class OptionResult(TypedDict):
    value: Any
    args: Dict[str, Any]


class SubcommandResult(TypedDict):
    value: Any
    args: Dict[str, Any]
    options: Dict[str, OptionResult]
