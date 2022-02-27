"""Alconna 的基础内容相关"""

import re
import inspect
from typing import Union, Any, Optional, Callable, Tuple, Type, Dict, Iterable, Generator, overload, List
from .exceptions import InvalidParam, NullTextMessage
from .types import ArgPattern, _AnyParam, Empty, NonTextElement, AllParam, AnyParam, MultiArg, AntiArg
from .util import arg_check
from .actions import ArgAction

TAValue = Union[ArgPattern, Type[NonTextElement], _AnyParam, MultiArg, AntiArg, Iterable]
TADefault = Union[Any, NonTextElement, Empty]
TArgs = Dict[str, Union[TAValue, TADefault]]


class Args:
    """
    对命令参数的封装

    Attributes:
        argument: 存放参数内容的容器
    """
    argument: Dict[str, TArgs]

    __slots__ = "argument"

    @overload
    def __init__(self, *args: Union[slice, tuple], **kwargs: ...):
        ...

    def __init__(self, *args: ..., **kwargs: TAValue):
        """
        构造一个Args

        Args:
            args: 应传入 slice|tuple, 代表key、value、default
            kwargs: 传入key与value; default需要另外传入
        """
        self.argument = {
            k: {"value": arg_check(v), "default": None}
            for k, v in kwargs.items()
            if k not in ("name", "args", "alias")
        }
        self._check(args)

    def default(self, **kwargs: TADefault):
        """设置参数的默认值"""
        for k, v in kwargs.items():
            if self.argument.get(k):
                self.argument[k]['default'] = v
        return self

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
            value = AllParam if arg[0].startswith("...") else (arg[1].strip(" ()") if _le > 1 else AnyParam)
            name = arg[0].replace("...", "")

            if not isinstance(value, AnyParam.__class__):
                if custom_types and custom_types.get(value) and not inspect.isclass(custom_types[value]):
                    raise InvalidParam(f"自定义参数类型传入的不是类型而是 {custom_types[value]}, 这是有意而为之的吗?")
                try:
                    custom_types.update(custom_types)
                    value = eval(value, custom_types.copy())
                except NameError:
                    pass
            _args.__getitem__([(name, value, default)])
        return _args

    def _check(self, args: Iterable[Union[slice, tuple]]):
        for sl in args:
            if isinstance(sl, slice):
                name, value, default = sl.start, sl.stop, sl.step
            else:
                name, value = sl[0], sl[1] if len(sl) > 1 else None
                default = sl[2] if len(sl) > 2 else None
            if not isinstance(name, str):
                raise InvalidParam("参数的名字只能是字符串")
            if name in ("name", "args", "alias"):
                raise InvalidParam("非法的参数名字")
            if name == "":
                raise InvalidParam("该参数的指示名不能为空")
            value = arg_check(value)
            if value is Empty:
                raise InvalidParam("参数值不能为Empty")
            if name.startswith("*"):
                name = name.lstrip("*")
                if not isinstance(value, _AnyParam):
                    value = MultiArg(value)
            elif name.startswith("!"):
                name = name.lstrip("!")
                if not isinstance(value, _AnyParam):
                    value = AntiArg(value)
            if default in ("...", Ellipsis):
                default = Empty
            self.argument.setdefault(name, {"value": value, "default": default})

    def params(self, sep: str = " "):
        """预处理参数的 help doc"""
        argument_string = ""
        i = 0
        length = len(self.argument)
        for k, v in self.argument.items():
            arg = f"<{k}"
            if isinstance(v['value'], _AnyParam):
                arg += ": WildMatch"
            elif isinstance(v['value'], Iterable):
                arg += ": (" + "|".join(v['value']) + ")"
            elif not isinstance(v['value'], ArgPattern):
                arg += f": Type_{v['value'].__name__}"
            if v['default'] is Empty:
                arg += ", default=Empty"
            elif v['default'] is not None:
                arg += f", default={v['default']}"
            argument_string += arg + ">"
            i += 1
            if i != length:
                argument_string += sep
        return argument_string

    def __iter__(self) -> Generator[Tuple[str, TAValue, TADefault], Any, None]:
        for k, a in self.argument.items():
            yield k, a.get('value'), a.get('default')

    def __len__(self):
        return len(self.argument)

    def __setitem__(self, key, value):
        if isinstance(value, Iterable):
            values = list(value)
            self.argument[key] = {"value": arg_check(values[0]), "default": arg_check(values[1])}
        else:
            self.argument[key] = {"value": arg_check(value), "default": None}
        return self

    def __setattr__(self, key, value):
        if isinstance(value, Dict):
            super().__setattr__(key, value)
        elif isinstance(value, Iterable):
            values = list(value)
            self.argument[key] = {"value": arg_check(values[0]), "default": arg_check(values[1])}
        else:
            self.argument[key] = {"value": arg_check(value), "default": None}

    def __class_getitem__(cls, item) -> "Args":
        slices = list(item) if not isinstance(item, slice) else [item]
        return cls(*slices)

    def __getitem__(self, item) -> Union["Args", Tuple[TAValue, TADefault]]:
        if isinstance(item, str):
            return self.argument[item].get('value'), self.argument[item].get('default')
        self._check(item if not isinstance(item, slice) else [item])
        return self

    def __merge__(self, other) -> "Args":
        if isinstance(other, Args):
            self.argument.update(other.argument)
            del other
        elif isinstance(other, Iterable):
            values = list(other)
            if not isinstance(values[0], str):
                raise InvalidParam("参数的名字只能是字符串")
            self.argument[values[0]] = {"value": arg_check(values[1]), "default": arg_check(values[2])} if len(
                values) > 2 \
                else {"value": arg_check(values[1]), "default": None}
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
        result = {}
        for k, v in self.argument.items():
            value = v['value']
            default = v['default']
            if isinstance(value, (ArgPattern, _AnyParam)):
                value = value.__getstate__()
            else:
                value = {"type": value.__name__}
            result[k] = {"value": value, "default": default}
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        args = cls()
        for k, v in data.items():
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
        for k, v in state.items():
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


class TemplateCommand:
    """
    命令体基类, 规定基础命令的参数

    Attributes:
        name: 命令名称
        args: 命令参数
        separator: 命令分隔符
        action: 命令动作
        nargs: 参数个数
        help_text: 命令帮助信息
    """
    name: str
    args: Args
    separator: str
    action: ArgAction
    nargs: int
    help_text: str

    def __init__(
            self, name: str,
            args: Optional[Args] = None,
            action: Optional[Union[ArgAction, Callable]] = None,
            **kwargs
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
        self.args = args or Args(**kwargs)
        self.__check_action__(action)
        self.separator = " "
        self.help_text = self.name
        self.nargs = len(self.args.argument)

    def separate(self, sep: str):
        """设置命令头与命令参数的分隔符"""
        self.separator = sep
        return self

    def help(self, help_string: str):
        """预处理 help 文档"""
        setattr(
            self, "help_doc",
            f"# {help_string}\n  {self.name}{self.separator}{self.args.params(self.separator)}\n"
        )
        self.help_text = help_string
        return self

    def __getitem__(self, item):
        self.args.__merge__(Args.__class_getitem__(item))
        self.nargs = len(self.args.argument)
        return self

    def __check_action__(self, action):
        if action:
            if isinstance(action, ArgAction):
                self.action = action
                return
            argument = [
                (name, param.annotation, param.default) for name, param in inspect.signature(action).parameters.items()
            ]
            if len(argument) != len(self.args.argument):
                raise InvalidParam("action 接受的参数个数必须与 Args 里的一致")
            if action.__name__ != "<lambda>":
                for i, k in enumerate(self.args.argument):
                    value = self.args.argument[k]['value']
                    if isinstance(
                            value, ArgPattern
                    ):
                        if value.type_mark != getattr(argument[i][1], "__origin__", argument[i][1]):
                            raise InvalidParam(f"{argument[i][0]}的类型 与 Args 中 '{k}' 接受的类型 {value.type_mark} 不一致")
                    elif isinstance(
                            value, _AnyParam
                    ):
                        if argument[i][1] not in (Empty, Any):
                            raise InvalidParam(f"{argument[i][0]}的类型不能指定为 {argument[i][1]}")
                    elif argument[i][1] != value:
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
        cmd = cls(name, args).separate(data['separator']).help(data['help_text'])
        return cmd

    def __setstate__(self, state):
        self.__init__(
            state['name'], Args.from_dict(state['args'])
        ).separate(state['separator']).help(state['help_text'])
