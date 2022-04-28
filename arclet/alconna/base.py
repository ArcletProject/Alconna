"""Alconna 的基础内容相关"""
import asyncio
import re
import inspect
from enum import Enum
from types import LambdaType
from typing import Union, Tuple, Type, Dict, Iterable, Callable, Any, Optional, Sequence, List, Literal, \
    MutableSequence, TypedDict
from .exceptions import InvalidParam, NullTextMessage
from .types import (
    ArgPattern,
    _AnyParam, Empty, DataUnit, AllParam, AnyParam, MultiArg, AntiArg, UnionArg, argument_type_validator, TypePattern
)
from .lang import lang_config

TAValue = Union[ArgPattern, TypePattern, Type[DataUnit], _AnyParam]
TADefault = Union[Any, DataUnit, Empty]


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

    def __getitem__(cls, item):
        if isinstance(item, slice):
            return cls(args=[item])
        elif isinstance(item, str):
            if cls.selecting:
                cls.selecting = False
                return cls(args=[(cls.last_key, item)])
            return cls(args=[(item, item)])
        elif not isinstance(item, tuple):
            if cls.selecting:
                cls.selecting = False
                return cls(args=[(cls.last_key, item)])
            return cls(args=[(item,)])
        slices = list(filter(lambda x: isinstance(x, slice), item))
        args = cls(args=slices)
        iters = list(filter(lambda x: isinstance(x, (list, tuple)), item))
        items = list(filter(lambda x: not isinstance(x, slice), item))
        iters += list(map(lambda x: (x,), filter(lambda x: isinstance(x, str), item)))
        if items:
            if cls.selecting:
                args.__setitem__(cls.last_key, items)
                cls.selecting = False
            else:
                args.__check_vars__(iters)
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
    separator: str

    class _Flag(str, Enum):
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
                AnyParam if arg[0].startswith("..") else (
                    arg[1].strip(" ") if _le > 1 else arg[0].lstrip(".-"))
            )
            name = arg[0].replace("...", "").replace("..", "")

            if not isinstance(value, AnyParam.__class__):
                if custom_types and custom_types.get(value) and not inspect.isclass(custom_types[value]):
                    raise InvalidParam(lang_config.common_custom_type_error.format(target=custom_types[value]))
                try:
                    value = eval(value, custom_types)
                except NameError:
                    pass
            _args.__merge__([name, value, default])
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
                anno = type(de) if de not in (inspect.Signature.empty, None) else AnyParam
            if de is inspect.Signature.empty:
                de = None
            elif de is None:
                de = inspect.Signature.empty
            if param.kind == param.VAR_POSITIONAL:
                name += ";S"
            if param.kind == param.VAR_KEYWORD:
                name += ";W"
            _args.__merge__([name, anno, de])
        return _args, method

    def __init__(
            self,
            args: Optional[Union[List[slice], Sequence]] = None,
            extra: Literal["allow", "ignore", "reject"] = "allow",
            separator: str = " ",
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
        self.separator = separator
        self.argument = {  # type: ignore
            k: {
                "value": argument_type_validator(v),
                "default": None, 'optional': False, 'hidden': False, 'kwonly': False
            } for k, v in kwargs.items()
        }
        self.__check_vars__(args or [])

    __ignore__ = "extra", "var_positional", "var_keyword", "argument", "optional_count", "separator"

    def default(self, **kwargs: TADefault):
        """设置参数的默认值"""
        for k, v in kwargs.items():
            if self.argument.get(k):
                self.argument[k]['default'] = v
        return self

    def separate(self, separator: str):
        """设置参数的分隔符"""
        self.separator = separator
        return self

    def __check_vars__(self, args: Iterable[Union[slice, Sequence]]):
        for sl in args:
            if isinstance(sl, slice):
                name, value, default = sl.start, sl.stop, sl.step
            else:
                name, value, default = sl[0], sl[1] if len(sl) > 1 else sl[0], sl[2] if len(sl) > 2 else None
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
                    if flag == self._Flag.FORCE and not _limit:
                        _value = value if not isinstance(value, str) else ArgPattern(value)
                        _limit = True
                    if flag == self._Flag.ANTI and not _limit:
                        if isinstance(_value, UnionArg):
                            _value.anti = True
                        elif not isinstance(_value, _AnyParam):
                            _value = AntiArg(_value)
                        _limit = True
                    if flag == self._Flag.VAR_KEYWORD and not _limit:
                        if self.var_keyword:
                            raise InvalidParam(lang_config.args_duplicate_kwargs)
                        if not isinstance(_value, (_AnyParam, UnionArg)):
                            _value = MultiArg(_value, flag='kwargs')
                            self.var_keyword = (name, _value)
                        _limit = True
                    if flag == self._Flag.VAR_POSITIONAL and not _limit:
                        if self.var_positional:
                            raise InvalidParam(lang_config.args_duplicate_varargs)
                        if not isinstance(_value, (_AnyParam, UnionArg)):
                            _value = MultiArg(_value)
                            self.var_positional = (name, _value)
                    if flag.isdigit() and not _limit:
                        if self.var_positional:
                            raise InvalidParam(lang_config.args_duplicate_varargs)
                        if not isinstance(_value, (_AnyParam, UnionArg)):
                            _value = MultiArg(_value, array_length=int(flag))
                            self.var_positional = (name, _value)
                    if flag == self._Flag.OPTIONAL:
                        if self.var_keyword or self.var_positional:
                            raise InvalidParam(lang_config.args_exclude_mutable_args)
                        _addition['optional'] = True
                        self.optional_count += 1
                    if flag == self._Flag.HIDDEN:
                        _addition['hidden'] = True
                    if flag == self._Flag.KWONLY:
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
            self.__check_vars__([(key, values[0], values[1])])
        else:
            self.__check_vars__([(key, value)])
        return self

    def __getitem__(self, item) -> Union["Args", Tuple[TAValue, TADefault]]:
        if isinstance(item, str):
            if self.argument.get(item):
                return self.argument[item]['value'], self.argument[item]['default']
            else:
                raise KeyError(lang_config.args_key_not_found)
        if isinstance(item, slice):
            slices = [item]
            self.__check_vars__(slices)
        elif isinstance(item, Iterable):
            slices = list(filter(lambda x: isinstance(x, slice), item))
            items = list(filter(lambda x: isinstance(x, Sequence), item))
            items += list(map(lambda x: (x,), filter(lambda x: isinstance(x, str), item)))
            if items:
                self.__check_vars__(items)
            self.__check_vars__(slices)
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
        self.separate(other)
        return self

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


class ArgAction:
    """
    负责封装action的类

    Attributes:
        action: 实际的function
    """
    action: Callable[..., Any]

    def __init__(self, action: Callable):
        """
        ArgAction的构造函数

        Args:
            action: (...) -> Sequence
        """
        self.action = action

    @staticmethod
    def _loop() -> asyncio.AbstractEventLoop:
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.get_event_loop()

    def handle(
            self,
            option_dict: dict,
            varargs: Optional[List] = None,
            kwargs: Optional[Dict] = None,
            is_raise_exception: bool = False,
    ):
        """
        处理action

        Args:
            option_dict: 参数字典
            varargs: 可变参数
            kwargs: 关键字参数
            is_raise_exception: 是否抛出异常
        """
        varargs = varargs or []
        kwargs = kwargs or {}
        try:
            if inspect.iscoroutinefunction(self.action):
                loop = self._loop()
                if loop.is_running():
                    loop.create_task(self.action(*option_dict.values(), *varargs, **kwargs))
                    return option_dict
                else:
                    additional_values = loop.run_until_complete(self.action(*option_dict.values(), *varargs, **kwargs))
            else:
                additional_values = self.action(*option_dict.values(), *varargs, **kwargs)
            if not additional_values:
                return option_dict
            if not isinstance(additional_values, Sequence):
                option_dict['result'] = additional_values
                return option_dict
            for i, k in enumerate(option_dict.keys()):
                if i == len(additional_values):
                    break
                option_dict[k] = additional_values[i]
        except Exception as e:
            if is_raise_exception:
                raise e
        return option_dict


class CommandNode:
    """
    命令体基类, 规定基础命令的参数

    Attributes:
        name: 命令名称
        args: 命令参数
        separator: 命令分隔符
        action: 命令动作
        help_text: 命令帮助信息
    """
    name: str
    args: Args
    separator: str
    action: ArgAction
    help_text: str

    def __init__(
            self, name: str,
            args: Union[Args, str, None] = None,
            action: Optional[Union[ArgAction, Callable]] = None,
            separator: Optional[str] = None,
            help_text: Optional[str] = None,
    ):
        """
        初始化命令节点

        Args:
            name(str): 命令节点名称
            args(Args): 命令节点参数
            action(ArgAction): 命令节点响应动作
            separator(str): 命令分隔符
            help_text(str): 命令帮助信息
        """
        if name.lstrip() == "":
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
        self.__check_action__(action)
        self.separator = separator if separator is not None else " "
        self.help_text = help_text or self.name
        self.nargs = len(self.args.argument)
        self.is_compact = False
        if separator == "":
            self.is_compact = True

    is_compact: bool
    nargs: int
    scale: Tuple[int, int]

    def __getitem__(self, item):
        self.args.__merge__(Args[item])
        self.nargs = len(self.args.argument)
        return self

    def separate(self, separator: str):
        self.separator = separator
        return self

    def __check_action__(self, action):
        if action:
            if isinstance(action, ArgAction):
                self.action = action
                return
            if len(self.args.argument) == 0:
                self.args, _ = Args.from_callable(action)
                self.action = ArgAction(action)
            else:
                argument = [
                    (name, param.annotation, param.default)
                    for name, param in inspect.signature(action).parameters.items()
                    if name not in ["self", "cls", "option_dict", "exception_in_time"]
                ]
                if len(argument) != len(self.args.argument):
                    raise InvalidParam(lang_config.action_length_error)
                if not isinstance(action, LambdaType):
                    for i, k in enumerate(self.args.argument):
                        anno = argument[i][1]
                        if anno == inspect.Signature.empty:
                            anno = type(argument[i][2]) if argument[i][2] is not inspect.Signature.empty else str
                        value = self.args.argument[k]['value']
                        if isinstance(value, ArgPattern):
                            if value.origin_type != getattr(anno, "__origin__", anno):
                                raise InvalidParam(lang_config.action_args_error.format(
                                    target=argument[i][0], key=k, source=value.origin_type
                                ))
                        elif isinstance(value, _AnyParam):
                            if anno not in (Empty, Any):
                                raise InvalidParam(lang_config.action_args_empty.format(
                                    target=argument[i][0], source=anno
                                ))
                        elif isinstance(value, Iterable):
                            if anno != value.__class__:
                                raise InvalidParam(lang_config.action_args_error.format(
                                    target=argument[i][0], key=k, source=value.__class__
                                ))
                        elif anno != value:
                            raise InvalidParam(lang_config.action_args_not_same.format(
                                target=argument[i][0], source=value
                            ))
                self.action = ArgAction(action)
        else:
            self.action = action

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
            action: Optional[Union[ArgAction, Callable]] = None,
            separator: Optional[str] = None,
            help_text: Optional[str] = None,

    ):
        self.aliases = alias if alias else []
        if "|" in name:
            aliases = name.replace(' ', '').split('|')
            aliases.sort(key=len, reverse=True)
            name = aliases[0]
            self.aliases.extend(aliases[1:])
        self.aliases.insert(0, name)
        super().__init__(name, args, action, separator, help_text)


class Subcommand(CommandNode):
    """子命令, 次于主命令, 可解析 SubOption"""
    options: List[Option]
    sub_params: Dict[str, Option]
    sub_part_len: range

    def __init__(
            self,
            name: str,
            options: Optional[Iterable[Option]] = None,
            args: Union[Args, str, None] = None,
            action: Optional[Union[ArgAction, Callable]] = None,
            separator: Optional[str] = None,
            help_text: Optional[str] = None,
    ):
        self.options = list(options or [])
        super().__init__(name, args, action, separator, help_text)
        self.sub_params = {}
        self.sub_part_len = range(self.nargs)
