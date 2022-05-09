import re
from typing import Union, Dict, Any, Set

from .analyser import Analyser
from ..types import MultiArg, ArgPattern, DataUnit, PatternToken, AntiArg, Empty
from ..exceptions import ParamsUnmatched, ArgumentMissing
from ..lang import lang_config


def multi_arg_handler(
        analyser: Analyser,
        may_arg: Union[str, DataUnit],
        key: str,
        value: MultiArg,
        default: Any,
        nargs: int,
        seps: Set[str],
        result_dict: Dict[str, Any],
        optional: bool
):
    _m_arg_base = value.arg_value
    if _m_arg_base.__class__ is ArgPattern:
        if not isinstance(may_arg, str):
            return
    elif isinstance(may_arg, str):
        return
    # 当前args 已经解析 m 个参数， 总共需要 n 个参数，总共剩余p个参数，
    # q = n - m 为剩余需要参数（包括自己）， p - q + 1 为自己可能需要的参数个数
    _m_rest_arg = nargs - len(result_dict) - 1
    _m_all_args_count = analyser.rest_count(seps) - _m_rest_arg + 1
    if value.array_length:
        _m_all_args_count = min(_m_all_args_count, value.array_length)
    analyser.reduce_data(may_arg)
    if value.flag == 'args':
        result = []

        def __putback(data):
            analyser.reduce_data(data)
            for ii in range(min(len(result), _m_rest_arg)):
                analyser.reduce_data(result.pop(-1))

        for i in range(_m_all_args_count):
            _m_arg, _m_str = analyser.next_data(seps)
            if _m_str and _m_arg in analyser.param_ids:
                __putback(_m_arg)
                break
            if _m_arg_base.__class__ is ArgPattern:
                if not _m_str:
                    analyser.reduce_data(_m_arg)
                    break
                _m_arg_find = _m_arg_base.match(_m_arg)
                if not _m_arg_find:
                    analyser.reduce_data(_m_arg)
                    break
                # if _m_arg_base.token == PatternToken.REGEX_TRANSFORM and isinstance(_m_arg_find, str):
                #     _m_arg_find = _m_arg_base.converter(_m_arg_find)
                if _m_arg_find == _m_arg_base.pattern:
                    _m_arg_find = Ellipsis
                result.append(_m_arg_find)
            else:
                if _m_str:
                    __putback(_m_arg)
                    break
                if _m_arg.__class__ is _m_arg_base:
                    result.append(_m_arg)
                elif isinstance(value, type) and isinstance(may_arg, value):
                    result.append(_m_arg)
                else:
                    analyser.reduce_data(_m_arg)
                    break
        if len(result) == 0:
            result = [default] if default else []
        result_dict[key] = tuple(result)
    else:
        result = {}

        def __putback(data):
            analyser.reduce_data(data)
            for ii in range(min(len(result), _m_rest_arg)):
                arg = result.popitem()  # type: ignore
                analyser.reduce_data(arg[0] + '=' + arg[1])

        for i in range(_m_all_args_count):
            _m_arg, _m_str = analyser.next_data(seps)
            if _m_str and _m_arg in analyser.command_params:
                __putback(_m_arg)
                break
            if _m_arg_base.__class__ is ArgPattern:
                if not _m_str:
                    analyser.reduce_data(_m_arg)
                    break
                _kwarg = re.findall(r'^(.*)=(.*)$', _m_arg)
                if not _kwarg:
                    analyser.reduce_data(_m_arg)
                    break
                _key, _m_arg = _kwarg[0]
                _m_arg_find = _m_arg_base.match(_m_arg)
                if not _m_arg_find:
                    analyser.reduce_data(_m_arg)
                    break
                # if _m_arg_base.token == PatternToken.REGEX_TRANSFORM and isinstance(_m_arg_find, str):
                #     _m_arg_find = _m_arg_base.converter(_m_arg_find)
                if _m_arg_find == _m_arg_base.pattern:
                    _m_arg_find = Ellipsis
                result[_key] = _m_arg_find
            else:
                if _m_str:
                    _kwarg = re.findall(r'^(.*)=.*?$', _m_arg)
                    if not _kwarg:
                        __putback(_m_arg)
                        break
                    _key = _kwarg[0]
                    _m_arg, _m_str = analyser.next_data(seps)
                    if _m_str:
                        __putback(_m_arg)
                        break
                    if _m_arg.__class__ is _m_arg_base:
                        result[_key] = _m_arg
                    elif isinstance(value, type) and isinstance(may_arg, value):
                        result[_key] = _m_arg
                    else:
                        analyser.reduce_data(_m_arg)
                        break
                else:
                    analyser.reduce_data(_m_arg)
                    break
        if len(result) == 0:
            result = [default] if default else []
        result_dict[key] = result


def anti_arg_handler(
        analyser: Analyser,
        may_arg: Union[str, DataUnit],
        key: str,
        value: AntiArg,
        default: Any,
        nargs: int,
        seps: Set[str],
        result_dict: Dict[str, Any],
        optional: bool
):
    _a_arg_base = value.arg_value
    if _a_arg_base.__class__ is ArgPattern:
        arg_find = _a_arg_base.match(may_arg)
        if not arg_find:  # and isinstance(may_arg, str):
            result_dict[key] = may_arg
        else:
            analyser.reduce_data(may_arg)
            if default is None:
                if optional:
                    return
                if may_arg:
                    raise ArgumentMissing(lang_config.args_error.format(target=may_arg))
                else:
                    raise ArgumentMissing(lang_config.args_missing.format(key=key))
            result_dict[key] = None if default is Empty else default
    else:
        if may_arg.__class__ is not _a_arg_base:
            result_dict[key] = may_arg
        elif default is not None:
            result_dict[key] = None if default is Empty else default
            analyser.reduce_data(may_arg)
        else:
            analyser.reduce_data(may_arg)
            if optional:
                return
            if may_arg:
                raise ParamsUnmatched(lang_config.args_type_error.format(target=may_arg.__class__))
            else:
                raise ArgumentMissing(lang_config.args_missing.format(key=key))


def common_arg_handler(
        analyser: Analyser,
        may_arg: Union[str, DataUnit],
        key: str,
        value: ArgPattern,
        default: Any,
        nargs: int,
        seps: Set[str],
        result_dict: Dict[str, Any],
        optional: bool
):
    arg_find = value.match(may_arg)
    if not arg_find:
        analyser.reduce_data(may_arg)
        if default is None:
            if optional:
                return
            if may_arg:
                raise ArgumentMissing(lang_config.args_error.format(target=may_arg))
            raise ArgumentMissing(lang_config.args_missing.format(key=key))
        arg_find = None if default is Empty else default
    # if value.token == PatternToken.REGEX_TRANSFORM and isinstance(arg_find, str):
    #     arg_find = value.converter(arg_find)
    if arg_find == value.pattern:
        arg_find = Ellipsis
    result_dict[key] = arg_find
