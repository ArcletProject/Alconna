import re
from typing import Iterable, Union, List, Any, Dict, Tuple
from nepattern import AllParam, Empty, BasePattern
from nepattern.util import TPattern

from .analyser import Analyser
from ..exceptions import ParamsUnmatched, ArgumentMissing, FuzzyMatchSuccess
from ..typing import MultiArg
from ..args import Args
from ..base import Option, Subcommand, OptionResult, SubcommandResult, Sentence
from ..util import levenshtein_norm, split_once
from ..config import config


def multi_arg_handler(
    analyser: Analyser,
    args: Args,
    may_arg: Union[str, Any],
    key: str,
    value: MultiArg,
    default: Any,
    result_dict: Dict[str, Any]
):
    # 当前args 已经解析 m 个参数， 总共需要 n 个参数，总共剩余p个参数，
    # q = n - m 为剩余需要参数（包括自己）， p - q + 1 为自己可能需要的参数个数
    nargs = len(args.argument)
    seps = args.separators
    if value.flag == 'args' and args.var_keyword:
        nargs -= 1
    elif value.flag == 'kwargs' and args.var_positional:
        nargs -= 1
    _m_rest_arg = nargs - len(result_dict) - 1
    _m_all_args_count = len(analyser.release(seps)) - _m_rest_arg + 1
    if value.array_length:
        _m_all_args_count = min(_m_all_args_count, value.array_length)
    analyser.pushback(may_arg)
    if value.flag == 'args':
        result = []
        for i in range(_m_all_args_count):
            _m_arg, _m_str = analyser.popitem(seps)
            if not _m_arg:
                continue
            if _m_str and (_m_arg in analyser.param_ids or re.match(r'^([^=]+)=\s?$', _m_arg)):
                analyser.pushback(_m_arg)
                for ii in range(min(len(result), _m_rest_arg)):
                    analyser.pushback(result.pop(-1))
                break
            if (res := value.validate(_m_arg)).flag != 'valid':
                analyser.pushback(_m_arg)
                break
            result.append(res.value)
        if len(result) == 0:
            result = [default] if default else []
        result_dict[key] = tuple(result)
    else:
        result = {}

        def __putback(data):
            analyser.pushback(data)
            for _ in range(min(len(result), _m_rest_arg)):
                arg = result.popitem()  # type: ignore
                analyser.pushback(f'{arg[0]}={arg[1]}')

        for i in range(_m_all_args_count):
            _m_arg, _m_str = analyser.popitem(seps)
            if not _m_arg:
                continue
            if not _m_str:
                analyser.pushback(_m_arg)
                break
            if _m_str and _m_arg in analyser.command_params:
                __putback(_m_arg)
                break
            if _kwarg := re.match(r'^([^=]+)=([^=]+?)$', _m_arg):
                _m_arg = _kwarg.group(2)
                if (res := value.validate(_m_arg)).flag != 'valid':
                    analyser.pushback(_m_arg)
                    break
                result[_kwarg.group(1)] = res.value
            elif _kwarg := re.match(r'^([^=]+)=\s?$', _m_arg):
                _m_arg, _m_str = analyser.popitem(seps)
                if (res := value.validate(_m_arg)).flag != 'valid':
                    __putback(_m_arg)
                    break
                result[_kwarg.group(1)] = res.value
            else:
                analyser.pushback(_m_arg)
                break
        if len(result) == 0:
            result = [default] if default else []
        result_dict[key] = result


def analyse_args(analyser: Analyser, args: Args) -> Dict[str, Any]:
    """
    分析 Args 部分

    Args:
        analyser: 使用的分析器
        args: 目标Args

    Returns:
        Dict: 解析结果
    """
    option_dict: Dict[str, Any] = {}
    seps = args.separators
    for key, arg in args.argument.items():
        value = arg['value']
        default = arg['default']
        default_val = default.default_gen
        optional = arg['optional']
        may_arg, _str = analyser.popitem(seps)
        if not may_arg or (_str and may_arg in analyser.param_ids):
            analyser.pushback(may_arg)
            if default_val is None:
                if optional:
                    continue
                raise ArgumentMissing(config.lang.args_missing.format(key=key))
            option_dict[key] = None if default_val is Empty else default_val
            continue
        if arg['kwonly']:
            _kwarg = re.findall(f'^{key}=(.*)$', may_arg)
            if not _kwarg:
                analyser.pushback(may_arg)
                if analyser.alconna.is_fuzzy_match and (k := may_arg.split('=')[0]) != may_arg:
                    if levenshtein_norm(k, key) >= config.fuzzy_threshold:
                        raise FuzzyMatchSuccess(config.lang.common_fuzzy_matched.format(source=k, target=key))
                if default_val is None and analyser.is_raise_exception:
                    raise ParamsUnmatched(config.lang.args_key_missing.format(target=may_arg, key=key))
                option_dict[key] = None if default_val is Empty else default_val
                continue
            may_arg = _kwarg[0]
            if may_arg == '':
                may_arg, _str = analyser.popitem(seps)
                if _str:
                    analyser.pushback(may_arg)
                    if default_val is None and analyser.is_raise_exception:
                        raise ParamsUnmatched(config.lang.args_type_error.format(target=may_arg.__class__))
                    option_dict[key] = None if default_val is Empty else default_val
                    continue
        if isinstance(value, BasePattern):
            if value.__class__ is MultiArg:
                multi_arg_handler(analyser, args, may_arg, key, value, default_val, option_dict)  # type: ignore
            else:
                res = value.invalidate(may_arg, default_val) if value.anti else value.validate(may_arg, default_val)
                if res.flag != 'valid':
                    analyser.pushback(may_arg)
                if res.flag == 'error':
                    if optional:
                        continue
                    raise ParamsUnmatched(*res.error.args)
                if key[0] != '$':
                    option_dict[key] = res.value
        elif value is AllParam:
            analyser.pushback(may_arg)
            option_dict[key] = analyser.release()
            analyser.current_index = analyser.ndata
            analyser.content_index = 0
            return option_dict
        elif may_arg == value:
            option_dict[key] = may_arg
        elif default_val is None:
            if optional:
                continue
            raise ParamsUnmatched(config.lang.args_error.format(target=may_arg))
        else:
            option_dict[key] = None if default_val is Empty else default_val
    if args.var_keyword:
        kwargs = option_dict[args.var_keyword]
        if not isinstance(kwargs, dict):
            kwargs = {args.var_keyword: kwargs}
        option_dict['__kwargs__'] = (kwargs, args.var_keyword)
    if args.var_positional:
        varargs = option_dict[args.var_positional]
        if not isinstance(varargs, Iterable):
            varargs = [varargs]
        elif not isinstance(varargs, list):
            varargs = list(varargs)
        option_dict['__varargs__'] = (varargs, args.var_positional)
    if args.keyword_only:
        option_dict['__kwonly__'] = {k: v for k, v in option_dict.items() if k in args.keyword_only}
    return option_dict


def analyse_unmatch_params(
        params: Iterable[Union[List[Option], Sentence, Subcommand]],
        text: str,
        is_fuzzy_match: bool = False
):
    for _p in params:
        if isinstance(_p, list):
            res = []
            for _o in _p:
                _may_param = split_once(text, tuple(_o.separators))[0]
                if _may_param in _o.aliases or any(map(lambda x: _may_param.startswith(x), _o.aliases)):
                    res.append(_o)
                    continue
                if is_fuzzy_match and levenshtein_norm(_may_param, _o.name) >= config.fuzzy_threshold:
                    raise FuzzyMatchSuccess(config.lang.common_fuzzy_matched.format(source=_may_param, target=_o.name))
            if res:
                return res
        else:
            if (_may_param := split_once(text, tuple(_p.separators))[0]) == _p.name:
                return _p
            if is_fuzzy_match and levenshtein_norm(_may_param, _p.name) >= config.fuzzy_threshold:
                raise FuzzyMatchSuccess(config.lang.common_fuzzy_matched.format(source=_may_param, target=_p.name))


def analyse_option(analyser: Analyser, param: Option) -> Tuple[str, OptionResult]:
    """
    分析 Option 部分

    Args:
        analyser: 使用的分析器
        param: 目标Option
    """
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
        res['args'] = analyse_args(analyser, param.args)
    return name, res


def analyse_subcommand(analyser: Analyser, param: Subcommand) -> Tuple[str, SubcommandResult]:
    """
    分析 Subcommand 部分

    Args:
        analyser: 使用的分析器
        param: 目标Subcommand
    """
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
        _param = _param if (_param := (param.sub_params.get(_text) if _str and _text else Ellipsis)) else (
            analyse_unmatch_params(param.sub_params.values(), _text, analyser.alconna.is_fuzzy_match)
        )
        if (not _param or _param is Ellipsis) and not args:
            res['args'] = analyse_args(analyser, param.args)
            args = True
        elif isinstance(_param, List):
            for p in _param:
                _current_index = analyser.current_index
                _content_index = analyser.content_index
                try:
                    res['options'].setdefault(*analyse_option(analyser, p))
                    break
                except Exception as e:
                    exc = e
                    analyser.current_index = _current_index
                    analyser.content_index = _content_index
                    continue
            else:
                raise exc  # type: ignore  # noqa

    if not args and param.nargs > 0:
        raise ArgumentMissing(config.lang.subcommand_args_missing.format(name=name))
    return name, res


def analyse_header(analyser: Analyser) -> Union[Dict[str, Any], bool, None]:
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
    elif isinstance(command, BasePattern) and (_head_find := command.validate(head_text, Empty).value):
        analyser.head_matched = True
        return _head_find or True
    else:
        may_command, _m_str = analyser.popitem()
        if isinstance(command, List) and _m_str and not _str:
            for _command in command:
                if (_head_find := _command[1].fullmatch(may_command)) and head_text == _command[0]:
                    analyser.head_matched = True
                    return _head_find.groupdict() or True
        if isinstance(command, tuple):
            if not _str and (
                (isinstance(command[0], list) and head_text in command[0]) or
                (isinstance(command[0], tuple) and head_text in command[0][0])
            ):
                if isinstance(command[1], TPattern):
                    if _m_str and (_command_find := command[1].fullmatch(may_command)):
                        analyser.head_matched = True
                        return _command_find.groupdict() or True
                elif _command_find := command[1].validate(may_command, Empty).value:
                    analyser.head_matched = True
                    return _command_find or True
            elif _str and isinstance(command[0][1], TPattern):
                if _m_str:
                    pat = re.compile(command[0][1].pattern + command[1].pattern)  # type: ignore
                    if _head_find := pat.fullmatch(head_text):
                        analyser.pushback(may_command)
                        analyser.head_matched = True
                        return _head_find.groupdict() or True
                    elif _command_find := pat.fullmatch(head_text + may_command):
                        analyser.head_matched = True
                        return _command_find.groupdict() or True
                elif isinstance(command[1], BasePattern) and (_head_find := command[0][1].fullmatch(head_text)) and (
                    _command_find := command[1].validate(may_command, Empty).value
                ):
                    analyser.head_matched = True
                    return _command_find or True

    if not analyser.head_matched:
        if _str and analyser.alconna.is_fuzzy_match:
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
                source = head_text + analyser.separators.copy().pop() + str(may_command)  # type: ignore  # noqa
            if source == analyser.alconna.command:
                analyser.head_matched = False
                raise ParamsUnmatched(config.lang.header_error.format(target=head_text))
            for ht in headers_text:
                if levenshtein_norm(source, ht) >= config.fuzzy_threshold:
                    analyser.head_matched = True
                    raise FuzzyMatchSuccess(config.lang.common_fuzzy_matched.format(target=source, source=ht))
        raise ParamsUnmatched(config.lang.header_error.format(target=head_text))
