import inspect
from types import LambdaType
from typing import Optional, Dict, List, Callable, Any, Sequence, TYPE_CHECKING, Union
from nepattern import AnyOne, AllParam, type_parser

from ..args import Args
from ..config import config
from ..exceptions import InvalidParam
from ..util import is_async
from .behavior import ArpamarBehavior

if TYPE_CHECKING:
    from ..arpamar import Arpamar
    from ..base import SubcommandResult, OptionResult
    from ..core import Alconna


class ArgAction:
    """
    负责封装action的类
    """
    action: Callable[..., Any]

    def __init__(self, action: Callable):
        """ArgAction的构造函数"""
        self.action = action

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
            if name not in ["self", "cls", "option_dict", "exception_in_time"]
        ]
        if len(argument) != len(args.argument):
            raise InvalidParam(config.lang.action_length_error)
        if not isinstance(action, LambdaType):
            for i, k in enumerate(args.argument):
                anno = argument[i][1]
                if anno == inspect.Signature.empty:
                    anno = type(argument[i][2]) if argument[i][2] is not inspect.Signature.empty else str
                value = args.argument[k]['value']
                if value in (AnyOne, AllParam):
                    continue
                if value != type_parser(anno, args.extra):
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
    if '__kwargs__' in result_dict:
        kwargs, kw_key = result_dict.pop('__kwargs__')
        result_dict.pop(kw_key)
    if '__varargs__' in result_dict:
        varargs, var_key = result_dict.pop('__varargs__')
        result_dict.pop(var_key)
    if '__kwonly__' in result_dict:
        kwonly = result_dict.pop('__kwonly__')
        for k in kwonly:
            result_dict.pop(k)
    if kwargs:
        addition_kwargs = source.local_args.copy()
        addition_kwargs.update(kwargs)
        addition_kwargs.update(kwonly)
    else:
        addition_kwargs = {**kwonly, **kwargs}
        result_dict.update(source.local_args)
    res = func.handle(result_dict, varargs, addition_kwargs, source.is_raise_exception)
    if kw_key:
        res[kw_key] = kwargs
    if var_key:
        res[var_key] = varargs
    args.update(res)


def _exec(data: Union['OptionResult', 'SubcommandResult'], func: ArgAction, source: 'Alconna'):
    if not data['args']:
        data['value'] = func.handle(
            {}, [], source.local_args.copy(), source.is_raise_exception
        )
        return
    _exec_args(data['args'], func, source)


class ActionHandler(ArpamarBehavior):
    def operate(self, interface: "Arpamar"):
        interface.clean()
        source = interface.source

        if action := source.action_list['main']:
            _exec_args(interface.main_args, action, source)

        for path, action in source.action_list['options'].items():
            if d := interface.query(path, None):
                _exec(d, action, source)  # type: ignore
        for path, action in source.action_list['subcommands'].items():
            if d := interface.query(path, None):
                _exec(d, action, source)  # type: ignore
