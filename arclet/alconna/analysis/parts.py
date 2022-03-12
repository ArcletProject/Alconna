import re
from typing import Iterable, Union, Optional, List, Any, Dict, cast
import asyncio

from .analyser import Analyser
from ..component import Option, Subcommand
from ..exceptions import ParamsUnmatched, ArgumentMissing
from ..types import ArgPattern, AnyParam, AllParam, Empty
from ..base import Args, ArgAction


def loop() -> asyncio.AbstractEventLoop:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.get_event_loop()


def analyse_args(
        analyser: Analyser,
        opt_args: Args,
        sep: str,
        nargs: int,
        action: Optional[ArgAction] = None,
) -> Dict[str, Any]:
    """
    分析 Args 部分

    Args:
        analyser: 使用的分析器
        opt_args: 目标Args
        sep: 当前命令节点的分隔符
        nargs: Args参数个数
        action: 当前命令节点的ArgAction

    Returns:
        Dict: 解析结果
    """
    option_dict: Dict[str, Any] = {}
    for key, arg in opt_args.argument.items():
        value = arg['value']
        default = arg['default']
        kwonly = arg['kwonly']
        optional = arg['optional']
        may_arg, _str = analyser.next_data(sep)
        if kwonly:
            _kwarg = re.findall(f'^{key}=(.*)$', may_arg)
            if not _kwarg:
                analyser.reduce_data(may_arg)
                if analyser.is_raise_exception:
                    raise ParamsUnmatched(f"{may_arg} missing its key. Do you forget to add '{key}='?")
                continue
            may_arg = _kwarg[0]
            if may_arg == '':
                may_arg, _str = analyser.next_data(sep)
                if _str:
                    analyser.reduce_data(may_arg)
                    if analyser.is_raise_exception:
                        raise ParamsUnmatched(f"param type {may_arg.__class__} is incorrect")
                    continue
        if may_arg in analyser.params:
            analyser.reduce_data(may_arg)
            if default is None:
                if optional:
                    continue
                raise ArgumentMissing(f"param {key} is required")
            else:
                option_dict[key] = None if default is Empty else default
        elif value.__class__ in analyser.arg_handlers:
            analyser.arg_handlers[value.__class__](
                analyser, may_arg, key, value,
                default, nargs, sep, option_dict,
                optional
            )
        elif value is AnyParam:
            if may_arg:
                option_dict[key] = may_arg
        elif value is AllParam:
            rest_data = analyser.recover_raw_data()
            if not rest_data:
                rest_data = [may_arg]
            elif isinstance(rest_data[0], str):
                rest_data[0] = may_arg + sep + rest_data[0]
            else:
                rest_data.insert(0, may_arg)
            option_dict[key] = rest_data
            return option_dict
        else:
            if may_arg.__class__ is value:
                option_dict[key] = may_arg
            elif isinstance(value, type) and isinstance(may_arg, value):
                option_dict[key] = may_arg
            elif default is not None:
                option_dict[key] = None if default is Empty else default
                analyser.reduce_data(may_arg)
            else:
                analyser.reduce_data(may_arg)
                if optional:
                    continue
                if may_arg:
                    raise ParamsUnmatched(f"param type {may_arg.__class__} is incorrect")
                else:
                    raise ArgumentMissing(f"param {key} is required")
    if action:
        result_dict = option_dict.copy()
        kwargs = {}
        varargs = []
        if opt_args.var_keyword:
            kwargs = result_dict.pop(opt_args.var_keyword[0])
            if not isinstance(kwargs, dict):
                kwargs = {opt_args.var_keyword[0]: kwargs}
        if opt_args.var_positional:
            varargs = result_dict.pop(opt_args.var_positional[0])
            if not isinstance(varargs, Iterable):
                varargs = [varargs]
            elif not isinstance(varargs, list):
                varargs = list(varargs)
        if opt_args.var_keyword:
            addition_kwargs = analyser.alconna.local_args.copy()
            addition_kwargs.update(kwargs)
        else:
            addition_kwargs = kwargs
            result_dict.update(analyser.alconna.local_args)
        if action.awaitable:
            if loop().is_running():
                option_dict = cast(Dict, loop().create_task(
                    action.handle_async(result_dict, varargs, addition_kwargs, analyser.is_raise_exception)
                ))
            else:
                option_dict = loop().run_until_complete(
                    action.handle_async(result_dict, varargs, addition_kwargs, analyser.is_raise_exception)
                )
        else:
            option_dict = action.handle(result_dict, varargs, addition_kwargs, analyser.is_raise_exception)
        if opt_args.var_keyword:
            option_dict.update({opt_args.var_keyword[0]: kwargs})
        if opt_args.var_positional:
            option_dict.update({opt_args.var_positional[0]: varargs})
    return option_dict


def analyse_option(
        analyser: Analyser,
        param: Option,
) -> List[Any]:
    """
    分析 Option 部分

    Args:
        analyser: 使用的分析器
        param: 目标Option
    """

    name, _ = analyser.next_data(param.separator)
    if name not in (param.name, param.alias):  # 先匹配选项名称
        raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
    name = param.name.lstrip("-")
    if param.nargs == 0:
        if param.action:
            if param.action.awaitable:
                if loop().is_running():
                    r = loop().create_task(
                        param.action.handle_async(
                            {}, [], analyser.alconna.local_args.copy(), analyser.is_raise_exception
                        )
                    )
                else:
                    r = loop().run_until_complete(
                        param.action.handle_async(
                            {}, [], analyser.alconna.local_args.copy(), analyser.is_raise_exception
                        )
                    )
            else:
                r = param.action.handle({}, [], analyser.alconna.local_args.copy(), analyser.is_raise_exception)
            return [name, r]
        return [name, Ellipsis]
    return [name, analyse_args(analyser, param.args, param.separator, param.nargs, param.action)]


def analyse_subcommand(
        analyser: Analyser,
        param: Subcommand
) -> List[Union[str, Any]]:
    """
    分析 Subcommand 部分

    Args:
        analyser: 使用的分析器
        param: 目标Subcommand
    """
    name, _ = analyser.next_data(param.separator)
    if param.name != name:
        raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
    name = name.lstrip("-")
    if param.sub_part_len.stop == 0:
        if param.action:
            if param.action.awaitable:
                if loop().is_running():
                    r = loop().create_task(
                        param.action.handle_async(
                            {}, [], analyser.alconna.local_args.copy(), analyser.is_raise_exception
                        )
                    )
                else:
                    r = loop().run_until_complete(
                        param.action.handle_async(
                            {}, [], analyser.alconna.local_args.copy(), analyser.is_raise_exception
                        )
                    )
            else:
                r = param.action.handle({}, [], analyser.alconna.local_args.copy(), analyser.is_raise_exception)
            return [name, r]
        return [name, Ellipsis]

    subcommand = {}
    args = None
    need_args = True if param.nargs > 0 else False
    for _ in param.sub_part_len:
        text, _str = analyser.next_data(param.separator, pop=False)
        sub_param = param.sub_params.get(text, None) if _str else Ellipsis
        if not sub_param and text != "":
            for sp in param.sub_params:
                if text.startswith(getattr(param.sub_params[sp], 'alias', sp)):
                    sub_param = param.sub_params[sp]
                    break
        if isinstance(sub_param, Option):
            opt_n, opt_v = analyse_option(analyser, sub_param)
            if not subcommand.get(opt_n):
                subcommand[opt_n] = opt_v
            elif isinstance(subcommand[opt_n], dict):
                subcommand[opt_n] = [subcommand[opt_n], opt_v]
            else:
                subcommand[opt_n].append(opt_v)
        elif not args and (args := analyse_args(analyser, param.args, param.separator, param.nargs, param.action)):
            subcommand.update(args)
    if need_args and not args:
        raise ArgumentMissing(f"\"{name}\" subcommand missed its args")
    return [name, subcommand]


def analyse_header(
        analyser: Analyser,
) -> Union[str, bool]:
    """
    分析命令头部

    Args:
        analyser: 使用的分析器
    Returns:
        head_match: 当命令头内写有正则表达式并且匹配成功的话, 返回匹配结果
    """
    command = analyser.command_header
    separator = analyser.separator
    head_text, _str = analyser.next_data(separator)
    if isinstance(command, ArgPattern):
        if _str and (_head_find := command.find(head_text)):
            analyser.head_matched = True
            return _head_find if _head_find != head_text else True
    else:
        may_command, _str = analyser.next_data(separator)
        if _head_find := command[1].find(may_command) and head_text in command[0]:
            analyser.head_matched = True
            return _head_find if _head_find != head_text else True
    return analyser.head_matched
