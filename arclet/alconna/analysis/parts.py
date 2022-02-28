from typing import Union, Optional, List, Any, Dict, Iterable

from .analyser import Analyser
from ..component import Option, Subcommand
from ..exceptions import ParamsUnmatched
from ..types import ArgPattern, AnyParam, AllParam
from ..base import Args, ArgAction


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
    for key in opt_args.argument:
        value = opt_args.argument[key]['value']
        default = opt_args.argument[key]['default']
        may_arg = analyser.next_data(sep)
        if value.__class__ in analyser.arg_handlers:
            analyser.arg_handlers[value.__class__](
                analyser, may_arg, key, value,
                default, nargs, sep, option_dict
            )
        elif value is AnyParam:
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
        elif isinstance(value, Iterable):
            if may_arg not in value:
                analyser.reduce_data(may_arg)
                if default is None:
                    raise ParamsUnmatched(f"param {may_arg} is incorrect")
                may_arg = default
            option_dict[key] = may_arg
        else:
            if may_arg.__class__ is value:
                option_dict[key] = may_arg
            elif default is not None:
                option_dict[key] = default
                analyser.reduce_data(may_arg)
            else:
                analyser.reduce_data(may_arg)
                if may_arg:
                    raise ParamsUnmatched(f"param type {may_arg.__class__} is incorrect")
                else:
                    raise ParamsUnmatched(f"param {key} is required")
    if action:
        option_dict = action(option_dict, analyser.is_raise_exception)
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

    name = analyser.next_data(param.separator)
    if name not in (param.name, param.alias):  # 先匹配选项名称
        raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
    name = param.name.lstrip("-")
    if param.nargs == 0:
        return [name, param.action({}, analyser.is_raise_exception)] if param.action else [name, Ellipsis]
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
    name = analyser.next_data(param.separator)
    if param.name != name:
        raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
    name = name.lstrip("-")
    if param.sub_part_len.stop == 0:
        return [name, param.action({}, analyser.is_raise_exception)] if param.action else [name, Ellipsis]

    subcommand = {}
    args = None
    for _ in param.sub_part_len:
        text = analyser.next_data(param.separator, pop=False)
        try:
            sub_param = param.sub_params.get(text)
        except TypeError:
            sub_param = None
        if not sub_param and text != "" and isinstance(text, str):
            for sp in param.sub_params:
                if text.startswith(getattr(param.sub_params[sp], 'alias', sp)):
                    sub_param = param.sub_params[sp]
                    break
        try:
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
        except ParamsUnmatched:
            if analyser.is_raise_exception:
                raise
            break
    return [name, subcommand]


def analyse_header(
        analyser: Analyser,
) -> str:
    """
    分析命令头部

    Args:
        analyser: 使用的分析器
    Returns:
        head_match: 当命令头内写有正则表达式并且匹配成功的话, 返回匹配结果
    """
    command = analyser.command_header
    separator = analyser.separator
    head_text = analyser.next_data(separator)
    if isinstance(command, ArgPattern):
        if isinstance(head_text, str) and (_head_find := command.find(head_text)):
            analyser.head_matched = True
            return _head_find if _head_find != head_text else True
    else:
        may_command = analyser.next_data(separator)
        if _head_find := command[1].find(may_command) and head_text in command[0]:
            analyser.head_matched = True
            return _head_find if _head_find != head_text else True
    if not analyser.head_matched:
        raise ParamsUnmatched(f"{head_text} does not matched")
