from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from nepattern import ANY, STRING, AnyString
from tarina import Empty, safe_eval, lang, split_once

from ..i18n import i18n
from ..args import Arg, _Args
from ..base import Option, Subcommand, Header, HeadResult
from ..config import global_config
from ..exceptions import (
    AnalyseException,
    ArgumentMissing,
    FuzzyMatchSuccess,
    InvalidHeader,
    InvalidParam,
    PauseTriggered,
    ParamsUnmatched,
)
from ..utils import levenshtein

if TYPE_CHECKING:
    from ._analyser import Analyser
    from ._argv import Argv

pat = re.compile("(?:-*no)?-*(?P<name>.+)")
_bracket = re.compile(r"\{(.+)}")
_parentheses = re.compile(r"\$?\((.+)\)")


def _context(argv: Argv, target: Arg[Any], _arg: str):
    _pat = _bracket if argv.context_style == "bracket" else _parentheses
    if not (mat := _pat.fullmatch(_arg)):
        return _arg
    ctx = argv.context
    name = mat.group(1)
    if name == "_":
        return ctx
    if name in ctx:
        return ctx[name]
    try:
        return safe_eval(name, ctx)
    except NameError:
        raise ArgumentMissing(target.field.get_missing_tips(i18n.require("args.missing").format(key=target.name)), target)
    except Exception as e:
        raise InvalidParam(
            target.field.get_unmatch_tips(_arg, lang.require("nepattern", "error.content").format(target=target.name, expected=name)),
            target
        ) from e


def _handle_arg(argv: Argv, target: Arg[Any], arg: Any, _str: bool):
    value = target.type_
    _arg = arg
    if _str and argv.context_style:
        _arg = _context(argv, target, _arg)
    if (value is STRING and _str) or value is ANY:
        return _arg
    if value is AnyString:
        return str(_arg)
    res = value.execute(_arg)
    if res._value is Empty:
        argv.rollback(arg)
        default_val = target.field.get_default()
        if default_val is not Empty:
            return default_val
        if target.field.optional:
            return Empty
        raise InvalidParam(target.field.get_unmatch_tips(arg, res.error().args[0]), target)  # type: ignore
    return res._value  # noqa


def step_multiple(argv: Argv, ana: Analyser, arg: Arg[Any], result: dict[str, Any]):
    field = arg.field
    may_arg, _str = argv.next(field.seps)
    if _str and may_arg in global_config.remainders:
        may_arg = None
    elif _str and may_arg in ana._unvisited and ((slot := ana._unvisited[may_arg])[1] not in ana.value_result and not slot[0].soft_keyword):
        argv.rollback(may_arg)
        may_arg = None
    if may_arg is None or (_str and not may_arg):
        if arg.name not in result and field.multiple != "*":
            raise ArgumentMissing(field.get_missing_tips(i18n.require("args.missing").format(key=arg.name)), arg)
        if arg.name not in result:
            result[arg.name] = ()
        return True
    if field.kw_only:
        if not _str:
            raise InvalidParam(i18n.require("args.key_missing").format(target=may_arg, key=arg.name), arg)
        key, _m_arg = split_once(may_arg, field.kw_sep, argv.filter_crlf)
        key: str = pat.fullmatch(key)["name"]  # type: ignore
        if _m_arg:
            may_arg = _m_arg
        else:
            may_arg, _str = argv.next(field.seps)
        ans = _handle_arg(argv, arg, may_arg, _str)
        if ans is Empty:
            return True
        if arg.name not in result:
            result[arg.name] = []
        result[arg.name].append((key, ans))
        if field.multiple is not True and isinstance(field.multiple, int):
            return len(result[arg.name]) >= field.multiple
        return False
    try:
        ans = _handle_arg(argv, arg, may_arg, _str)
    except InvalidParam:
        return True
    if ans is Empty:
        return True
    if arg.name not in result:
        result[arg.name] = []
    result[arg.name].append(ans)
    if field.multiple is not True and isinstance(field.multiple, int):
        return len(result[arg.name]) >= field.multiple
    return False


def _handle_arg_wild(target: Arg[Any], arg: Any):
    value = target.type_
    _str = isinstance(arg, str)
    if value is ANY or (value is STRING and _str):
        return arg
    if value is AnyString:
        return str(arg)
    res = value.execute(arg)
    if res._value is Empty:
        if target.field.optional:
            return Empty
        raise InvalidParam(target.field.get_unmatch_tips(arg, res.error().args[0]), target)  # type: ignore
    return res._value  # noqa


def analyse_args(analyser: Analyser, argv: Argv, args: _Args) -> dict[str, Any]:
    """
    分析 `_Args` 部分

    Args:
        analyser (SubAnalyser): 当前解析器
        argv (Argv): 命令行参数
        args (_Args): 目标 `_Args`

    Returns:
        dict[str, Any]: 解析结果
    """
    result = {}
    index = 0
    while index < args.count:
        arg = args.data[index]
        field = arg.field
        if field.wildcard:
            data = [_handle_arg_wild(arg, d) for d in argv.release(no_split=True)]
            data = [d for d in data if d is not Empty]
            result[arg.name] = argv.converter(data)
            argv.current_index = argv.ndata
            return result
        if field.multiple is False:
            may_arg, _str = argv.next(field.seps)
            if _str and may_arg in analyser._unvisited and ((slot := analyser._unvisited[may_arg])[1] not in analyser.value_result and not slot[0].soft_keyword):
                argv.rollback(may_arg)
                may_arg = None
            if may_arg is None or (_str and not may_arg):
                if (de := arg.field.get_default()) is not Empty:
                    result[arg.name] = de
                elif not field.optional:
                    raise ArgumentMissing(field.get_missing_tips(i18n.require("args.missing").format(key=arg.name)), arg)
                index += 1
                continue
            if field.kw_only:
                if not _str:
                    raise InvalidParam(i18n.require("args.key_missing").format(target=may_arg, key=arg.name), arg)
                key, _m_arg = split_once(may_arg, field.kw_sep, argv.filter_crlf)
                key: str = pat.fullmatch(key)["name"]  # type: ignore
                if key != arg.name:
                    if levenshtein(key, arg.name) >= argv.fuzzy_threshold:
                        raise FuzzyMatchSuccess(i18n.require("fuzzy.matched").format(source=arg.name, target=key))
                    raise InvalidParam(i18n.require("args.key_not_found").format(name=key), arg)
                if _m_arg:
                    may_arg = _m_arg
                else:
                    may_arg, _str = argv.next(field.seps)
            ans = _handle_arg(argv, arg, may_arg, _str)
            if ans is not Empty:
                result[arg.name] = ans
            index += 1
            continue
        elif step_multiple(argv, analyser, arg, result):
            if arg.field.kw_only:
                result[arg.name] = dict(result[arg.name])
            elif arg.field.multiple == "str":
                result[arg.name] = arg.field.seps[0].join(result[arg.name])
            else:
                result[arg.name] = tuple(result[arg.name])
            index += 1
    # TODO: let the user decide whether to return the Args model or raw data
    # if args.origin:
    #     return args.origin.load(result)
    return result


def analyse_option(analyser: Analyser, opt: Option, argv: Argv, path: tuple[str, ...], name_validated: bool):
    """
    分析 `Option` 部分

    Args:
        analyser (SubAnalyser): 当前解析器
        opt (Option): 目标 `Option`
        argv (Argv): 命令行参数
        path (tuple[str, ...]): 路径
        name_validated (bool): 是否已经验证过名称
    """
    _cnt = 0
    error = True
    if not name_validated:
        name, _ = argv.next(opt.separators)
        if opt.compact:
            mat = next(filter(None, (re.fullmatch(f"{al}(?P<rest>.*?)", name) for al in opt.aliases)), None)
            if mat:
                argv.rollback(mat["rest"], replace=True)
                error = False
        elif opt.action.type == 2:
            for al in opt.aliases:
                if name.startswith(al) and (cnt := (len(name.lstrip("-")) / len(al.lstrip("-")))).is_integer():
                    _cnt = int(cnt)
                    error = False
                    break
        elif name in opt.aliases:
            error = False
        if error:
            argv.rollback(name)
            if not argv.fuzzy_match:
                raise InvalidParam(i18n.require("option.name_error").format(source=opt.dest, target=name), opt)
            for al in opt.aliases:
                if levenshtein(name, al) >= argv.fuzzy_threshold:
                    raise FuzzyMatchSuccess(i18n.require("fuzzy.matched").format(source=al, target=name))
            raise InvalidParam(i18n.require("option.name_error").format(source=opt.dest, target=name), opt)
    args = analyse_args(analyser, argv, opt.args) if opt.nargs else {}
    if path not in analyser.value_result:
        analyser.args_result[path] = args
        if opt.action.type == 1 and args:
            analyser.args_result[path] = {key: [value] for key, value in args.items()}
        analyser.value_result[path] = _cnt or opt.action.value
        return True
    if opt.action.type == 0:  # cover the old value
        analyser.value_result[path] = _cnt or opt.action.value
        analyser.args_result[path] = args
        return True
    if opt.action.type == 2:
        analyser.value_result[path] += _cnt or opt.action.value
        return True
    if not opt.nargs:  # opt.action.type == 1
        source = analyser.value_result[path][:]
        source.extend(opt.action.value)
        analyser.value_result[path] = source
    else:
        for key, value in args.items():
            if key in analyser.args_result[path]:
                analyser.args_result[path][key].append(args[key])
            else:
                analyser.args_result[path][key] = [value]
    return True


def analyse_subcommand(analyser: Analyser, sub: Subcommand, argv: Argv, path: tuple[str, ...], name_validated: bool = True):
    if path in analyser.value_result:
        return False
    if not name_validated:
        name, _ = argv.next(sub.separators)
        if name not in sub.aliases:
            argv.rollback(name)
            if not argv.fuzzy_match:
                raise InvalidParam(i18n.require("subcommand.name_error").format(source=sub.dest, target=name), sub)
            for al in sub.aliases:
                if levenshtein(name, al) >= argv.fuzzy_threshold:
                    raise FuzzyMatchSuccess(i18n.require("fuzzy.matched").format(source=al, target=name), sub)
            raise InvalidParam(i18n.require("subcommand.name_error").format(source=sub.dest, target=name), sub)
    analyser.value_result[path] = ...
    analyser.update(sub, path)
    while analyse_param(analyser, sub, argv, path, sub.separators) and argv.current_index != argv.ndata:
        pass
    if path not in analyser.args_optional or path in analyser.args_result:
        return True
    if not analyser.args_optional[path]:
        raise ArgumentMissing(
            sub.args.data[0].field.get_missing_tips(
                i18n.require("subcommand.args_missing").format(name=".".join(path))
            ),
            sub
        )
    analyser.args_result[path] = analyse_args(analyser, argv, sub.args)
    return True


def analyse_compact_params(analyser: Analyser, argv: Argv, prefixes: tuple[str, ...]):
    """分析紧凑参数

    Args:
        analyser (SubAnalyser): 当前解析器
        argv (Argv): 命令行参数
        prefixes (tuple[str, ...]): 前缀
    """
    exc = None
    for param in analyser.compact_params[prefixes]:
        _data, _index = argv.data_set()
        try:
            path = prefixes + (param.dest,)
            if param.__class__ is Option or param.__class__.__base__ is Option:
                oparam: Option = param  # type: ignore
                analyse_option(analyser, oparam, argv, path, False)
            else:
                sparam: SubAnalyser = param  # type: ignore
                analyse_subcommand(analyser, sparam, argv, path, False)
            _data.clear()
            return True
        except (FuzzyMatchSuccess, PauseTriggered):
            raise
        except AnalyseException as e:
            if isinstance(e, InvalidParam) and e.context_node is not param:
                exc = e
            else:
                argv.data_reset(_data, _index)
    else:
        if exc and not analyser._error:
            analyser._error = exc
        return False


def analyse_param(analyser: Analyser, current: Subcommand, argv: Argv, prefixes: tuple[str, ...], seps: str | None = None):
    """处理参数

    Args:
        analyser (SubAnalyser): 当前解析器
        current (Subcommand): 当前子命令
        argv (Argv): 命令行参数
        prefixes (tuple[str, ...]): 前缀
        seps (str, optional): 指定的分隔符.
    """
    # 每次调用都会尝试解析一个参数
    _text, _str = argv.next(seps)
    # analyser.compile_params 有命中，说明在当前子命令内有对应的选项/子命令
    if _str and _text and (_param := current._lookup_map.get(_text)):
        path = prefixes + (_param.dest,)
        apply = True
        try:
            if _param.__class__ is Subcommand:
                apply = analyse_subcommand(analyser, _param, argv, path, True)  # type: ignore
            else:
                apply = analyse_option(analyser, _param, argv, path, True)  # type: ignore
        except (FuzzyMatchSuccess, PauseTriggered):
            raise
        except AnalyseException as e:
            if not analyser._error:
                analyser._error = e
        if apply:
            return True
    # 如果没有命中，则说明当前参数可能存在自定义分隔符，或者属于子命令的主参数，那么需要重新解析
    argv.rollback(_text)
    # 尝试以紧凑参数解析
    if _str and _text and analyser.compact_params and prefixes in analyser.compact_params and analyse_compact_params(analyser, argv, prefixes):
        return True
    # 主参数同样只允许解析一次
    if current.nargs and prefixes not in analyser.args_result:
        if res := analyse_args(analyser, argv, current.args):
            analyser.args_result[prefixes] = res
            return True
    # 若参数属于该子命令的同级/上级选项或子命令，则终止解析
    if _str and _text and _text in analyser._unvisited and analyser._unvisited[_text][1] not in analyser.value_result:
        return False
    if analyser.extra_allow:
        analyser.args_result.setdefault(prefixes, {}).setdefault("$extra", []).append(_text)
        argv.next()
        return True
    # 给 Completion 打的洞，若此时 analyser 属于主命令, 则让其先解析完主命令
    elif _str and _text and not prefixes:
        if not analyser._error:
            analyser._error = ParamsUnmatched(i18n.require("analyser.param_unmatched").format(target=_text))
        argv.next()
        return True
    return False


def analyse_header(header: "Header", argv: Argv):
    head_text, _str = argv.next()
    if _str:
        if head_text in header.content:
            argv.apply()
            return HeadResult(head_text, head_text, True)
        if header.compact and (mat := header.compact_pattern.match(head_text)):
            argv.rollback(head_text[len(mat[0]):], replace=True)
            return HeadResult(mat[0], mat[0], True)
    may_cmd, _m_str = argv.next()
    if _m_str:
        cmd = f"{head_text}{argv.separators[0]}{may_cmd}"
        if cmd in header.content:
            argv.apply()
            return HeadResult(cmd, cmd, True)
        if header.compact and (mat := header.compact_pattern.match(cmd)):
            argv.rollback(cmd[len(mat[0]):], replace=True)
            return HeadResult(mat[0], mat[0], True)
    # _after_analyse_header
    if _str:
        argv.rollback(may_cmd)
        raise InvalidHeader(i18n.require("header.error").format(target=head_text), head_text)
    if _m_str and may_cmd:
        cmd = f"{head_text}{argv.separators[0]}{may_cmd}"
        raise InvalidHeader(i18n.require("header.error").format(target=cmd), cmd)
    argv.rollback(may_cmd)
    raise InvalidHeader(i18n.require("header.error").format(target=head_text), None)
