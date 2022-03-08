import re
from typing import Union, Dict, Any

from ..types import MultiArg, ArgPattern, NonTextElement, PatternToken, AntiArg, Empty, UnionArg
from .analyser import Analyser
from ..exceptions import ParamsUnmatched, ArgumentMissing


def multi_arg_handler(
        analyser: Analyser,
        may_arg: Union[str, NonTextElement],
        key: str,
        value: MultiArg,
        default: Any,
        nargs: int,
        sep: str,
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
    _m_all_args_count = analyser.rest_count(sep) - _m_rest_arg + 1
    analyser.reduce_data(may_arg)
    if value.flag == 'args':
        result = []

        def __putback(data):
            analyser.reduce_data(data)
            for ii in range(min(len(result), _m_rest_arg)):
                analyser.reduce_data(result.pop(-1))

        for i in range(_m_all_args_count):
            _m_arg = analyser.next_data(sep)
            if isinstance(_m_arg, str) and _m_arg in analyser.params:
                __putback(_m_arg)
                break
            if _m_arg_base.__class__ is ArgPattern:
                if not isinstance(_m_arg, str):
                    analyser.reduce_data(_m_arg)
                    break
                _m_arg_find = _m_arg_base.find(_m_arg)
                if not _m_arg_find:
                    analyser.reduce_data(_m_arg)
                    break
                if _m_arg_base.token == PatternToken.REGEX_TRANSFORM and isinstance(_m_arg_find, str):
                    _m_arg_find = _m_arg_base.transform_action(_m_arg_find)
                if _m_arg_find == _m_arg_base.pattern:
                    _m_arg_find = Ellipsis
                result.append(_m_arg_find)
            else:
                if isinstance(_m_arg, str):
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
                arg = result.popitem()
                analyser.reduce_data(arg[0] + '=' + arg[1])

        for i in range(_m_all_args_count):
            _m_arg = analyser.next_data(sep)
            if isinstance(_m_arg, str) and _m_arg in analyser.params:
                __putback(_m_arg)
                break
            if _m_arg_base.__class__ is ArgPattern:
                if not isinstance(_m_arg, str):
                    analyser.reduce_data(_m_arg)
                    break
                _kwarg = re.findall(r'^(.*)=(.*)$', _m_arg)
                if not _kwarg:
                    analyser.reduce_data(_m_arg)
                    break
                _key, _m_arg = _kwarg[0]
                _m_arg_find = _m_arg_base.find(_m_arg)
                if not _m_arg_find:
                    analyser.reduce_data(_m_arg)
                    break
                if _m_arg_base.token == PatternToken.REGEX_TRANSFORM and isinstance(_m_arg_find, str):
                    _m_arg_find = _m_arg_base.transform_action(_m_arg_find)
                if _m_arg_find == _m_arg_base.pattern:
                    _m_arg_find = Ellipsis
                result[_key] = _m_arg_find
            else:
                if isinstance(_m_arg, str):
                    _kwarg = re.findall(r'^(.*)=.*?$', _m_arg)
                    if not _kwarg:
                        __putback(_m_arg)
                        break
                    _key = _kwarg[0]
                    _m_arg = analyser.next_data(sep)
                    if isinstance(_m_arg, str):
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
        may_arg: Union[str, NonTextElement],
        key: str,
        value: AntiArg,
        default: Any,
        nargs: int,
        sep: str,
        result_dict: Dict[str, Any],
        optional: bool
):
    _a_arg_base = value.arg_value
    if _a_arg_base.__class__ is ArgPattern:
        arg_find = _a_arg_base.find(may_arg)
        if not arg_find and isinstance(may_arg, str):
            result_dict[key] = may_arg
        else:
            analyser.reduce_data(may_arg)
            if default is None:
                if optional:
                    return
                raise ParamsUnmatched(f"param {may_arg} is incorrect")
            result_dict[key] = None if default is Empty else default
    else:
        if may_arg.__class__ is not _a_arg_base:
            result_dict[key] = may_arg
        elif default is not None:
            result_dict[key] = None if default is Empty else default
            analyser.reduce_data(may_arg)
        else:
            analyser.reduce_data(may_arg)
            if key in may_arg.optional:
                return
            if may_arg:
                raise ParamsUnmatched(f"param type {may_arg.__class__} is incorrect")
            else:
                raise ArgumentMissing(f"param {key} is required")


def union_arg_handler(
        analyser: Analyser,
        may_arg: Union[str, NonTextElement],
        key: str,
        value: UnionArg,
        default: Any,
        nargs: int,
        sep: str,
        result_dict: Dict[str, Any],
        optional: bool
):
    if not value.anti:
        not_equal = True
        not_match = True
        not_check = True
        if may_arg in value.for_equal:
            not_equal = False

        if not_equal:
            for pat in value.for_match:
                if arg_find := pat.find(may_arg):
                    not_match = False
                    may_arg = arg_find
                    if pat.token == PatternToken.REGEX_TRANSFORM and isinstance(may_arg, str):
                        may_arg = pat.transform_action(may_arg)
                    if may_arg == pat.pattern:
                        may_arg = Ellipsis
                    break
        if not_match:
            for t in value.for_type_check:
                if isinstance(may_arg, t):
                    not_check = False
                    break
        result = all([not_equal, not_match, not_check])
    else:
        equal = False
        match = False
        type_check = False
        if may_arg in value.for_equal:
            equal = True
        for pat in value.for_match:
            if pat.find(may_arg):
                match = True
                break
        for t in value.for_type_check:
            if isinstance(may_arg, t):
                type_check = True
                break

        result = any([equal, match, type_check])

    if result:
        analyser.reduce_data(may_arg)
        if default is None:
            if optional:
                return
            if may_arg:
                raise ParamsUnmatched(f"param {may_arg} is incorrect")
            else:
                raise ArgumentMissing(f"param {key} is required")
        may_arg = None if default is Empty else default
    result_dict[key] = may_arg


def common_arg_handler(
        analyser: Analyser,
        may_arg: Union[str, NonTextElement],
        key: str,
        value: ArgPattern,
        default: Any,
        nargs: int,
        sep: str,
        result_dict: Dict[str, Any],
        optional: bool
):
    arg_find = value.find(may_arg)
    if not arg_find:
        analyser.reduce_data(may_arg)
        if default is None:
            if optional:
                return
            if may_arg:
                raise ParamsUnmatched(f"param {may_arg} is incorrect")
            else:
                raise ArgumentMissing(f"param {key} is required")
        else:
            arg_find = None if default is Empty else default
    if value.token == PatternToken.REGEX_TRANSFORM and isinstance(arg_find, str):
        arg_find = value.transform_action(arg_find)
    if arg_find == value.pattern:
        arg_find = Ellipsis
    result_dict[key] = arg_find
