from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Iterable

from nepattern import AllParam, AnyOne, AnyString, BasePattern
from nepattern.util import TPattern
from tarina import Empty, lang

from ..action import Action
from ..args import STRING, Arg, Args
from ..base import Option
from ..exceptions import ArgumentMissing, ParamsUnmatched
from ..model import HeadResult, OptionResult
from ..typing import KeyWordVar, MultiVar
from ._header import Double, Header

if TYPE_CHECKING:
    from ._analyser import SubAnalyser
    from ._argv import Argv


def _handle_keyword(
    argv: Argv,
    value: KeyWordVar,
    may_arg: Any,
    seps: tuple[str, ...],
    result_dict: dict[str, Any],
    default_val: Any,
    optional: bool,
    key: str | None = None,
    fuzzy: bool = False,
):
    """处理关键字参数

    Args:
        argv (Argv): 命令行参数
        value (KeyWordVar): 关键字参数
        may_arg (Any): 可能的参数
        seps (tuple[str, ...]): 分隔符
        result_dict (dict[str, Any]): 结果字典
        default_val (Any): 默认值
        optional (bool): 是否可选
        key (str | None, optional): 关键字. Defaults to None.
        fuzzy (bool, optional): 是否模糊匹配. Defaults to False.
    """
    if _kwarg := re.match(fr'^([^{value.sep}]+){value.sep}(.*?)$', may_arg):
        key = key or _kwarg[1]
        if (_key := _kwarg[1]) != key:
            argv.rollback(may_arg)
            if default_val is None:
                raise ParamsUnmatched(lang.require("fuzzy", "matched").format(source=_key, target=key))
            result_dict[_key] = None if default_val is Empty else default_val
            return
        if not (_m_arg := _kwarg[2]):
            _m_arg, _ = argv.next(seps)
        res = value.base.exec(_m_arg, default_val)
        if res.flag != 'valid':
            argv.rollback(may_arg)
        if res.flag == 'error':
            if optional:
                return
            raise ParamsUnmatched(*res.error.args)
        result_dict[_kwarg[1]] = res._value  # type: ignore
        return
    argv.rollback(may_arg)
    raise ParamsUnmatched(lang.require("args", "key_missing").format(target=may_arg, key=key))


def _loop_kw(
    argv: Argv,
    _loop: int,
    seps: tuple[str, ...],
    value: MultiVar,
    default: Any
):
    """循环关键字参数"""
    result = {}
    for _ in range(_loop):
        _m_arg, _m_str = argv.next(seps)
        if not _m_arg:
            continue
        if _m_str and _m_arg in argv.param_ids:
            argv.rollback(_m_arg)
            break
        try:
            _handle_keyword(argv, value.base, _m_arg, seps, result, default, False)  # type: ignore
        except ParamsUnmatched:
            break
    if not result:
        if value.flag == '+':
            raise ParamsUnmatched
        result = [default] if default else []
    return result


def _loop(
    argv: Argv,
    _loop: int,
    seps: tuple[str, ...],
    value: MultiVar,
    default: Any,
    kw: KeyWordVar | None
):
    """循环参数"""
    result = []
    for _ in range(_loop):
        _m_arg, _m_str = argv.next(seps)
        if not _m_arg:
            continue
        if _m_str and (
            _m_arg in argv.param_ids or
            (kw and re.match(fr'^([^{kw.sep}]+){kw.sep}(.*?)$', _m_arg))
        ):
            argv.rollback(_m_arg)
            break
        if (res := value.base.exec(_m_arg)).flag != 'valid':
            argv.rollback(_m_arg)
            break
        result.append(res._value)  # type: ignore
    if not result:
        if value.flag == '+':
            raise ParamsUnmatched
        result = [default] if default else []
    return tuple(result)


def multi_arg_handler(
    argv: Argv,
    args: Args,
    arg: Arg,
    result_dict: dict[str, Any],
):
    """处理可变参数

    Args:
        argv (Argv): 命令行参数
        args (Args): 参数集合
        arg (Arg): 参数单元
        result_dict (dict[str, Any]): 结果字典
    """
    seps = arg.separators
    value: MultiVar = arg.value  # type: ignore
    key = arg.name
    default = arg.field.default
    kw = value.base.__class__ == KeyWordVar
    _rest = len(args) - len(result_dict)
    _all_count = len(argv.release(seps))
    if not kw and not args.var_keyword or kw and not args.var_positional:
        loop = _all_count - _rest + 1
    elif not kw:
        loop = _all_count - (_rest - 2*(args.var_keyword.flag == "*"))
    else:
        loop = _all_count - (_rest - 2*(args.var_positional.flag == "*"))
    if value.length > 0:
        loop = min(loop, value.length)
    result_dict[key] = (
        _loop_kw(argv, loop, seps, value, default) if kw
        else _loop(argv, loop, seps, value, default, value.base if kw else None)
    )
    if kw:
        kwargs = result_dict[key]
        if not isinstance(kwargs, dict):
            kwargs = {key: kwargs}
        result_dict[key] = kwargs
    else:
        varargs = result_dict[key]
        if not isinstance(varargs, Iterable):
            varargs = (varargs, )
        elif not isinstance(varargs, tuple):
            varargs = tuple(varargs)
        result_dict[key] = varargs


def analyse_args(argv: Argv, args: Args) -> dict[str, Any]:
    """
    分析 `Args` 部分

    Args:
        argv (Argv): 命令行参数
        args (Args): 目标 `Args`

    Returns:
        dict[str, Any]: 解析结果
    """
    result: dict[str, Any] = {}
    for arg in args.argument:
        argv.context = arg
        key = arg.name
        value = arg.value
        default_val = arg.field.default
        may_arg, _str = argv.next(arg.separators)
        if not may_arg or (_str and may_arg in argv.param_ids):
            argv.rollback(may_arg)
            if default_val is not None:
                result[key] = None if default_val is Empty else default_val
            elif value.__class__ is MultiVar and value.flag == '*':  # type: ignore
                result[key] = ()
            elif not arg.optional:
                raise ArgumentMissing(lang.require("args", "missing").format(key=key))
            continue
        if value.__class__ is MultiVar:
            argv.rollback(may_arg)
            multi_arg_handler(argv, args, arg, result)  # type: ignore
        elif value.__class__ is KeyWordVar:
            _handle_keyword(
                argv, value, may_arg, arg.separators,  # type: ignore
                result, default_val, arg.optional, key, argv.fuzzy_match  # type: ignore
            )
        elif value == AllParam:
            argv.rollback(may_arg)
            result[key] = argv.converter(argv.release(arg.separators))
            argv.current_index = argv.ndata
            return result
        elif value == AnyOne:
            result[key] = may_arg
        elif value == AnyString:
            result[key] = str(may_arg)
        elif value == STRING and _str:
            result[key] = may_arg
        else:
            res = (
                value.invalidate(may_arg, default_val)
                if value.anti
                else value.validate(may_arg, default_val)
            )
            if res.flag != 'valid':
                argv.rollback(may_arg)
            if res.flag == 'error':
                if arg.optional:
                    continue
                raise ParamsUnmatched(*res.error.args)
            if not arg.anonymous:
                result[key] = res._value  # type: ignore
    argv.context = None
    return result


def handle_option(argv: Argv, opt: Option) -> tuple[str, OptionResult]:
    """
    处理 `Option` 部分

    Args:
        argv (Argv): 命令行参数
        opt (Option): 目标 `Option`
    """
    argv.context = opt
    _cnt = 0
    error = True
    name, _ = argv.next(opt.separators)
    if opt.compact:
        for al in opt.aliases:
            if mat := re.fullmatch(f"{al}(?P<rest>.*?)", name):
                argv.rollback(mat.groupdict()['rest'], replace=True)
                error = False
                break
    elif opt.action.type == 2:
        for al in opt.aliases:
            if name.startswith(al) and (cnt := (len(name.lstrip("-")) / len(al.lstrip("-")))).is_integer():
                _cnt = int(cnt)
                error = False
                break
    elif name in opt.aliases:
        error = False
    if error:
        raise ParamsUnmatched(lang.require("option", "name_error").format(source=opt.name, target=name))
    name = opt.dest
    return (
        (name, OptionResult(None, analyse_args(argv, opt.args)))
        if opt.nargs
        else (name, OptionResult(_cnt or opt.action.value))
    )


def handle_action(param: Option, source: OptionResult, target: OptionResult):
    """处理 `Option` 的 `action`"""
    if param.action.type == 0:
        return target
    if param.action.type == 2:
        if not param.nargs:
            source.value += target.value
            return source
        return target
    if not param.nargs:
        source.value.extend(target.value)
    else:
        for key, value in target.args.items():
            if key in source.args:
                source.args[key].append(value)
            else:
                source.args[key] = [value]
    return source


def analyse_option(analyser: SubAnalyser, argv: Argv, opt: Option):
    """
    分析 `Option` 部分

    Args:
        analyser (SubAnalyser): 当前解析器
        argv (Argv): 命令行参数
        opt (Option): 目标 `Option`
    """
    opt_n, opt_v = handle_option(argv, opt)
    if opt_n not in analyser.options_result:
        analyser.options_result[opt_n] = opt_v
        if opt.action.type == 1 and opt_v.args:
            for key in list(opt_v.args.keys()):
                opt_v.args[key] = [opt_v.args[key]]
    else:
        analyser.options_result[opt_n] = handle_action(opt, analyser.options_result[opt_n], opt_v)


def analyse_compact_params(analyser: SubAnalyser, argv: Argv):
    """分析紧凑参数

    Args:
        analyser (SubAnalyser): 当前解析器
        argv (Argv): 命令行参数
    """
    for param in analyser.compact_params:
        _data, _index = argv.data_set()
        try:
            if param.__class__ is Option:
                analyse_option(analyser, argv, param)
            else:
                try:
                    param.process(argv)
                finally:
                    analyser.subcommands_result[param.command.dest] = param.result()
            _data.clear()
            return True
        except ParamsUnmatched as e:
            if argv.context.__class__ is Arg:
                raise e
            argv.data_reset(_data, _index)


def handle_opt_default(defaults: dict[str, tuple[OptionResult, Action]], data: dict[str, OptionResult]):
    for k, v in defaults.items():
        if k not in data:
            data[k] = v[0]
        if not v[0].args:
            continue
        for key, value in v[0].args.items():
            data[k].args.setdefault(key, [value] if v[1].value == 1 else value)


def analyse_param(analyser: SubAnalyser, argv: Argv, seps: tuple[str, ...] | None = None):
    """处理参数

    Args:
        analyser (SubAnalyser): 当前解析器
        argv (Argv): 命令行参数
        seps (tuple[str, ...], optional): 指定的分隔符.
    """
    _text, _str = argv.next(seps, move=False)
    if not _str or not _text:
        _param = None
    elif _text in analyser.compile_params:
        _param = analyser.compile_params[_text]
    elif analyser.compact_params and (res := analyse_compact_params(analyser, argv)):
        if res.__class__ is str:
            raise ParamsUnmatched(res)
        argv.context = None
        return True
    else:
        _param = None
    if not _param and analyser.command.nargs and not analyser.args_result:
        analyser.args_result = analyse_args(argv, analyser.self_args)
        if analyser.args_result:
            argv.context = None
            return True
    if _param.__class__ is Option:
        analyse_option(analyser, argv, _param)
    elif _param is not None:
        try:
            _param.process(argv)
        finally:
            analyser.subcommands_result[_param.command.dest] = _param.result()
    else:
        return False
    argv.context = None
    return True


def analyse_header(header: Header, argv: Argv) -> HeadResult:
    """分析头部

    Args:
        header (Header): 头部
        argv (Argv): 命令行参数

    Returns:
        HeadResult: 分析结果
    """
    content = header.content
    mapping = header.mapping
    head_text, _str = argv.next()
    if _str:
        if content.__class__ is set and head_text in content:
            return HeadResult(head_text, head_text, True, fixes=mapping)
        elif content.__class__ is TPattern and (mat := content.fullmatch(head_text)):
            return HeadResult(head_text, head_text, True, mat.groupdict(), mapping)
        if header.compact and content.__class__ in (set, TPattern) and (mat := header.compact_pattern.match(head_text)):
            argv.rollback(head_text[len(mat[0]):], replace=True)
            return HeadResult(mat[0], mat[0], True, mat.groupdict(), mapping)

    may_cmd, _m_str = argv.next()
    if content.__class__ is list and _m_str:
        for pair in content:
            if res := pair.match(head_text, may_cmd, argv.rollback, header.compact):
                return HeadResult(*res, fixes=mapping)
    if content.__class__ is Double and (
        res := content.match(head_text, may_cmd, _str, _m_str, argv.rollback, header.compact)
    ):
        return HeadResult(*res, fixes=mapping)
    if _str:
        argv.rollback(may_cmd)
        source = head_text
    elif _m_str and may_cmd:
        source = may_cmd
    else:
        argv.rollback(may_cmd)
        raise ParamsUnmatched(lang.require("header", "error").format(target=head_text), None)
    raise ParamsUnmatched(lang.require("header", "error").format(target=source), source)
