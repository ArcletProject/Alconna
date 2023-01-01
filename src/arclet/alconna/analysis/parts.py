from __future__ import annotations

import re
from inspect import isclass
from typing import Iterable, List, Any, TYPE_CHECKING 
from nepattern import AllParam, Empty, BasePattern
from nepattern.util import TPattern

from ..exceptions import ParamsUnmatched, ArgumentMissing, FuzzyMatchSuccess, CompletionTriggered
from ..typing import MultiVar, KeyWordVar
from ..args import Args, Arg
from ..base import Option, Subcommand, OptionResult, SubcommandResult, Sentence
from ..util import levenshtein_norm, split_once
from ..config import config

if TYPE_CHECKING:
    from .analyser import Analyser


def _handle_keyword(
    analyser: Analyser,
    value: KeyWordVar,
    may_arg: Any,
    seps: tuple[str, ...],
    result_dict: dict[str, Any],
    default_val: Any,
    optional: bool,
    key: str | None = None,
):
    if _kwarg := re.match(fr'^([^{value.sep}]+){value.sep}(.*?)$', may_arg):
        key = key or _kwarg[1]
        if (_key := _kwarg[1]) != key:
            analyser.pushback(may_arg)
            if analyser.fuzzy_match and levenshtein_norm(_key, key) >= config.fuzzy_threshold:
                raise FuzzyMatchSuccess(config.lang.common_fuzzy_matched.format(source=_key, target=key))
            if default_val is None and analyser.raise_exception:
                raise ParamsUnmatched(config.lang.common_fuzzy_matched.format(source=_key, target=key))
            result_dict[_key] = None if default_val is Empty else default_val
            return
        if not (_m_arg := _kwarg[2]):
            may_arg, _str = analyser.popitem(seps)
        res = value.base(_kwarg[2], default_val)
        if res.flag != 'valid':
            analyser.pushback(may_arg)
        if res.flag == 'error':
            if optional:
                return
            raise ParamsUnmatched(*res.error.args)
        result_dict[_kwarg[1]] = res.value
        return
    analyser.pushback(may_arg)
    raise ParamsUnmatched(config.lang.args_key_missing.format(target=may_arg, key=key))


def multi_arg_handler(
    analyser: Analyser,
    args: Args,
    arg: Arg,
    result_dict: dict[str, Any],
    nargs: int
):
    seps = arg.separators
    value = arg.value
    key = arg.name
    default = arg.field.default_gen
    kw = value.base.__class__ == KeyWordVar
    _m_rest_arg = nargs - len(result_dict)
    _m_rest_all_param_count = len(analyser.release(seps))
    if not kw and not args.var_keyword or kw and not args.var_positional:
        _loop = _m_rest_all_param_count - (_m_rest_arg - (value.flag == "+"))
    elif not kw:
        _loop = _m_rest_all_param_count - (_m_rest_arg - (args[args.var_keyword].value.flag == "*"))
    else:
        _loop = _m_rest_all_param_count - (_m_rest_arg - (args[args.var_positional].value.flag == "*"))
    if value.length > 0:
        _loop = min(_loop, value.length)
    if kw:
        result = {}
        for _ in range(_loop):
            _m_arg, _m_str = analyser.popitem(seps)
            if not _m_arg:
                continue
            if _m_str and _m_arg in analyser.param_ids:
                analyser.pushback(_m_arg)
                for _ in range(min(len(result), _m_rest_arg - 1)):
                    arg = result.popitem()  # type: ignore
                    analyser.pushback(f'{arg[0]}={arg[1]}')
                break
            try:
                _handle_keyword(analyser, value.base, _m_arg, seps, result, default, False)  # type: ignore
            except ParamsUnmatched:
                break
        if not result:
            if value.flag == '+':
                raise ParamsUnmatched
            result = [default] if default else []
        result_dict[key] = result
    else:
        result = []
        for _ in range(_loop):
            _m_arg, _m_str = analyser.popitem(seps)
            if not _m_arg:
                continue
            if _m_str and (_m_arg in analyser.param_ids or re.match(fr'^(.+)=\s?$', _m_arg)):
                analyser.pushback(_m_arg)
                for _ in range(min(len(result), _m_rest_arg - 1)):
                    analyser.pushback(result.pop(-1))
                break
            if (res := value.base(_m_arg)).flag != 'valid':
                analyser.pushback(_m_arg)
                break
            result.append(res.value)
        if not result:
            if value.flag == '+':
                raise ParamsUnmatched
            result = [default] if default else []
        result_dict[key] = tuple(result)


def analyse_args(analyser: Analyser, args: Args, nargs: int) -> dict[str, Any]:
    """
    分析 Args 部分

    Args:
        analyser: 使用的分析器
        args: 目标Args
        nargs: 目标Args的参数个数

    Returns:
        Dict: 解析结果
    """
    result: dict[str, Any] = {}
    for arg in args.argument:
        analyser.context = arg
        key, value, default_val, optional = arg.name, arg.value, arg.field.default_gen, arg.optional
        seps = arg.separators
        may_arg, _str = analyser.popitem(seps)
        if may_arg in analyser.special:
            raise CompletionTriggered(arg)
        if not may_arg or (_str and may_arg in analyser.param_ids):
            analyser.pushback(may_arg)
            if default_val is not None:
                result[key] = None if default_val is Empty else default_val
            elif not optional:
                raise ArgumentMissing(config.lang.args_missing.format(key=key))
            continue
        if isinstance(value, BasePattern):
            if value.__class__ is MultiVar:
                analyser.pushback(may_arg)
                multi_arg_handler(analyser, args, arg, result, nargs)  # type: ignore
            elif value.__class__ is KeyWordVar:
                _handle_keyword(analyser, value, may_arg, seps, result, default_val, optional, key)  # type: ignore
            else:
                res = value(may_arg, default_val)
                if res.flag != 'valid':
                    analyser.pushback(may_arg)
                if res.flag == 'error':
                    if optional:
                        continue
                    raise ParamsUnmatched(*res.error.args)
                if not key.startswith('_key'):
                    result[key] = res.value
        elif value is AllParam:
            analyser.pushback(may_arg)
            result[key] = analyser.release(seps)
            analyser.current_index = analyser.ndata
            return result
        elif may_arg == value:
            result[key] = may_arg
        elif default_val is not None:
            result[key] = None if default_val is Empty else default_val
        elif not optional:
            raise ParamsUnmatched(config.lang.args_error.format(target=may_arg))
        else:
            continue
    if args.var_keyword:
        kwargs = result[args.var_keyword]
        if not isinstance(kwargs, dict):
            kwargs = {args.var_keyword: kwargs}
        result['$kwargs'] = (kwargs, args.var_keyword)
    if args.var_positional:
        varargs = result[args.var_positional]
        if not isinstance(varargs, Iterable):
            varargs = [varargs]
        elif not isinstance(varargs, list):
            varargs = list(varargs)
        result['$varargs'] = (varargs, args.var_positional)
    if args.keyword_only:
        result['$kwonly'] = {k: v for k, v in result.items() if k in args.keyword_only}
    return result


def analyse_unmatch_params(
    params: Iterable[list[Option] | Sentence | Subcommand],
    text: str,
    is_fuzzy_match: bool = False
):
    for _p in params:
        if isinstance(_p, list):
            res = []
            for _o in _p:
                _may_param = split_once(text, _o.separators)[0]
                if _may_param in _o.aliases or any(map(lambda x: _may_param.startswith(x), _o.aliases)):
                    res.append(_o)
                    continue
                if is_fuzzy_match and levenshtein_norm(_may_param, _o.name) >= config.fuzzy_threshold:
                    raise FuzzyMatchSuccess(config.lang.common_fuzzy_matched.format(source=_may_param, target=_o.name))
            if res:
                return res
        else:
            if (_may_param := split_once(text, _p.separators)[0]) == _p.name:
                return _p
            if is_fuzzy_match and levenshtein_norm(_may_param, _p.name) >= config.fuzzy_threshold:
                raise FuzzyMatchSuccess(config.lang.common_fuzzy_matched.format(source=_may_param, target=_p.name))


def analyse_option(analyser: Analyser, param: Option) -> tuple[str, OptionResult]:
    """
    分析 Option 部分

    Args:
        analyser: 使用的分析器
        param: 目标Option
    """
    analyser.context = param
    if param.requires and analyser.sentences != param.requires:
        raise ParamsUnmatched(f"{param.name}'s required is not '{' '.join(analyser.sentences)}'")
    analyser.sentences = []
    if param.is_compact:
        name, _ = analyser.popitem()
        for al in param.aliases:
            if mat := re.fullmatch(f"{al}(?P<rest>.*?)", name):
                analyser.pushback(mat.groupdict()['rest'], replace=True)
                break
        else:
            raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
    else:
        name, _ = analyser.popitem(param.separators)
        if name not in param.aliases:  # 先匹配选项名称
            raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
    name = param.dest
    res: OptionResult = {"value": None, "args": {}}
    if param.nargs == 0:
        res['value'] = Ellipsis
    else:
        res['args'] = analyse_args(analyser, param.args, param.nargs)
    return name, res


def analyse_subcommand(analyser: Analyser, param: Subcommand) -> tuple[str, SubcommandResult]:
    """
    分析 Subcommand 部分

    Args:
        analyser: 使用的分析器
        param: 目标Subcommand
    """
    analyser.context = param
    if param.requires and analyser.sentences != param.requires:
        raise ParamsUnmatched(f"{param.name}'s required is not '{' '.join(analyser.sentences)}'")
    analyser.sentences = []
    if param.is_compact:
        name, _ = analyser.popitem()
        if not name.startswith(param.name):
            raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
        analyser.pushback(name.lstrip(param.name), replace=True)
    else:
        name, _ = analyser.popitem(param.separators)
        if name != param.name:  # 先匹配选项名称
            raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
    name = param.dest
    res: SubcommandResult = {"value": None, "args": {}, 'options': {}}
    if param.sub_part_len.stop == 0:
        res['value'] = Ellipsis
        return name, res

    args = False
    for _ in param.sub_part_len:
        _text, _str = analyser.popitem(param.separators, move=False)
        if _text in analyser.alconna.namespace_config.builtin_option_name['completion']:
            raise CompletionTriggered(param)
        _param = _param if (_param := (param.sub_params.get(_text) if _str and _text else Ellipsis)) else (
            analyse_unmatch_params(param.sub_params.values(), _text, analyser.fuzzy_match)
        )
        if (not _param or _param is Ellipsis) and not args:
            res['args'] = analyse_args(analyser, param.args, param.nargs)
            args = True
        elif isinstance(_param, List):
            for p in _param:
                _data = analyser.raw_data.copy()
                _index = analyser.current_index
                try:
                    res['options'].setdefault(*analyse_option(analyser, p))
                    break
                except Exception as e:
                    exc = e
                    analyser.raw_data = _data
                    analyser.current_index = _index
                    continue
            else:
                raise exc  # type: ignore  # noqa

    if not args and param.nargs > 0:
        raise ArgumentMissing(config.lang.subcommand_args_missing.format(name=name))
    return name, res


def analyse_header(analyser: Analyser) -> dict[str, str] | bool | None:
    """
    分析命令头部

    Args:
        analyser: 使用的分析器
    Returns:
        head_match: 当命令头内写有正则表达式并且匹配成功的话, 返回匹配结果
    """
    command = analyser.command_header
    head_text, _str = analyser.popitem()
    if isinstance(command, TPattern) and _str and (_head_find := command.fullmatch(head_text)):
        analyser.head_matched = True
        return _head_find.groupdict() or True
    elif isinstance(command, BasePattern) and command(head_text, Empty).success:
        analyser.head_matched = True
        return True
    else:
        may_command, _m_str = analyser.popitem()
        if isinstance(command, List) and _m_str and not _str:
            for _command in command:
                if (_head_find := _command[1].fullmatch(may_command)) and head_text == _command[0]:
                    analyser.head_matched = True
                    return _head_find.groupdict() or True
        if isinstance(command, tuple):
            if not _str and not isclass(head_text) and (
                (isinstance(command[0], list) and (head_text in command[0] or type(head_text) in command[0])) or
                (isinstance(command[0], tuple) and (head_text in command[0][0] or type(head_text) in command[0][0]))
            ):
                if isinstance(command[1], TPattern):
                    if _m_str and (_command_find := command[1].fullmatch(may_command)):
                        analyser.head_matched = True
                        return _command_find.groupdict() or True
                elif command[1](may_command, Empty).success:
                    analyser.head_matched = True
                    return True
            elif _str and isinstance(command[0], tuple) and isinstance(command[0][1], TPattern):
                if _m_str:
                    pat = re.compile(command[0][1].pattern + command[1].pattern)  # type: ignore
                    if _head_find := pat.fullmatch(head_text):
                        analyser.pushback(may_command)
                        analyser.head_matched = True
                        return _head_find.groupdict() or True
                    elif _command_find := pat.fullmatch(head_text + may_command):
                        analyser.head_matched = True
                        return _command_find.groupdict() or True
                elif isinstance(command[1], BasePattern) and (
                    (_head_find := command[0][1].fullmatch(head_text)) and command[1](may_command, Empty).success
                ):
                    analyser.head_matched = True
                    return _head_find.groupdict() or True

    if not analyser.head_matched:
        if _str and analyser.fuzzy_match:
            headers_text = []
            if analyser.alconna.headers and analyser.alconna.headers != [""]:
                for i in analyser.alconna.headers:
                    if isinstance(i, str):
                        headers_text.append(f"{i}{analyser.alconna.command}")
                    else:
                        headers_text.extend((f"{i}", analyser.alconna.command))
            elif analyser.alconna.command:
                headers_text.append(analyser.alconna.command)
            if isinstance(command, (TPattern, BasePattern)):
                source = head_text
            else:
                source = head_text + analyser.separators[0] + str(may_command)
            if source == analyser.alconna.command:
                analyser.head_matched = False
                raise ParamsUnmatched(config.lang.header_error.format(target=head_text))
            for ht in headers_text:
                if levenshtein_norm(source, ht) >= config.fuzzy_threshold:
                    analyser.head_matched = True
                    raise FuzzyMatchSuccess(config.lang.common_fuzzy_matched.format(target=source, source=ht))
        raise ParamsUnmatched(config.lang.header_error.format(target=head_text))
