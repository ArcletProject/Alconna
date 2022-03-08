"""Alconna 的基础内容相关"""

import re
import inspect
from types import LambdaType
from typing import Union, Tuple, Type, Dict, Iterable, overload, Callable, Any, Optional, Sequence, List, Literal, \
    MutableSequence
from .exceptions import InvalidParam, NullTextMessage
from .types import (
    ArgPattern, _AnyParam, Empty, NonTextElement, AllParam, AnyParam, MultiArg, AntiArg, UnionArg, argtype_validator,
)

TAValue = Union[ArgPattern, Type[NonTextElement], _AnyParam, MultiArg, AntiArg, UnionArg]
TADefault = Union[Any, NonTextElement, Empty]
TArgs = Dict[str, Union[TAValue, TADefault]]


class ArgsMeta(type):

    def __getattr__(cls, name):
        cls.last_key = name
        return cls

    def __getitem__(cls, item):
        if isinstance(item, slice):
            return cls(args=[item])
        elif not isinstance(item, tuple):
            return cls(args=[(cls.last_key, item)])
        slices = list(filter(lambda x: isinstance(x, slice), item))
        args = cls(args=slices)
        items = list(filter(lambda x: not isinstance(x, slice), item))
        if items:
            args.__setitem__(cls.last_key, items)
        return args


class Args(metaclass=ArgsMeta):
    """
    对命令参数的封装

    Attributes:
        argument: 存放参数内容的容器
    """
    extra: Literal["allow", "ignore", "reject"]
    argument: Dict[str, TArgs]
    var_positional: Optional[Tuple[str, MultiArg]]
    var_keyword: Optional[Tuple[str, MultiArg]]
    optional: List[str]
    kwonly: List[str]

    @classmethod
    def from_string_list(cls, args: List[List[str]], custom_types: Dict) -> "Args":
        """
        从处理好的字符串列表中生成Args

        Args:
            args: 字符串列表
            custom_types: 自定义的类型

        Example:
            Args.from_string_list([["foo", "str"], ["bar", "digit", "123"]], {"digit":int})
        """
        _args = cls()
        for arg in args:
            _le = len(arg)
            if _le == 0:
                raise NullTextMessage

            default = arg[2].strip(" ") if _le > 2 else None
            value = AllParam if arg[0].startswith("...") else (arg[1].strip(" ") if _le > 1 else AnyParam)
            name = arg[0].replace("...", "")

            if not isinstance(value, AnyParam.__class__):
                if custom_types and custom_types.get(value) and not inspect.isclass(custom_types[value]):
                    raise InvalidParam(f"自定义参数类型传入的不是类型而是 {custom_types[value]}, 这是有意而为之的吗?")
                try:
                    value = eval(value, custom_types)
                except NameError:
                    pass
            _args.__merge__([name, value, default])
        return _args

    @classmethod
    def from_callable(cls, target: Callable, extra: Literal["allow", "ignore", "reject"] = "allow"):
        """
        从方法中构造Args
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
                anno = type(de) if de is not inspect.Signature.empty else AnyParam
            if de is inspect.Signature.empty:
                de = None
            elif de is None:
                de = inspect.Signature.empty
            if param.kind == param.VAR_POSITIONAL:
                name = "*" + name
            if param.kind == param.VAR_KEYWORD:
                name = "**" + name
            _args.__merge__([name, anno, de])
        return _args, method

    @overload
    def __init__(
            self,
            args: Optional[Union[slice, Sequence]] = None,
            extra: Literal["allow", "ignore", "reject"] = "allow",
            **kwargs: ...
    ):
        ...

    def __init__(
            self,
            args: ... = None,
            extra: Literal["allow", "ignore", "reject"] = "allow",
            **kwargs: TAValue
    ):
        """
        构造一个Args

        Args:
            args: 应传入 slice|tuple, 代表key、value、default
            kwargs: 传入key与value; default需要另外传入
        """
        self.extra = extra
        self.var_positional = None
        self.var_keyword = None
        self.optional = []
        self.kwonly = []
        self.argument = {
            k: {"value": argtype_validator(v), "default": None} for k, v in kwargs.items()
        }
        self.__check_vars__(args or [])

    __ignore__ = "extra", "var_positional", "var_keyword", "argument", "optional", "kwonly"

    def default(self, **kwargs: TADefault):
        """设置参数的默认值"""
        for k, v in kwargs.items():
            if self.argument.get(k):
                self.argument[k]['default'] = v
        return self

    def __check_vars__(self, args: Iterable[Union[slice, Sequence]]):
        for sl in args:
            if isinstance(sl, slice):
                name, value, default = sl.start, sl.stop, sl.step
            else:
                name, value, default = sl[0], sl[1] if len(sl) > 1 else None, sl[2] if len(sl) > 2 else None
            if not isinstance(name, str):
                raise InvalidParam("参数的名字只能是字符串")
            if name == "":
                raise InvalidParam("该参数的指示名不能为空")
            if not name.startswith("#"):
                _value = argtype_validator(value, self.extra)
            else:
                name = name.lstrip("#")
                _value = value if not isinstance(value, str) else ArgPattern(value)
            if isinstance(_value, (Sequence, MutableSequence)):
                if len(_value) == 2 and Empty in _value:
                    _value.remove(Empty)
                    _value = _value[0]
                    default = Empty if default is None else default
                else:
                    _value = UnionArg(_value, anti=name.startswith("!"))
            if name.startswith("**"):
                name = name.lstrip("**").replace("@", "").replace("?", "")
                if self.var_keyword:
                    raise InvalidParam("不能同时设置多个键值对可变参数")
                if not isinstance(_value, (_AnyParam, UnionArg)):
                    _value = MultiArg(_value, flag='kwargs')
                    self.var_keyword = (name, _value)
            elif name.startswith("*"):
                name = name.lstrip("*").replace("@", "").replace("?", "")
                if self.var_positional:
                    raise InvalidParam("不能同时设置多个非键值对可变参数")
                if not isinstance(_value, (_AnyParam, UnionArg)):
                    _value = MultiArg(_value)
                    self.var_positional = (name, _value)
            elif name.startswith("!"):
                name = name.lstrip("!")
                if not isinstance(_value, (_AnyParam, UnionArg)):
                    _value = AntiArg(_value)
            if "?" in name:
                name = name.replace("?", "")
                self.optional.append(name)
            if "@" in name:
                name = name.replace("@", "")
                self.kwonly.append(name)
            if default in ("...", Ellipsis):
                default = Empty
            if _value is Empty:
                raise InvalidParam(f"{name} 的参数值不能为Empty")
            self.argument[name] = {"value": _value, "default": default}

    def params(self, sep: str = " "):
        """预处理参数的 help doc"""
        argument_string = ""
        i = 0
        length = len(self.argument)
        for k, v in self.argument.items():
            arg = f"<{k}" if k not in self.optional else f"<{k}?"
            _sep = "=" if k in self.kwonly else ":"
            if isinstance(v['value'], _AnyParam):
                arg += f"{_sep}WildMatch"
            elif isinstance(v['value'], ArgPattern):
                arg += f"{_sep}{v['value'].alias or v['value'].origin_type.__name__}"
            else:
                try:
                    arg += f"{_sep}Type_{v['value'].__name__}"
                except AttributeError:
                    arg += f"{_sep}Type_{repr(v['value'])}"
            if v['default'] is Empty:
                arg += ", default=None"
            elif v['default'] is not None:
                arg += f", default={v['default']}"
            argument_string += arg + ">"
            i += 1
            if i != length:
                argument_string += sep
        return argument_string

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
            return self.argument[item].get('value'), self.argument[item].get('default')
        if isinstance(item, slice):
            slices = [item]
            self.__check_vars__(slices)
        elif isinstance(item, Iterable):
            slices = list(filter(lambda x: isinstance(x, slice), item))
            items = list(filter(lambda x: isinstance(x, Sequence), item))
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

    def __getstate__(self):
        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        args = {}
        for k, v in self.argument.items():
            value = v['value']
            default = v['default']
            if isinstance(value, (ArgPattern, _AnyParam)):
                value = value.__getstate__()
            else:
                value = {"type": value.__name__}
            args[k] = {"value": value, "default": default}
        return {"argument": args, "extra": self.extra, "optional": self.optional, "kwonly": self.kwonly}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        args = cls(extra=data['extra'])
        args.optional = data['optional']
        args.kwonly = data['kwonly']
        for k, v in data['argument'].items():
            value = v['value']
            default = v['default']
            v_type = value.get("type")
            if v_type == "ArgPattern":
                value = ArgPattern.from_dict(value)
            elif v_type == "AnyParam":
                value = AnyParam
            elif v_type == "AllParam":
                value = AllParam
            else:
                value = eval(v_type)
            args.argument[k] = {"value": value, "default": default}
        return args

    def __setstate__(self, state):
        self.extra = state["extra"]
        self.optional = state['optional']
        self.kwonly = state['kwonly']
        self.var_positional = None
        self.var_keyword = None
        for k, v in state['argument'].items():
            value = v['value']
            default = v['default']
            v_type = value.get("type")
            if v_type == "ArgPattern":
                value = ArgPattern.from_dict(value)
            elif v_type == "AnyParam":
                value = AnyParam
            elif v_type == "AllParam":
                value = AllParam
            else:
                value = eval(v_type)
            self.argument[k] = {"value": value, "default": default}


class ArgAction:
    """
    负责封装action的类

    Attributes:
        action: 实际的function
    """
    awaitable: bool
    action: Callable[..., Any]

    def __init__(self, action: Callable = None):
        """
        ArgAction的构造函数

        Args:
            action: (...) -> Iterable
        """
        self.action = action
        self.awaitable = inspect.iscoroutinefunction(action)

    def handle(self, option_dict: dict, varargs: List, kwargs: Dict, is_raise_exception: bool):
        try:
            additional_values = self.action(*option_dict.values(), *varargs, **kwargs)
            if additional_values is None:
                return option_dict
            if not isinstance(additional_values, Iterable):
                additional_values = [additional_values]
            for i, k in enumerate(option_dict.keys()):
                option_dict[k] = additional_values[i]
        except Exception as e:
            if is_raise_exception:
                raise e
        return option_dict

    async def handle_async(self, option_dict: dict, varargs: List, kwargs: Dict, is_raise_exception: bool):
        try:
            additional_values = await self.action(*option_dict.values(), *varargs, **kwargs)
            if additional_values is None:
                return option_dict
            if not isinstance(additional_values, Iterable):
                additional_values = [additional_values]
            for i, k in enumerate(option_dict.keys()):
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
            separator: str = None,
            help_text: str = None,
    ):
        """
        初始化命令体

        Args:
            name(str): 命令名称
            args(Args): 命令参数
            action(ArgAction): 命令动作
        """
        if name == "":
            raise InvalidParam("该指令的名字不能为空")
        if re.match(r"^[`~?/.,<>;\':\"|!@#$%^&*()_+=\[\]}{]+.*$", name):
            raise InvalidParam("该指令的名字含有非法字符")
        self.name = name
        if args is None:
            self.args = Args()
        elif isinstance(args, str):
            self.args = Args.from_string_list(
                [re.split("[:|=]", p) for p in re.split(r"\s*,\s*", args)], {}
            )
        else:
            self.args = args
        self.__check_action__(action)
        self.separator = separator or " "
        self.help_text = help_text or self.name
        self.__generate_help__()

        self.nargs = len(self.args.argument)

    help_docstring: str
    nargs: int
    scale: Tuple[int, int]

    def __getitem__(self, item):
        self.args.__merge__(Args[item])
        self.nargs = len(self.args.argument)
        return self

    def __generate_help__(self):
        """预处理 help 文档"""
        self.help_docstring = f"# {self.help_text}\n  {self.name}{self.separator}{self.args.params(self.separator)}\n"

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
                    raise InvalidParam("action 接受的参数个数必须与 Args 里的一致")
                if not isinstance(action, LambdaType):
                    for i, k in enumerate(self.args.argument):
                        anno = argument[i][1]
                        if anno == inspect.Signature.empty:
                            anno = type(argument[i][2]) if argument[i][2] is not inspect.Signature.empty else str
                        value = self.args.argument[k]['value']
                        if isinstance(
                                value, ArgPattern
                        ):
                            if value.origin_type != getattr(anno, "__origin__", anno):
                                raise InvalidParam(f"{argument[i][0]}的类型 与 Args 中 '{k}' 接受的类型 {value.origin_type} 不一致")
                        elif isinstance(
                                value, _AnyParam
                        ):
                            if anno not in (Empty, Any):
                                raise InvalidParam(f"{argument[i][0]}的类型不能指定为 {anno}")
                        elif isinstance(
                                value, Iterable
                        ):
                            if anno != value.__class__:
                                raise InvalidParam(f"{argument[i][0]}的类型 与 Args 中 '{k}' 接受的类型 {value.__class__} 不一致")
                        elif anno != value:
                            raise InvalidParam(f"{argument[i][0]}指定的消息元素类型不是 {value}")
                self.action = ArgAction(action)
        else:
            self.action = action

    def __repr__(self):
        return f"<{self.name} args={self.args}>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.__class__.__name__,
            "name": self.name,
            "args": self.args.to_dict(),
            "separator": self.separator,
            "help_text": self.help_text,
        }

    def __getstate__(self):
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        name = data['name']
        args = Args.from_dict(data['args'])
        cmd = cls(name, args, separator=data['separator'], help_text=data['help_text'])
        return cmd

    def __setstate__(self, state):
        self.__init__(
            state['name'], Args.from_dict(state['args']), separator=state['separator'], help_text=state['help_text']
        )
