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
    """负责挂载 `action` 并处理 `Args` 解析结果

    Attributes:
        action (Callable[..., Any]): 挂载的 action, 其参数的个数, 名称, 类型必须与 Args 一致
    """
    action: Callable[..., Any]

    def handle(self, params: dict, varargs: list | None = None, kwargs: dict | None = None, raise_exc: bool = False):
        """处理 `Args` 解析结果

        Args:
            params (dict): 一般的参数结果
            varargs (Optional[list], optional): 可变参数结果
            kwargs (Optional[dict], optional): 关键字参数结果
            raise_exc (bool, optional): 是否抛出异常
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
        """验证 `action` 是否合法

        Args:
            action (Callable | ArgAction | None): 待验证的 action
            args (Args): 参数列表

        Raises:
            InvalidParam: action 参数个数与 args 不一致
            ValueError: action 参数类型与 args 不一致
        """
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
    """处理 `Args` 解析结果并传入 `action`

    Args:
        args (dict[str, Any]): 参数结果
        func (ArgAction): 使用的 action
        raise_exc (bool): 是否抛出异常
    """
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
    """处理 `OptionResult` 或 `SubcommandResult`

    Args:
        data (OptionResult | SubcommandResult): 选项解析结果或子命令解析结果.
        func (ArgAction): 使用的 action.
        raise_exc (bool): 是否抛出异常.

    """
    return (
        ("args", exec_args(data.args, func, raise_exc)) if data.args else ("value", func.action())
    )
