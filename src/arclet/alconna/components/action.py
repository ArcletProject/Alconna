from __future__ import annotations

from types import LambdaType
from typing import Dict, Callable, Any, TYPE_CHECKING 
from nepattern import AnyOne, AllParam
from dataclasses import dataclass, field, InitVar

from ..args import Args
from ..config import config
from ..exceptions import InvalidParam
from ..util import is_async
from ..model import OptionResult, SubcommandResult
from .behavior import ArparmaBehavior

if TYPE_CHECKING:
    from ..arparma import Arparma
    from ..core import Alconna


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
            if is_async(self.action):
                if config.loop.is_running():
                    config.loop.create_task(self.action(*_varargs, **kwargs))
                    return params
                additional_values = config.loop.run_until_complete(self.action(*_varargs, **kwargs))
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
            raise InvalidParam(config.lang.action_length_error)
        if not isinstance(action, LambdaType):
            for tgt, slf in zip(target_args.argument, args.argument):
                if tgt.value in (AnyOne, AllParam):
                    continue
                if tgt.value != slf.value:
                    raise InvalidParam(config.lang.action_args_error.format(
                        target=tgt.value.origin, key=tgt.name, source=slf.value.origin
                    ))
        return ArgAction(action)


def _exec_args(args: dict[str, Any], func: ArgAction, raise_exc: bool):
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


def _exec(data: OptionResult | SubcommandResult, func: ArgAction, raise_exc: bool):
    return (
        ("args", _exec_args(data.args, func, raise_exc)) if data.args else ("value", func.action())
    )


@dataclass
class ActionHandler(ArparmaBehavior):
    source: InitVar[Alconna]
    main_action: ArgAction | None = field(init=False, default=None)
    options: dict[str, ArgAction] = field(init=False, default_factory=dict)

    def __post_init__(self, source: Alconna):
        self.main_action = source.action
        def _step(src, prefix=None):
            for opt in src.options:
                if opt.action:
                    self.options[(f"{prefix}." if prefix else "") + opt.dest] = opt.action
                if hasattr(opt, "options"):
                    _step(opt, (f"{prefix}." if prefix else "") + opt.dest)

        _step(source)

    def operate(self, interface: Arparma):
        self.before_operate(interface)
        source = interface.source

        if action := self.main_action:
            self.update(interface, "main_args", _exec_args(interface.main_args, action, source.meta.raise_exception))

        for path, action in self.options.items():
            if d := interface.query(path, None):
                end, value = _exec(
                    d, action, source.meta.raise_exception  # type: ignore
                )
                self.update(interface, f"{path}.{end}", value)  # type: ignore
