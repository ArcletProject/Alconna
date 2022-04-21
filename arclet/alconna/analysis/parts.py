import re
from typing import Iterable, Union, Optional, List, Any, Dict, Pattern

from .analyser import Analyser
from ..exceptions import ParamsUnmatched, ArgumentMissing, FuzzyMatchSuccess
from ..types import AnyParam, AllParam, Empty, TypePattern
from ..base import Args, ArgAction, Option, Subcommand
from ..util import levenshtein_norm
from ..manager import command_manager
from ..lang_config import lang_config


def analyse_args(
        analyser: Analyser,
        opt_args: Args,
        nargs: int,
        action: Optional[ArgAction] = None,
) -> Dict[str, Any]:
    """
    分析 Args 部分

    Args:
        analyser: 使用的分析器
        opt_args: 目标Args
        nargs: Args参数个数
        action: 当前命令节点的ArgAction

    Returns:
        Dict: 解析结果
    """
    option_dict: Dict[str, Any] = {}
    sep = opt_args.separator
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
                if analyser.alconna.is_fuzzy_match and (k := may_arg.split('=')[0]) != may_arg:
                    if levenshtein_norm(k, key) >= 0.7:
                        raise FuzzyMatchSuccess(lang_config.common_fuzzy_matched.format(source=k, target=key))
                if default is None and analyser.is_raise_exception:
                    raise ParamsUnmatched(lang_config.args_key_missing.format(target=may_arg, key=key))
                else:
                    option_dict[key] = None if default is Empty else default
                continue
            may_arg = _kwarg[0]
            if may_arg == '':
                may_arg, _str = analyser.next_data(sep)
                if _str:
                    analyser.reduce_data(may_arg)
                    if default is None and analyser.is_raise_exception:
                        raise ParamsUnmatched(lang_config.args_type_error.format(target=may_arg.__class__))
                    else:
                        option_dict[key] = None if default is Empty else default
                    continue
        if may_arg in analyser.param_ids:
            analyser.reduce_data(may_arg)
            if default is None:
                if optional:
                    continue
                raise ArgumentMissing(lang_config.args_missing.format(key=key))
            else:
                option_dict[key] = None if default is Empty else default
        elif value.__class__ in analyser.arg_handlers:
            analyser.arg_handlers[value.__class__](
                analyser, may_arg, key, value, default, nargs, sep, option_dict, optional
            )
        elif value.__class__ is TypePattern:
            arg_find = value.match(may_arg)
            if not arg_find:
                analyser.reduce_data(may_arg)
                if default is None:
                    if optional:
                        continue
                    if may_arg:
                        raise ArgumentMissing(lang_config.args_error.format(target=may_arg))
                    else:
                        raise ArgumentMissing(lang_config.args_missing.format(key=key))
                else:
                    arg_find = None if default is Empty else default
            option_dict[key] = arg_find
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
                    raise ParamsUnmatched(lang_config.args_type_error.format(target=may_arg.__class__))
                else:
                    raise ArgumentMissing(lang_config.args_missing.format(key=key))
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
    if param.is_compact:
        name, _ = analyser.next_data()
        for al in param.aliases:
            if name.startswith(al):
                analyser.reduce_data(name.lstrip(al), replace=True)
                break
        else:
            raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
    else:
        name, _ = analyser.next_data(param.separator)
        if name not in param.aliases:  # 先匹配选项名称
            raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
    name = param.name.lstrip("-")
    if param.nargs == 0:
        if param.action:
            return [name, param.action.handle({}, [], analyser.alconna.local_args.copy(), analyser.is_raise_exception)]
        return [name, Ellipsis]
    return [name, analyse_args(analyser, param.args, param.nargs, param.action)]


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
    if param.is_compact:
        name, _ = analyser.next_data()
        if name.startswith(param.name):
            analyser.reduce_data(name.lstrip(param.name), replace=True)
        else:
            raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
    else:
        name, _ = analyser.next_data(param.separator)
        if name != param.name:  # 先匹配选项名称
            raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
    name = name.lstrip("-")
    if param.sub_part_len.stop == 0:
        if param.action:
            return [name, param.action.handle({}, [], analyser.alconna.local_args.copy(), analyser.is_raise_exception)]
        return [name, Ellipsis]

    subcommand = {}
    args = None
    need_args = True if param.nargs > 0 else False
    for _ in param.sub_part_len:
        text, _str = analyser.next_data(param.separator, pop=False)
        sub_param = param.sub_params.get(text, None) if _str else Ellipsis
        if not sub_param and text != "":
            for sp in param.sub_params:
                _may_param = text.split(param.sub_params[sp].separator)[0]
                if _may_param in param.sub_params[sp].aliases:
                    _param = param.sub_params[sp]
                    break
                if analyser.alconna.is_fuzzy_match and levenshtein_norm(_may_param, sp) >= 0.7:
                    raise FuzzyMatchSuccess(lang_config.common_fuzzy_matched.format(source=_may_param, target=sp))
        if isinstance(sub_param, Option):
            opt_n, opt_v = analyse_option(analyser, sub_param)
            if not subcommand.get(opt_n):
                subcommand[opt_n] = opt_v
            elif isinstance(subcommand[opt_n], dict):
                subcommand[opt_n] = [subcommand[opt_n], opt_v]
            else:
                subcommand[opt_n].append(opt_v)
        elif not args and (args := analyse_args(analyser, param.args, param.nargs, param.action)):
            subcommand.update(args)
    if need_args and not args:
        raise ArgumentMissing(lang_config.subcommand_args_missing.format(name=name))
    return [name, subcommand]


def analyse_header(
        analyser: Analyser,
) -> Union[Dict[str, Any], bool, None]:
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
    if isinstance(command, Pattern):
        if _str and (_head_find := command.match(head_text)):
            analyser.head_matched = True
            return _head_find.groupdict() or True
    else:
        may_command, _m_str = analyser.next_data(separator)
        if _m_str:
            if isinstance(command, List) and not _str:
                for _command in command:
                    if (_head_find := _command[1].match(may_command)) and head_text == _command[0]:
                        analyser.head_matched = True
                        return _head_find.groupdict() or True
            elif isinstance(command[0], list) and not _str:
                if (_head_find := command[1].match(may_command)) and head_text in command[0]:  # type: ignore
                    analyser.head_matched = True
                    return _head_find.groupdict() or True
            elif _str:
                if (_command_find := command[1].match(may_command)) and (  # type: ignore
                        _head_find := command[0][1].match(head_text)
                ):
                    analyser.head_matched = True
                    return _command_find.groupdict() or True
            else:
                if (_command_find := command[1].match(may_command)) and head_text in command[0][0]:  # type: ignore
                    analyser.head_matched = True
                    return _command_find.groupdict() or True

    if not analyser.head_matched:
        if _str and analyser.alconna.is_fuzzy_match:
            headers_text = []
            if analyser.alconna.headers and analyser.alconna.headers != [""]:
                for i in analyser.alconna.headers:
                    if isinstance(i, str):
                        headers_text.append(i + analyser.alconna.command)
                    else:
                        headers_text.extend((f"{i}", analyser.alconna.command))
            elif analyser.alconna.command:
                headers_text.append(analyser.alconna.command)
            if isinstance(command, Pattern):
                source = head_text
            else:
                source = head_text + analyser.separator + str(may_command)  # noqa
            if command_manager.get_command(source):
                analyser.head_matched = False
                raise ParamsUnmatched(lang_config.header_error.format(target=head_text))
            for ht in headers_text:
                if levenshtein_norm(source, ht) >= 0.7:
                    analyser.head_matched = True
                    raise FuzzyMatchSuccess(lang_config.common_fuzzy_matched.format(target=source, source=ht))
        raise ParamsUnmatched(lang_config.header_error.format(target=head_text))
