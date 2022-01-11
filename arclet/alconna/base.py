"""Alconna 的基础内容相关"""


import re
import inspect
from typing import Union, Any, Optional, Callable, Tuple, Type, Dict, Iterable, Generator, overload
from .exceptions import InvalidParam
from .types import ArgPattern, _AnyParam, Empty, NonTextElement
from .util import arg_check
from .actions import ArgAction

TAValue = Union[ArgPattern, Type[NonTextElement], _AnyParam]
TADefault = Union[str, NonTextElement, Empty]
TArgs = Dict[str, Union[TAValue, TADefault]]


class Args:
    """对命令参数的封装"""
    argument: Dict[str, TArgs]

    __slots__ = ["argument"]

    @overload
    def __init__(self, *args: Union[slice, tuple], **kwargs: ...):
        ...

    def __init__(self, *args: ..., **kwargs: TAValue):
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

            value = arg_check(value)
            if value is Empty:
                raise InvalidParam("参数值不能为Empty")

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
            elif not isinstance(v['value'], ArgPattern):
                arg += f": Type_{v['value'].__name__}"
            if v['default'] is Empty:
                arg += " default: Empty"
            elif v['default'] is not None:
                arg += f" default: {v['default']}"
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


class TemplateCommand:
    """命令体基类, 规定基础命令的参数"""
    name: str
    args: Args
    separator: str = " "
    action: ArgAction

    def __init__(
            self, name: str,
            args: Optional[Args] = None,
            actions: Optional[Union[ArgAction, Callable]] = None,
            **kwargs
    ):
        if name == "":
            raise InvalidParam("该指令的名字不能为空")
        if re.match(r"^[`~?/.,<>;\':\"|!@#$%^&*()_+=\[\]}{]+.*$", name):
            raise InvalidParam("该指令的名字含有非法字符")
        self.name = name
        self.args = args or Args(**kwargs)
        self.__check_action__(actions)

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
        return self

    def __getitem__(self, item):
        self.args.__merge__(Args.__class_getitem__(item))
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
            self.action = ArgAction.set_action(action)
        else:
            self.action = action

    def __repr__(self):
        return f"<{self.name}: args={self.args}>"
