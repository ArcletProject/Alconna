from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Iterable, Literal

from nepattern import ANY, STRING, AnyString, Pattern
from tarina import Empty, lang, safe_eval, split_once

from .. import Subcommand
from ..args import Arg, _Args
from ..base import Option, Header, HeadResult
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
from ..typing import KWBool, _AllParamPattern

from ._util import levenshtein

if TYPE_CHECKING:
    from ._analyser import Analyser
    from ._argv import Argv

pat = re.compile("(?:-*no)?-*(?P<name>.+)")
_bracket = re.compile(r"{(.+)}")
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
        raise ArgumentMissing(target.field.get_missing_tips(lang.require("args", "missing").format(key=target.name)), target)
    except Exception as e:
        raise InvalidParam(
            target.field.get_unmatch_tips(_arg, lang.require("nepattern", "context_error").format(target=target.name, expected=name)),
            target
        )


def _validate(argv: Argv, target: Arg[Any], value: Pattern[Any], result: dict[str, Any], arg: Any, _str: bool):
    _arg = arg
    if _str and argv.context_style:
        _arg = _context(argv, target, _arg)
    if (value is STRING and _str) or value is ANY:
        result[target.name] = _arg
        return
    if value is AnyString:
        result[target.name] = str(_arg)
        return
    default_val = target.field.default
    res = value.execute(_arg)
    if res._value is Empty:
        argv.rollback(arg)
        if default_val is not Empty:
            result[target.name] = default_val
            return
        if target.field.optional:
            return
        raise InvalidParam(target.field.get_unmatch_tips(arg, res.error().args[0]), target)  # type: ignore
    result[target.name] = res._value  # noqa


def step_varpos(argv: Argv, args: _Args, slot: tuple[int | Literal["+", "*", "str"], Arg], result: dict[str, Any]):
    flag, arg = slot
    value = arg.type_
    key = arg.name
    length = int(flag) if flag.__class__ is int else -1
    default_val = arg.field.default
    _result = []
    kwonly_seps = "".join([arg.field.kw_sep for arg in args.keyword_only.values()])
    count = 0
    while argv.current_index != argv.ndata:
        may_arg, _str = argv.next(arg.field.seps)
        if not may_arg or (_str and may_arg in argv.stack_params and not argv.stack_params[may_arg].soft_keyword):
            argv.rollback(may_arg)
            break
        if _str and may_arg in global_config.remainders:
            break
        if _str and kwonly_seps and split_once(pat.match(may_arg)["name"], kwonly_seps, argv.filter_crlf)[0] in args.keyword_only:  # noqa: E501  # type: ignore
            argv.rollback(may_arg)
            break
        if _str and args.vars_keyword and args.vars_keyword[0][1].field.kw_sep in may_arg:
            argv.rollback(may_arg)
            break
        if not (res := value.execute(may_arg)).success:
            argv.rollback(may_arg)
            break
        _result.append(res._value)  # noqa
        count += 1
        if 0 < length <= count:
            break
    if not _result:
        if default_val is not Empty:
            _result = default_val if isinstance(default_val, Iterable) else ()
        elif flag == "*":
            _result = ()
        elif arg.field.optional:
            return
        else:
            raise ArgumentMissing(arg.field.get_missing_tips(lang.require("args", "missing").format(key=key)), arg)
    if flag == "str":
        result[key] = arg.field.seps[0].join(_result)
    else:
        result[key] = tuple(_result)


def step_varkey(argv: Argv, slot: tuple[int | Literal["+", "*", "str"], Arg], result: dict[str, Any]):
    flag, arg = slot
    length = int(flag) if flag.__class__ is int else -1
    value = arg.type_
    name = arg.name
    default_val = arg.field.default
    kw_sep = arg.field.kw_sep
    _result = {}
    count = 0
    while argv.current_index != argv.ndata:
        may_arg, _str = argv.next(arg.field.seps)
        if not may_arg or (_str and may_arg in argv.stack_params and not argv.stack_params[may_arg].soft_keyword) or not _str:
            argv.rollback(may_arg)
            break
        if _str and may_arg in global_config.remainders:
            break
        if not (_kwarg := re.match(rf"^(-*[^{kw_sep}]+){kw_sep}(.*?)$", may_arg)):
            argv.rollback(may_arg)
            break
        key = _kwarg[1]
        if not (_m_arg := _kwarg[2]):
            _m_arg, _ = argv.next(arg.field.seps)
        if not (res := value.execute(_m_arg)).success:
            argv.rollback(may_arg)
            break
        _result[key] = res._value  # noqa
        count += 1
        if 0 < length <= count:
            break
    if not _result:
        if default_val is not Empty:
            _result = default_val if isinstance(default_val, dict) else {}
        elif flag == "*":
            _result = {}
        elif arg.field.optional:
            return
        else:
            raise ArgumentMissing(arg.field.get_missing_tips(lang.require("args", "missing").format(key=name)), arg)
    result[name] = _result


def step_keyword(argv: Argv, args: _Args, result: dict[str, Any]):
    kwonly_seps = set()
    for arg in args.keyword_only.values():
        kwonly_seps.update(arg.field.seps)
    kwonly_seps1 = "".join({arg.field.kw_sep for arg in args.keyword_only.values()})
    target = len(args.keyword_only)
    count = 0
    while count < target:
        may_arg, _str = argv.next("".join(kwonly_seps))
        if not may_arg or not _str:
            argv.rollback(may_arg)
            break
        if _str and may_arg in global_config.remainders:
            break
        key, _m_arg = split_once(may_arg, kwonly_seps1, argv.filter_crlf)
        _key = pat.match(key)["name"]  # type: ignore
        if _key not in args.keyword_only:
            _key = key
        if _key not in args.keyword_only:
            argv.rollback(may_arg)
            if args.vars_keyword or (
                _str and may_arg in argv.stack_params
                and not argv.stack_params[may_arg].soft_keyword
            ):
                break
            for arg in args.keyword_only.values():
                if arg.type_.execute(may_arg).success:
                    raise InvalidParam(lang.require("args", "key_missing").format(target=may_arg, key=arg.name), arg)
            for name in args.keyword_only:
                if levenshtein(_key, name) >= argv.fuzzy_threshold:
                    raise FuzzyMatchSuccess(lang.require("fuzzy", "matched").format(source=name, target=_key))
            raise InvalidParam(lang.require("args", "key_not_found").format(name=_key), args)
        arg = args.keyword_only[_key]
        value = arg.type_
        if not _m_arg:
            if isinstance(value, KWBool):
                _m_arg = key
            else:
                _m_arg, _ = argv.next(args.keyword_only[_key].separators)
        _validate(argv, arg, value, result, _m_arg, _str)
        count += 1

    if count < target:
        for key, arg in args.keyword_only.items():
            if key in result:
                continue
            if arg.field.default is not Empty:
                result[key] = arg.field.default
            elif not arg.field.optional:
                raise ArgumentMissing(arg.field.get_missing_tips(lang.require("args", "missing").format(key=key)), arg)


def _raise(target: Arg, arg: Any, res: Any):
    raise InvalidParam(target.field.get_unmatch_tips(arg, res.error().args[0]), arg)


def analyse_args(argv: Argv, args: _Args) -> dict[str, Any]:
    """
    分析 `_Args` 部分

    _Args:
        argv (Argv): 命令行参数
        args (_Args): 目标 `_Args`

    Returns:
        dict[str, Any]: 解析结果
    """
    result = {}
    for arg in args.normal:
        value = arg.type_
        field = arg.field
        may_arg, _str = argv.next(field.seps)
        if _str and may_arg in argv.stack_params and not argv.stack_params[may_arg].soft_keyword:
            argv.rollback(may_arg)
            if (de := arg.field.default) is not Empty:
                result[arg.name] = de
            elif not field.optional:
                raise ArgumentMissing(field.get_missing_tips(lang.require("args", "missing").format(key=arg.name)), arg)
            continue
        if may_arg is None or (_str and not may_arg):
            if (de := arg.field.default) is not Empty:
                result[arg.name] = de
            elif not field.optional:
                raise ArgumentMissing(field.get_missing_tips(lang.require("args", "missing").format(key=arg.name)), arg)
            continue
        if value.alias == "*":
            if TYPE_CHECKING:
                assert isinstance(value, _AllParamPattern)
            argv.rollback(may_arg)
            if not value.types:
                result[arg.name] = argv.converter(argv.release(no_split=True))
            else:
                data = [
                    d for d in argv.release(no_split=True)
                    if (res := value.execute(d)).success or (not value.ignore and _raise(arg, d, res))
                ]
                result[arg.name] = argv.converter(data)
            argv.current_index = argv.ndata
            return result
        _validate(argv, arg, value, result, may_arg, _str)
    for slot in args.vars_positional:
        step_varpos(argv, args, slot, result)
    if args.keyword_only:
        step_keyword(argv, args, result)
    for slot in args.vars_keyword:
        step_varkey(argv, slot, result)
    # TODO: let the user decide whether to return the Args model or raw data
    # if args.origin:
    #     return args.origin.load(result)
    return result


def handle_option(argv: Argv, opt: Option, name_validated: bool) -> tuple[Any, dict[str, Any]]:
    """
    处理 `Option` 部分

    _Args:
        argv (Argv): 命令行参数
        opt (Option): 目标 `Option`
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
                raise InvalidParam(lang.require("option", "name_error").format(source=opt.dest, target=name), opt)
            for al in opt.aliases:
                if levenshtein(name, al) >= argv.fuzzy_threshold:
                    raise FuzzyMatchSuccess(lang.require("fuzzy", "matched").format(source=al, target=name))
            raise InvalidParam(lang.require("option", "name_error").format(source=opt.dest, target=name), opt)
    if opt.nargs:
        return ..., analyse_args(argv, opt.args)
    return _cnt or opt.action.value, {}


def analyse_option(analyser: Analyser, opt: Option, argv: Argv, path: tuple[str, ...], name_validated: bool):
    """
    分析 `Option` 部分

    _Args:
        analyser (SubAnalyser): 当前解析器
        argv (Argv): 命令行参数
        opt (Option): 目标 `Option`
        name_validated (bool): 是否已经验证过名称
    """
    value, args = handle_option(argv, opt, name_validated)
    if path not in analyser.value_result:
        analyser.value_result[path] = value
        analyser.args_result[path] = args
        if opt.action.type == 1 and args:
            for key in list(args.keys()):
                analyser.args_result[path][key] = [args[key]]
    elif opt.action.type == 0:  # cover the old value
        analyser.value_result[path] = value
        analyser.args_result[path] = args
    elif opt.action.type == 2:
        if not opt.nargs:
            analyser.value_result[path] += value
        else:
            analyser.value_result[path] = value
    elif not opt.nargs:  # opt.action.type == 1
        source = analyser.value_result[path][:]
        source.extend(value)
        analyser.value_result[path] = source
    else:
        for key, value in analyser.args_result[path].items():
            if key in args:
                analyser.args_result[path][key].append(value)
            else:
                analyser.args_result[path][key] = [value]


def analyse_compact_params(analyser: Analyser, argv: Argv, prefixes: tuple[str, ...]):
    """分析紧凑参数

    _Args:
        analyser (SubAnalyser): 当前解析器
        argv (Argv): 命令行参数
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
                try:
                    analyse_subcommand(analyser, sparam, argv, path, False)
                except (FuzzyMatchSuccess, PauseTriggered):
                    raise
                except InvalidParam as e:
                    if e.context_node is not sparam:
                        analyser.value_result[path] = ...
                    if not argv.error:
                        argv.error = e
                except AnalyseException as e1:
                    analyser.value_result[path] = ...
                    if not argv.error:
                        argv.error = e1
                else:
                    analyser.value_result[path] = ...
            _data.clear()
            return True
        except InvalidParam as e:
            if e.context_node is not param:
                exc = e
            else:
                argv.data_reset(_data, _index)
    else:
        if exc and not argv.error:
            argv.error = exc
        return False


def analyse_subcommand(analyser: Analyser, sub: Subcommand, argv: Argv, path: tuple[str, ...], name_validated: bool = True):
    if not name_validated:
        name, _ = argv.next(sub.separators)
        if name not in sub.aliases:
            argv.rollback(name)
            if not argv.fuzzy_match:
                raise InvalidParam(lang.require("subcommand", "name_error").format(source=sub.dest, target=name), sub)
            for al in sub.aliases:
                if levenshtein(name, al) >= argv.fuzzy_threshold:
                    raise FuzzyMatchSuccess(lang.require("fuzzy", "matched").format(source=al, target=name), sub)
            raise InvalidParam(lang.require("subcommand", "name_error").format(source=sub.dest, target=name), sub)

    # self.value_result = sub.action.value
    argv.stack_params.enter(sub._lookup_map)
    while analyse_param(analyser, sub, argv, path, sub.separators) and argv.current_index != argv.ndata:
        pass
    if analyser.default_main_only[path] and not analyser.args_result.get(path):
        analyser.args_result[path] = analyse_args(argv, sub.args)
    if not analyser.args_result.get(path) and analyser.need_main_args[path]:
        raise ArgumentMissing(
            sub.args.data[0].field.get_missing_tips(
                lang.require("subcommand", "args_missing").format(name=".".join(path))
            ),
            sub
        )
    argv.stack_params.leave()
    return


def analyse_param(analyser: Analyser, current: Subcommand, argv: Argv, prefixes: tuple[str, ...], seps: str | None = None):
    """处理参数

    _Args:
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
        # Help 之类的选项是 Option 子类, 得加上 __base__ 判断
        path = prefixes + (_param.dest,)
        if _param.__class__ is Option or _param.__class__.__base__ is Option:
            oparam: Option = _param  # type: ignore
            try:
                # 因为 _text 已经被确定为选项名，所以 name_validated 为 True
                analyse_option(analyser, oparam,argv, path, True)
            except AnalyseException as e:
                if not argv.error:
                    argv.error = e
            return True
        sparam: Subcommand = _param  # type: ignore
        # 禁止子命令重复解析
        if path not in analyser.value_result:
            try:
                analyse_subcommand(analyser, sparam, argv, path, True)
            except (FuzzyMatchSuccess, PauseTriggered):
                raise
            except InvalidParam as e:
                if e.context_node is not sparam:
                    analyser.value_result[path] = ...
                if not argv.error:
                    argv.error = e
            except AnalyseException as e1:
                analyser.value_result[path] = ...
                if not argv.error:
                    argv.error = e1
            else:
                analyser.value_result[path] = ...
            return True
    # 如果没有命中，则说明当前参数可能存在自定义分隔符，或者属于子命令的主参数，那么需要重新解析
    argv.rollback(_text)
    # 尝试以紧凑参数解析
    if _str and _text and analyser.compact_params and prefixes in analyser.compact_params and analyse_compact_params(analyser, argv, prefixes):
        return True
    # 主参数同样只允许解析一次
    if current.nargs and prefixes not in analyser.args_result:
        res = analyse_args(argv, current.args)
        if res:
            analyser.args_result[prefixes] = res
            return True
    # 若参数属于该子命令的同级/上级选项或子命令，则终止解析
    if _str and _text and _text in argv.stack_params.parents():
        return False
    if analyser.extra_allow:
        analyser.args_result[prefixes].setdefault("$extra", []).append(_text)
        argv.next()
        return True
    # 给 Completion 打的洞，若此时 analyser 属于主命令, 则让其先解析完主命令
    elif _str and _text and not argv.stack_params.stack:
        if not argv.error:
            argv.error = ParamsUnmatched(lang.require("analyser", "param_unmatched").format(target=_text))
        argv.next()
        return True
    return False


def analyse_header(header: "Header", argv: Argv):
    content = header.content
    head_text, _str = argv.next()
    if _str:
        if head_text in content:
            return HeadResult(head_text, head_text, True)
        if header.compact and (mat := header.compact_pattern.match(head_text)):
            argv.rollback(head_text[len(mat[0]):], replace=True)
            return HeadResult(mat[0], mat[0], True)
    may_cmd, _m_str = argv.next()
    if _m_str:
        cmd = f"{head_text}{argv.separators[0]}{may_cmd}"
        if cmd in content:
            return HeadResult(cmd, cmd, True)
        if header.compact and (mat := header.compact_pattern.match(cmd)):
            argv.rollback(cmd[len(mat[0]):], replace=True)
            return HeadResult(mat[0], mat[0], True)
    # _after_analyse_header
    if _str:
        argv.rollback(may_cmd)
        raise InvalidHeader(lang.require("header", "error").format(target=head_text), head_text)
    if _m_str and may_cmd:
        cmd = f"{head_text}{argv.separators[0]}{may_cmd}"
        raise InvalidHeader(lang.require("header", "error").format(target=cmd), cmd)
    argv.rollback(may_cmd)
    raise InvalidHeader(lang.require("header", "error").format(target=head_text), None)


def handle_head_fuzzy(header: Header, source: str, threshold: float):
    command = header.origin[0]
    if not header.origin[1]:
        headers_text = [str(command)]
    else:
        headers_text = []
        for prefix in header.origin[1]:
            if isinstance(prefix, tuple):
                headers_text.append(f"{prefix[0]} {prefix[1]}{command}")
            elif isinstance(prefix, str):
                headers_text.append(f"{prefix}{command}")
            else:
                headers_text.append(f"{prefix} {command}")
    for ht in headers_text:
        if levenshtein(source, ht) >= threshold:
            return lang.require("fuzzy", "matched").format(target=source, source=ht)
