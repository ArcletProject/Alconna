import inspect
from types import LambdaType
from typing import Optional, Dict, List, Callable, Any, TYPE_CHECKING, Union
from nepattern import AnyOne, AllParam, type_parser
from dataclasses import dataclass

from ..args import Args
from ..config import config
from ..exceptions import InvalidParam
from ..util import is_async
from .behavior import ArpamarBehavior

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
        varargs: Optional[List] = None,
        kwargs: Optional[Dict] = None,
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
    def __validator__(action: Union[Callable, "ArgAction", None], args: "Args"):
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


def _exec_args(args: Dict[str, Any], func: ArgAction, source: 'Alconna'):
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
    res = func.handle(result_dict, varargs, addition_kwargs, source.meta.raise_exception)
    if kw_key:
        res[kw_key] = kwargs
    if var_key:
        res[var_key] = varargs
    return res


def _exec(data: Union['OptionResult', 'SubcommandResult'], func: ArgAction, source: 'Alconna'):
    return (
        ("args", _exec_args(data['args'], func, source))
        if data['args'] else ("value", func.handle({}, [], {}, source.meta.raise_exception))
    )


class ActionHandler(ArpamarBehavior):
    def operate(self, interface: "Arparma"):
        interface.clean()
        source = interface.source

        if action := source.action_list['main']:
            interface.update("main_args", _exec_args(interface.main_args, action, source))

        for path, action in source.action_list['options'].items():
            if d := interface.query(path, None):
                end, value = _exec(d, action, source)
                interface.update(f"{path}.{end}", value)  # type: ignore

        for path, action in source.action_list['subcommands'].items():
            if d := interface.query(path, None):
                end, value = _exec(d, action, source)
                interface.update(f"{path}.{end}", value)  # type: ignore
