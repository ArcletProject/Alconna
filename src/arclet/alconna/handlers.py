from __future__ import annotations

import re
from inspect import isclass
from typing import TYPE_CHECKING, Any, Iterable, List

from nepattern import AllParam, BasePattern, Empty
from nepattern.util import TPattern

from .args import Arg, Args
from .base import Option, Subcommand
from .config import config
from .exceptions import ArgumentMissing, CompletionTriggered, FuzzyMatchSuccess, ParamsUnmatched, SpecialOptionTriggered
from .model import OptionResult, Sentence
from .output import output_manager
from .typing import KeyWordVar, MultiVar
from .util import levenshtein_norm, split_once

if TYPE_CHECKING:
    from .analyser import Analyser, SubAnalyser


def _handle_keyword(
    analyser: SubAnalyser,
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
            analyser.container.pushback(may_arg)
            if analyser.fuzzy_match and levenshtein_norm(_key, key) >= config.fuzzy_threshold:
                raise FuzzyMatchSuccess(config.lang.common_fuzzy_matched.format(source=_key, target=key))
            if default_val is None:
                raise ParamsUnmatched(config.lang.common_fuzzy_matched.format(source=_key, target=key))
            result_dict[_key] = None if default_val is Empty else default_val
            return
        if not (_m_arg := _kwarg[2]):
            may_arg, _str = analyser.container.popitem(seps)
        res = value.base(_kwarg[2], default_val)
        if res.flag != 'valid':
            analyser.container.pushback(may_arg)
        if res.flag == 'error':
            if optional:
                return
            raise ParamsUnmatched(*res.error.args)
        result_dict[_kwarg[1]] = res.value
        return
    analyser.container.pushback(may_arg)
    raise ParamsUnmatched(config.lang.args_key_missing.format(target=may_arg, key=key))


def multi_arg_handler(
    analyser: SubAnalyser,
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
    _m_rest_all_param_count = len(analyser.container.release(seps))
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
            _m_arg, _m_str = analyser.container.popitem(seps)
            if not _m_arg:
                continue
            if _m_str and _m_arg in analyser.container.param_ids:
                analyser.container.pushback(_m_arg)
                for _ in range(min(len(result), _m_rest_arg - 1)):
                    arg = result.popitem()  # type: ignore
                    analyser.container.pushback(f'{arg[0]}={arg[1]}')
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
            _m_arg, _m_str = analyser.container.popitem(seps)
            if not _m_arg:
                continue
            if _m_str and (_m_arg in analyser.container.param_ids or re.match(fr'^(.+)=\s?$', _m_arg)):
                analyser.container.pushback(_m_arg)
                for _ in range(min(len(result), _m_rest_arg - 1)):
                    analyser.container.pushback(result.pop(-1))
                break
            if (res := value.base(_m_arg)).flag != 'valid':
                analyser.container.pushback(_m_arg)
                break
            result.append(res.value)
        if not result:
            if value.flag == '+':
                raise ParamsUnmatched
            result = [default] if default else []
        result_dict[key] = tuple(result)


def analyse_args(analyser: SubAnalyser, args: Args, nargs: int) -> dict[str, Any]:
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
        analyser.container.context = arg
        key, value, default_val, optional = arg.name, arg.value, arg.field.default_gen, arg.optional
        seps = arg.separators
        may_arg, _str = analyser.container.popitem(seps)
        if _str and may_arg in analyser.special:
            raise CompletionTriggered(arg)
        if not may_arg or (_str and may_arg in analyser.container.param_ids):
            analyser.container.pushback(may_arg)
            if default_val is not None:
                result[key] = None if default_val is Empty else default_val
            elif not optional:
                raise ArgumentMissing(config.lang.args_missing.format(key=key))
            continue
        if isinstance(value, BasePattern):
            if value.__class__ is MultiVar:
                analyser.container.pushback(may_arg)
                multi_arg_handler(analyser, args, arg, result, nargs)  # type: ignore
            elif value.__class__ is KeyWordVar:
                _handle_keyword(analyser, value, may_arg, seps, result, default_val, optional, key)  # type: ignore
            else:
                res = value(may_arg, default_val)
                if res.flag != 'valid':
                    analyser.container.pushback(may_arg)
                if res.flag == 'error':
                    if optional:
                        continue
                    raise ParamsUnmatched(*res.error.args)
                if not key.startswith('_key'):
                    result[key] = res.value
        elif value is AllParam:
            analyser.container.pushback(may_arg)
            result[key] = analyser.container.release(seps)
            analyser.container.current_index = analyser.container.ndata
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
    params: Iterable[list[Option] | Sentence | SubAnalyser],
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
        elif isinstance(_p, Sentence):
            if (_may_param := split_once(text, _p.separators)[0]) == _p.name:
                return _p
            if is_fuzzy_match and levenshtein_norm(_may_param, _p.name) >= config.fuzzy_threshold:
                raise FuzzyMatchSuccess(config.lang.common_fuzzy_matched.format(source=_may_param, target=_p.name))
        else:
            if (_may_param := split_once(text, _p.container.separators)[0]) == _p.command.name:
                return _p
            if is_fuzzy_match and levenshtein_norm(_may_param, _p.command.name) >= config.fuzzy_threshold:
                raise FuzzyMatchSuccess(config.lang.common_fuzzy_matched.format(source=_may_param, target=_p.command.name))

def analyse_option(analyser: SubAnalyser, param: Option) -> tuple[str, OptionResult]:
    """
    分析 Option 部分

    Args:
        analyser: 使用的分析器
        param: 目标Option
    """
    analyser.container.context = param
    if param.requires and analyser.sentences != param.requires:
        raise ParamsUnmatched(f"{param.name}'s required is not '{' '.join(analyser.sentences)}'")
    analyser.sentences = []
    if param.is_compact:
        name, _ = analyser.container.popitem()
        for al in param.aliases:
            if mat := re.fullmatch(f"{al}(?P<rest>.*?)", name):
                analyser.container.pushback(mat.groupdict()['rest'], replace=True)
                break
        else:
            raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
    else:
        name, _ = analyser.container.popitem(param.separators)
        if name not in param.aliases:  # 先匹配选项名称
            raise ParamsUnmatched(f"{name} dose not matched with {param.name}")
    name = param.dest
    if param.nargs == 0:
        return name, OptionResult()
    return name, OptionResult(None, analyse_args(analyser, param.args, param.nargs))


def analyse_param(analyser: SubAnalyser, _text: Any, _str: bool):
    if handler := analyser.special.get(_text if _str else Ellipsis):
        raise SpecialOptionTriggered(handler)
    _param = _param if (_param := (analyser.compile_params.get(_text) if _str and _text else Ellipsis)) else (
        None if analyser.container.default_separate else analyse_unmatch_params(
            analyser.compile_params.values(), _text, analyser.fuzzy_match
        )
    )
    if (not _param or _param is Ellipsis) and not analyser.args_result:
        analyser.args_result = analyse_args(analyser, analyser.self_args, analyser.command.nargs)
    elif isinstance(_param, list):
        for opt in _param:
            _data, _index = analyser.container.data_set()
            try:
                opt_n, opt_v = analyse_option(analyser, opt)
                analyser.options_result[opt_n] = opt_v
                _data.clear()
                break
            except Exception as e:
                exc = e
                analyser.container.data_reset(_data, _index)
                continue
        else:
            raise exc  # type: ignore  # noqa
    elif isinstance(_param, Sentence):
        analyser.sentences.append(analyser.container.popitem()[0])
    elif _param not in (None, Ellipsis):
        _param.process()
        analyser.subcommands_result.setdefault(_param.command.dest, _param.export())

def analyse_header(analyser: Analyser) -> tuple:
    command = analyser.command_header
    head_text, _str = analyser.container.popitem()
    if isinstance(command, TPattern) and _str and (mat := command.fullmatch(head_text)):
        return head_text, head_text, True, mat.groupdict()
    elif isinstance(command, BasePattern) and (val := command(head_text, Empty)).success:
        return head_text, val.value, True
    else:
        may_command, _m_str = analyser.container.popitem()
        if isinstance(command, List) and _m_str and not _str:
            for _command in command:
                if (mat := _command[1].fullmatch(may_command)) and head_text == _command[0]:
                    return (head_text, may_command), (head_text, may_command), True, mat.groupdict()
        if isinstance(command, tuple):
            if not _str and not isclass(head_text) and (
                (isinstance(command[0], list) and (head_text in command[0] or type(head_text) in command[0])) or
                (isinstance(command[0], tuple) and (head_text in command[0][0] or type(head_text) in command[0][0]))
            ):
                if isinstance(command[1], TPattern):
                    if _m_str and (mat := command[1].fullmatch(may_command)):
                        return (head_text, may_command), (head_text, may_command), True, mat.groupdict()
                elif (val := command[1](may_command, Empty)).success:
                    return (head_text, may_command), (head_text, val.value), True
            elif _str and isinstance(command[0], tuple) and isinstance(command[0][1], TPattern):
                if _m_str:
                    pat = re.compile(command[0][1].pattern + command[1].pattern)  # type: ignore
                    if mat := pat.fullmatch(head_text):
                        analyser.container.pushback(may_command)
                        return head_text, head_text, True, mat.groupdict()
                    elif mat := pat.fullmatch(head_text + may_command):
                        return head_text + may_command, head_text + may_command, True, mat.groupdict()
                elif isinstance(command[1], BasePattern) and (
                    (mat := command[0][1].fullmatch(head_text)) and (val := command[1](may_command, Empty)).success
                ):
                    return (head_text, may_command), (head_text, val.value), True, mat.groupdict()

    if _str and analyser.fuzzy_match:
        headers_text = []
        if analyser.command.headers and analyser.command.headers != [""]:
            for i in analyser.command.headers:
                if isinstance(i, str):
                    headers_text.append(f"{i}{analyser.command.command}")
                else:
                    headers_text.extend((f"{i}", analyser.command.command))
        elif analyser.command.command:
            headers_text.append(analyser.command.command)
        if isinstance(command, (TPattern, BasePattern)):
            source = head_text
        else:
            source = head_text + analyser.container.separators[0] + str(may_command)
        if source == analyser.command.command:
            analyser.header_result = (source, source, False)
            raise ParamsUnmatched(config.lang.header_error.format(target=head_text))
        for ht in headers_text:
            if levenshtein_norm(source, ht) >= config.fuzzy_threshold:
                analyser.header_result = (source, ht, True)
                raise FuzzyMatchSuccess(config.lang.common_fuzzy_matched.format(target=source, source=ht))
    raise ParamsUnmatched(config.lang.header_error.format(target=head_text))

def handle_help(analyser: Analyser):
    _help_param = [str(i) for i in analyser.container.release(recover=True) if i not in analyser.special]
    output_manager.send(
        analyser.command.name,
        lambda: analyser.command.formatter.format_node(_help_param),
    )
    return analyser.export(fail=True)


def handle_shortcut(analyser: Analyser):
    analyser.container.popitem()
    opt_v = analyse_args(analyser, Args["delete;?", "delete"]["name", str]["command", str, "_"], 3)
    try:
        msg = analyser.command.shortcut(
            opt_v["name"],
            None if opt_v["command"] == "_" else {"command": analyser.converter(opt_v["command"])},
            bool(opt_v.get("delete"))
        )
        output_manager.send(analyser.command.name, lambda: msg)
    except Exception as e:
        output_manager.send(analyser.command.name, lambda: str(e))
    return analyser.export(fail=True)


def _handle_unit(analyser: Analyser, trigger: Arg):
    if gen := trigger.field.completion:
        comp = gen()
        if isinstance(comp, str):
            return output_manager.send(analyser.command.name, lambda: comp)
        target = str(analyser.container.release(recover=True)[-2])
        o = "\n- ".join(list(filter(lambda x: target in x, comp)) or comp)
        return output_manager.send(
            analyser.command.name, lambda: f"{config.lang.common_completion_arg}\n- {o}"
        )
    default = trigger.field.default_gen
    o = f"{trigger.value}{'' if default is None else f' default:({None if default is Empty else default})'}"
    return output_manager.send(
        analyser.command.name, lambda: f"{config.lang.common_completion_arg}\n{o}"
    )


def _handle_sentence(analyser: Analyser):
    res: list[str] = []
    s_len = len(stc := analyser.sentences)
    for opt in filter(
        lambda x: len(x.requires) >= s_len and x.requires[s_len - 1] == stc[-1],
        analyser.command.options,
    ):
        if len(opt.requires) > s_len:
            res.append(opt.requires[s_len])
        else:
            res.extend(opt.aliases if isinstance(opt, Option) else [opt.name])
    return res


def _handle_none(analyser: Analyser, got: list[str]):
    res: list[str] = []
    if not analyser.args_result and analyser.self_args.argument:
        unit = analyser.self_args.argument[0]
        if gen := unit.field.completion:
            res.append(comp if isinstance(comp := gen(), str) else "\n- ".join(comp))
        else:
            default = unit.field.default_gen
            res.append(
                f"{unit.value}{'' if default is None else f' ({None if default is Empty else default})'}"
            )
    for opt in filter(
        lambda x: x.name not in analyser.command.namespace_config.builtin_option_name['completion'],
        analyser.command.options,
    ):
        if opt.requires and all(opt.requires[0] not in i for i in got):
            res.append(opt.requires[0])
        elif opt.dest not in got:
            res.extend(opt.aliases if isinstance(opt, Option) else [opt.name])
    return res


def handle_completion(analyser: Analyser, trigger: None | Args | Subcommand | str = None):
    if isinstance(trigger, Arg):
        _handle_unit(analyser, trigger)
    elif isinstance(trigger, Subcommand):
        output_manager.send(
            analyser.command.name,
            lambda: f"{config.lang.common_completion_node}\n- " +
                    "\n- ".join(analyser.get_sub_analyser(trigger).compile_params),
        )
    elif isinstance(trigger, str):
        res = list(filter(lambda x: trigger in x, analyser.compile_params))
        if not res:
            return analyser.export(
                fail=True,
                exception=ParamsUnmatched(config.lang.analyser_param_unmatched.format(target=trigger)),
            )
        out = [
            i for i in res
            if i not in (*analyser.options_result.keys(), *analyser.subcommands_result.keys(), *analyser.sentences)
        ]
        output_manager.send(
            analyser.command.name,
            lambda: f"{config.lang.common_completion_node}\n- " + "\n- ".join(out or res),
        )
    else:
        got = [*analyser.options_result.keys(), *analyser.subcommands_result.keys(), *analyser.sentences]
        target = str(analyser.container.release(recover=True)[-1])
        if _res := list(filter(lambda x: target in x and target != x, analyser.compile_params)):
            out = [i for i in _res if i not in got]
            output_manager.send(
                analyser.command.name,
                lambda: f"{config.lang.common_completion_node}\n- " + "\n- ".join(out or _res),
            )
        else:
            res = _handle_sentence(analyser) if analyser.sentences else _handle_none(analyser, got)
            output_manager.send(
                analyser.command.name,
                lambda: f"{config.lang.common_completion_node}\n- " + "\n- ".join(set(res)),
            )
    return analyser.export(fail=True, exception='NoneType: None\n')  # type: ignore
