from __future__ import annotations

import inspect
from types import LambdaType
from typing import Dict, Callable, Any, TYPE_CHECKING 
from nepattern import AnyOne, AllParam, type_parser
from dataclasses import dataclass

from ..args import Args
from ..config import config
from ..exceptions import InvalidParam
from ..util import is_async
from .behavior import ArparmaBehavior

if TYPE_CHECKING:
    from ..arparma import Arparma
    from ..base import SubcommandResult, OptionResult
    from ..core import Alconna


@dataclass
class ArgAction:
    """负责封装action的类"""
    action: Callable[..., Any]

    def handle(
        self,
        option_dict: dict,
        varargs: list | None = None,
        kwargs: dict | None = None,
        raise_exception: bool = False,
    ):
        """
        处理action

        Args:
            option_dict: 参数字典
            varargs: 可变参数
            kwargs: 关键字参数
            raise_exception: 是否抛出异常
        """
        _varargs = list(option_dict.values())
        _varargs.extend(varargs or [])
        kwargs = kwargs or {}
        try:
            if is_async(self.action):
                loop = config.loop
                if loop.is_running():
                    loop.create_task(self.action(*_varargs, **kwargs))
                    return option_dict
                else:
                    additional_values = loop.run_until_complete(self.action(*_varargs, **kwargs))
            else:
                additional_values = self.action(*_varargs, **kwargs)
            if not additional_values:
                return option_dict
            return additional_values if isinstance(additional_values, Dict) else option_dict
        except Exception as e:
            if raise_exception:
                raise e
        return option_dict

    @staticmethod
    def __validator__(action: Callable | ArgAction | None, args: Args):
        if not action:
            return None
        if isinstance(action, ArgAction):
            return action
        if len(args.argument) == 0:
            args.__merge__(args.from_callable(action)[0])
            return ArgAction(action)
        argument = [
            (name, param.annotation, param.default)
            for name, param in inspect.signature(action).parameters.items()
            if name not in ["self", "cls"]
        ]
        if len(argument) != len(args.argument):
            raise InvalidParam(config.lang.action_length_error)
        if not isinstance(action, LambdaType):
            for i, arg in enumerate(args.argument):
                anno = argument[i][1]
                if anno == inspect.Signature.empty:
                    anno = type(argument[i][2]) if argument[i][2] is not inspect.Signature.empty else str
                value = arg.value
                if value in (AnyOne, AllParam):
                    continue
                if value != type_parser(anno):
                    raise InvalidParam(config.lang.action_args_error.format(
                        target=argument[i][0], key=k, source=value.origin  # type: ignore
                    ))
        return ArgAction(action)


def _exec_args(args: dict[str, Any], func: ArgAction, raise_exc: bool):
    result_dict = args.copy()
    kwargs = {}
    kwonly = {}
    varargs = []
    kw_key = None
    var_key = None
    if '$kwargs' in result_dict:
        kwargs, kw_key = result_dict.pop('$kwargs')
        result_dict.pop(kw_key)
    if '$varargs' in result_dict:
        varargs, var_key = result_dict.pop('$varargs')
        result_dict.pop(var_key)
    if '$kwonly' in result_dict:
        kwonly = result_dict.pop('$kwonly')
        for k in kwonly:
            result_dict.pop(k)
    addition_kwargs = {**kwonly, **kwargs}
    res = func.handle(result_dict, varargs, addition_kwargs, raise_exc)
    if kw_key:
        res[kw_key] = kwargs
    if var_key:
        res[var_key] = varargs
    return res


def _exec(data: OptionResult | SubcommandResult, func: ArgAction, raise_exc: bool):
    return (
        ("args", _exec_args(data['args'], func, raise_exc))
        if data['args'] else ("value", func.handle({}, [], {}, raise_exc))
    )


class ActionHandler(ArparmaBehavior):
    
    def __init__(self, source: Alconna):
        self.main_action = source.action
        self.options = {}
        for opt in source.options:
            if opt.action:
                self.options[opt.dest] = opt.action
            if hasattr(opt, "options"):
                for option in opt.options:  # type: ignore
                    if option.action:
                        self.options[f"{opt.dest}.{option.dest}"] = option.action

    def operate(self, interface: Arparma):
        interface.clean()
        source = interface.source

        if action := self.main_action:
            interface.update("main_args", _exec_args(interface.main_args, action, source.meta.raise_exception))

        for path, action in self.options.items():
            if d := interface.query(path, None):
                end, value = _exec(
                    d, action, source.meta.raise_exception  # type: ignore
                )
                interface.update(f"{path}.{end}", value)  # type: ignore

