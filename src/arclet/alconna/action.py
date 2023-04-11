from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import LambdaType
from typing import Any, Callable, Dict
from nepattern import AllParam, AnyOne
from tarina import is_coroutinefunction

from .args import Args
from .exceptions import InvalidParam
from .model import OptionResult, SubcommandResult


@dataclass(init=True, unsafe_hash=True)
class ArgAction:
    """负责封装action的类"""
    action: Callable[..., Any]

    def handle(self, params: dict, varargs: list | None = None, kwargs: dict | None = None, raise_exc: bool = False):
        """
        处理action

        Args:
            params: 参数字典
            varargs: 可变参数
            kwargs: 关键字参数
            raise_exc: 是否抛出异常
        """
        _varargs = list(params.values()) + (varargs or [])
        kwargs = kwargs or {}
        try:
            if is_coroutinefunction(self.action):
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.action(*_varargs, **kwargs))
                    return params
                additional_values = loop.run_until_complete(self.action(*_varargs, **kwargs))
            else:
                additional_values = self.action(*_varargs, **kwargs)
            return additional_values if additional_values and isinstance(additional_values, Dict) else params
        except Exception as e:
            if raise_exc:
                raise e
        return params

    @staticmethod
    def __validator__(action: Callable | ArgAction | None, args: Args):
        if not action:
            return None
        if isinstance(action, ArgAction):
            return action
        if len(args.argument) == 0:
            args.__merge__(args.from_callable(action)[0])
            return ArgAction(action)
        target_args, _ = Args.from_callable(action)
        if len(target_args.argument) != len(args.argument):
            raise InvalidParam(action)
        if not isinstance(action, LambdaType):
            for tgt, slf in zip(target_args.argument, args.argument):
                if tgt.value in (AnyOne, AllParam):
                    continue
                if tgt.value != slf.value:
                    raise ValueError(tgt.value.origin, tgt.name)
        return ArgAction(action)


def exec_args(args: dict[str, Any], func: ArgAction, raise_exc: bool):
    result_dict = args.copy()
    kwargs, kwonly, varargs, kw_key, var_key = {}, {}, [], None, None
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


def exec_(data: OptionResult | SubcommandResult, func: ArgAction, raise_exc: bool):
    return (
        ("args", exec_args(data.args, func, raise_exc)) if data.args else ("value", func.action())
    )
