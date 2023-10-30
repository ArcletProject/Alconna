from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Iterable

from nepattern import AllParam, AnyOne, AnyString, BasePattern
from nepattern.util import TPattern
from tarina import Empty, lang, split_once

from ..action import Action
from ..args import STRING, Arg, Args
from ..base import Option, Subcommand
from ..completion import Prompt, comp_ctx
from ..config import config
from ..exceptions import ArgumentMissing, FuzzyMatchSuccess, InvalidParam, PauseTriggered, SpecialOptionTriggered
from ..model import HeadResult, OptionResult, Sentence
from ..output import output_manager
from ..typing import KWBool
from ._header import Double, Header
from ._util import escape, levenshtein, unescape

if TYPE_CHECKING:
    from ._analyser import Analyser, SubAnalyser
    from ._argv import Argv

pat = re.compile("(?:-*no)?-*(?P<name>.+)")


def _validate(argv: Argv, target: Arg[Any], value: BasePattern[Any], result: dict[str, Any], arg: Any, _str: bool):
    if value == AnyOne or (value == STRING and _str):
        result[target.name] = arg
        return
    if value == AnyString:
        result[target.name] = str(arg)
        return
    default_val = target.field.default
    res = value.invalidate(arg, default_val) if value.anti else value.validate(arg, default_val)
    if res.flag != "valid":
        argv.rollback(arg)
    if res.flag == "error":
        if target.optional:
            return
        raise InvalidParam(target.field.get_unmatch_tips(arg, res.error.args[0]))
    result[target.name] = res._value  # noqa


def step_varpos(argv: Argv, args: Args, result: dict[str, Any]):
    value, arg = args.argument.var_positional
    argv.context = arg
    key = arg.name
    default_val = arg.field.default
    _result = []
    kwonly_seps = tuple(arg.value.sep for arg in args.argument.keyword_only.values())  # type: ignore
    loop = len(argv.release(arg.separators))
    if value.length > 0:
        loop = min(loop, value.length)
    for _ in range(loop):
        may_arg, _str = argv.next(arg.separators)
        if _str and may_arg in argv.special:
            if argv.special[may_arg] not in argv.namespace.disable_builtin_options:
                raise SpecialOptionTriggered(argv.special[may_arg])
        if not may_arg or (_str and may_arg in argv.param_ids):
            argv.rollback(may_arg)
            break
        if _str and kwonly_seps and split_once(pat.match(may_arg)["name"], kwonly_seps, argv.filter_crlf)[0] in args.argument.keyword_only:  # noqa: E501
            argv.rollback(may_arg)
            break
        if _str and args.argument.var_keyword and args.argument.var_keyword[0].base.sep in may_arg:  # type: ignore
            argv.rollback(may_arg)
            break
        if (res := value.base.exec(may_arg)).flag != "valid":
            argv.rollback(may_arg)
            break
        _result.append(res._value)  # noqa
    if not _result:
        if default_val is not None:
            _result = default_val if isinstance(default_val, Iterable) else ()
        elif value.flag == "*":
            _result = ()
        else:
            raise ArgumentMissing(arg.field.get_missing_tips(lang.require("args", "missing").format(key=key)))
    result[key] = tuple(_result)


def step_varkey(argv: Argv, args: Args, result: dict[str, Any]):
    value, arg = args.argument.var_keyword
    argv.context = arg
    name = arg.name
    default_val = arg.field.default
    _result = {}
    loop = len(argv.release(arg.separators))
    if value.length > 0:
        loop = min(loop, value.length)
    for _ in range(loop):
        may_arg, _str = argv.next(arg.separators)
        if _str and may_arg in argv.special:
            if argv.special[may_arg] not in argv.namespace.disable_builtin_options:
                raise SpecialOptionTriggered(argv.special[may_arg])
        if not may_arg or (_str and may_arg in argv.param_ids) or not _str:
            argv.rollback(may_arg)
            break
        if not (_kwarg := re.match(rf"^(-*[^{value.base.sep}]+){value.base.sep}(.*?)$", may_arg)):
            argv.rollback(may_arg)
            break
        key = _kwarg[1]
        if not (_m_arg := _kwarg[2]):
            _m_arg, _ = argv.next(arg.separators)
        if (res := value.base.base.exec(_m_arg)).flag != "valid":
            argv.rollback(may_arg)
            break
        _result[key] = res._value  # noqa
    if not _result:
        if default_val is not None:
            _result = default_val if isinstance(default_val, dict) else {}
        elif value.flag == "*":
            _result = {}
        else:
            raise ArgumentMissing(arg.field.get_missing_tips(lang.require("args", "missing").format(key=name)))
    result[name] = _result


def step_keyword(argv: Argv, args: Args, result: dict[str, Any]):
    kwonly_seps = set()
    for arg in args.argument.keyword_only.values():
        kwonly_seps.update(arg.separators)
    kwonly_seps1 = tuple(arg.value.sep for arg in args.argument.keyword_only.values())  # type: ignore
    target = len(args.argument.keyword_only)
    count = 0
    while count < target:
        may_arg, _str = argv.next(tuple(kwonly_seps))
        if _str and may_arg in argv.special:
            if argv.special[may_arg] not in argv.namespace.disable_builtin_options:
                raise SpecialOptionTriggered(argv.special[may_arg])
        if not may_arg or not _str:
            argv.rollback(may_arg)
            break
        key, _m_arg = split_once(may_arg, kwonly_seps1, argv.filter_crlf)
        _key = pat.match(key)["name"]
        if _key not in args.argument.keyword_only:
            _key = key
        if _key not in args.argument.keyword_only:
            argv.rollback(may_arg)
            if args.argument.var_keyword or (_str and may_arg in argv.param_ids):
                break
            for arg in args.argument.keyword_only.values():
                if arg.value.base.exec(may_arg).flag == "valid":  # type: ignore
                    raise InvalidParam(lang.require("args", "key_missing").format(target=may_arg, key=arg.name))
            for name in args.argument.keyword_only:
                if levenshtein(_key, name) >= config.fuzzy_threshold:
                    raise FuzzyMatchSuccess(lang.require("fuzzy", "matched").format(source=name, target=_key))
            raise InvalidParam(lang.require("args", "key_not_found").format(name=_key))
        arg = args.argument.keyword_only[_key]
        value = arg.value.base  # type: ignore
        if not _m_arg:
            if isinstance(value, KWBool):
                _m_arg = key
            else:
                _m_arg, _ = argv.next(args.argument.keyword_only[_key].separators)
        _validate(argv, arg, value, result, _m_arg, _str)
        count += 1

    if count < target:
        for key, arg in args.argument.keyword_only.items():
            if key in result:
                continue
            if arg.field.default is not None:
                result[key] = None if arg.field.default is Empty else arg.field.default
            elif not arg.optional:
                raise ArgumentMissing(arg.field.get_missing_tips(lang.require("args", "missing").format(key=key)))


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
    for arg in args.argument.normal:
        argv.context = arg
        may_arg, _str = argv.next(arg.separators)
        if _str and may_arg in argv.special:
            if argv.special[may_arg] not in argv.namespace.disable_builtin_options:
                raise SpecialOptionTriggered(argv.special[may_arg])
        if _str and may_arg in argv.param_ids and arg.optional:
            if (de := arg.field.default) is not None:
                result[arg.name] = None if de is Empty else de
            argv.rollback(may_arg)
            continue
        if not may_arg:
            argv.rollback(may_arg)
            if (de := arg.field.default) is not None:
                result[arg.name] = None if de is Empty else de
            elif not arg.optional:
                raise ArgumentMissing(arg.field.get_missing_tips(lang.require("args", "missing").format(key=arg.name)))
            continue
        value = arg.value
        if value == AllParam:
            argv.rollback(may_arg)
            result[arg.name] = argv.converter(argv.release(arg.separators))
            argv.current_index = argv.ndata
            return result
        _validate(argv, arg, value, result, may_arg, _str)
    if args.argument.unpack:
        arg, unpack = args.argument.unpack
        try:
            unpack.separate(*arg.separators)
            result[arg.name] = arg.value.origin(**analyse_args(argv, unpack))
        except Exception as e:
            if (de := arg.field.default) is not None:
                result[arg.name] = None if de is Empty else de
            elif not arg.optional:
                raise e
    if args.argument.var_positional:
        step_varpos(argv, args, result)
    if args.argument.keyword_only:
        step_keyword(argv, args, result)
    if args.argument.var_keyword:
        step_varkey(argv, args, result)
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
                argv.rollback(mat["rest"], replace=True)
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
        if argv.fuzzy_match and levenshtein(name, opt.name) >= config.fuzzy_threshold:
            raise FuzzyMatchSuccess(lang.require("fuzzy", "matched").format(source=name, target=opt.name))
        raise InvalidParam(lang.require("option", "name_error").format(source=opt.name, target=name))
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
        source.value = source.value[:]
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
                if param.requires and analyser.sentences != param.requires:
                    return lang.require("option", "require_error").format(
                        source=param.name, target=" ".join(analyser.sentences)
                    )
                analyse_option(analyser, argv, param)
            else:
                if param.command.requires and analyser.sentences != param.command.requires:
                    return lang.require("subcommand", "require_error").format(
                        source=param.command.name, target=" ".join(analyser.sentences)
                    )
                try:
                    param.process(argv)
                finally:
                    analyser.subcommands_result[param.command.dest] = param.result()
            _data.clear()
            return True
        except InvalidParam as e:
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
    if _str and _text in argv.special:
        if argv.special[_text] not in argv.namespace.disable_builtin_options:
            if _text in argv.completion_names:
                argv.bak_data[argv.current_index] = argv.bak_data[argv.current_index].replace(_text, "")
            raise SpecialOptionTriggered(argv.special[_text])
    if not _str or not _text:
        _param = None
    elif _text in analyser.compile_params:
        _param = analyser.compile_params[_text]
    elif analyser.compact_params and (res := analyse_compact_params(analyser, argv)):
        if res.__class__ is str:
            raise InvalidParam(res)
        argv.context = None
        return True
    else:
        _param = None
    if not _param and analyser.command.nargs and not analyser.args_result:
        analyser.args_result = analyse_args(argv, analyser.self_args)
        if analyser.args_result:
            argv.context = None
            return True
    if _param.__class__ is Sentence:
        analyser.sentences.append(argv.next()[0])
        return True
    if _param.__class__ is Option:
        if _param.requires and analyser.sentences != _param.requires:
            raise InvalidParam(
                lang.require("option", "require_error").format(source=_param.name, target=" ".join(analyser.sentences))
            )
        analyse_option(analyser, argv, _param)
    elif _param.__class__ is list:
        exc: Exception | None = None
        for opt in _param:
            _data, _index = argv.data_set()
            try:
                if opt.requires and analyser.sentences != opt.requires:
                    raise InvalidParam(
                        lang.require("option", "require_error").format(
                            source=opt.name, target=" ".join(analyser.sentences)
                        )
                    )
                analyser.sentences = []
                analyse_option(analyser, argv, opt)
                _data.clear()
                exc = None
                break
            except Exception as e:
                exc = e
                argv.data_reset(_data, _index)
        if exc:
            raise exc  # type: ignore  # noqa
    elif _param is not None:
        if _param.command.requires and analyser.sentences != _param.command.requires:
            raise InvalidParam(
                lang.require("subcommand", "require_error").format(
                    source=_param.command.name, target=" ".join(analyser.sentences)
                )
            )
        try:
            _param.process(argv)
        finally:
            analyser.subcommands_result[_param.command.dest] = _param.result()
    else:
        return False
    analyser.sentences.clear()
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
            argv.rollback(head_text[len(mat[0]) :], replace=True)
            return HeadResult(mat[0], mat[0], True, mat.groupdict(), mapping)
    if isinstance(content, BasePattern):
        if (val := content.exec(head_text, Empty)).success:
            return HeadResult(head_text, val.value, True, fixes=mapping)
        if header.compact and (val := header.compact_pattern.exec(head_text, Empty)).success:
            if _str:
                argv.rollback(head_text[len(str(val.value)) :], replace=True)
            return HeadResult(val.value, val.value, True, fixes=mapping)

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
        if argv.fuzzy_match:
            _handle_fuzzy(header, head_text)
        raise InvalidParam(lang.require("header", "error").format(target=head_text), head_text)
    if _m_str and may_cmd:
        if argv.fuzzy_match:
            _handle_fuzzy(header, f"{head_text} {may_cmd}")
        raise InvalidParam(lang.require("header", "error").format(target=may_cmd), may_cmd)
    argv.rollback(may_cmd)
    raise InvalidParam(lang.require("header", "error").format(target=head_text), None)


def _handle_fuzzy(header: Header, source: str):
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
        if levenshtein(source, ht) >= config.fuzzy_threshold:
            raise FuzzyMatchSuccess(lang.require("fuzzy", "matched").format(target=source, source=ht))


def handle_help(analyser: Analyser, argv: Argv):
    """处理帮助选项触发"""
    _help_param = [str(i) for i in argv.release(recover=True) if str(i) not in argv.special]
    output_manager.send(
        analyser.command.name,
        lambda: analyser.command.formatter.format_node(_help_param),
    )
    return analyser.export(argv, True, SpecialOptionTriggered("help"))


_args = Args["action?", "delete|list"]["name?", str]["command", str, "$"]


def handle_shortcut(analyser: Analyser, argv: Argv):
    """处理快捷命令触发"""
    argv.next()
    try:
        opt_v = analyse_args(argv, _args)
    except SpecialOptionTriggered:
        return handle_completion(analyser, argv)
    try:
        if opt_v.get("action") == "list":
            data = analyser.command.get_shortcuts()
            output_manager.send(analyser.command.name, lambda: "\n".join(data))
        else:
            if not opt_v.get("name"):
                raise ArgumentMissing(lang.require("shortcut", "name_require"))
            if opt_v.get("action") == "delete":
                msg = analyser.command.shortcut(opt_v["name"], delete=True)
            elif opt_v["command"] == "_":
                msg = analyser.command.shortcut(opt_v["name"], None)
            elif opt_v["command"] == "$":
                msg = analyser.command.shortcut(opt_v["name"], {})
            else:
                msg = analyser.command.shortcut(opt_v["name"], {"command": argv.converter(opt_v["command"])})
            output_manager.send(analyser.command.name, lambda: msg)
    except Exception as e:
        output_manager.send(analyser.command.name, lambda: str(e))
    return analyser.export(argv, True, SpecialOptionTriggered("shortcut"))


INDEX_SLOT = re.compile(r"\{%(\d+)\}")
WILDCARD_SLOT = re.compile(r"\{\*(.*)\}", re.DOTALL)


def _gen_extend(data: list, sep: str):
    extend = []
    for slot in data:
        if isinstance(slot, str) and extend and isinstance(extend[-1], str):
            extend[-1] += sep + slot
        else:
            extend.append(slot)
    return extend


def _handle_multi_slot(argv: Argv, unit: str, data: list, index: int, current: int, offset: int):
    slot = data[index]
    if not isinstance(slot, str):
        left, right = unit.split(f"{{%{index}}}", 1)
        if left.strip():
            argv.raw_data[current] = left.strip()
        argv.raw_data.insert(current + 1, slot)
        if right.strip():
            argv.raw_data[current + 2] = right.strip()
            offset += 1
    else:
        argv.raw_data[current + offset] = unescape(unit.replace(f"{{%{index}}}", slot))
    return offset


def _handle_shortcut_data(argv: Argv, data: list):
    data_len = len(data)
    if not data_len:
        return []
    record = set()
    offset = 0
    for i, unit in enumerate(argv.raw_data.copy()):
        if not isinstance(unit, str):
            continue
        unit = escape(unit)
        if mat := INDEX_SLOT.fullmatch(unit):
            index = int(mat[1])
            if index >= data_len:
                continue
            argv.raw_data[i + offset] = data[index]
            record.add(index)
        elif res := INDEX_SLOT.findall(unit):
            for index in map(int, res):
                if index >= data_len:
                    continue
                offset = _handle_multi_slot(argv, unit, data, index, i, offset)
                record.add(index)
        elif mat := WILDCARD_SLOT.search(unit):
            extend = _gen_extend(data, mat[1] or " ")
            if unit == f"{{*{mat[1]}}}":
                argv.raw_data.extend(extend)
            else:
                argv.raw_data[i + offset] = unescape(unit.replace(f"{{*{mat[1]}}}", "".join(map(str, extend))))
            data.clear()
            break
    return [unit for i, unit in enumerate(data) if i not in record]


def _handle_shortcut_reg(argv: Argv, groups: tuple[str, ...], gdict: dict[str, str]):
    for j, unit in enumerate(argv.raw_data):
        if not isinstance(unit, str):
            continue
        unit = escape(unit)
        for i, c in enumerate(groups):
            unit = unit.replace(f"{{{i}}}", c)
        for k, v in gdict.items():
            unit = unit.replace(f"{{{k}}}", v)
        argv.raw_data[j] = unescape(unit)


def _prompt_unit(analyser: Analyser, argv: Argv, trig: Arg):
    if comp := trig.field.get_completion():
        if isinstance(comp, str):
            return [Prompt(comp, False)]
        releases = argv.release(recover=True)
        target = str(releases[-1]) or str(releases[-2])
        o = list(filter(lambda x: target in x, comp)) or comp
        return [Prompt(i, False, target) for i in o]
    return [Prompt(analyser.command.formatter.param(trig), False)]


def _prompt_sentence(analyser: Analyser):
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
    return [Prompt(i) for i in res]


def _prompt_none(analyser: Analyser, argv: Argv, got: list[str]):
    res: list[Prompt] = []
    if not analyser.args_result and analyser.self_args.argument:
        unit = analyser.self_args.argument[0]
        if comp := unit.field.get_completion():
            res.extend([Prompt(comp, False)] if isinstance(comp, str) else [Prompt(i, False) for i in comp])
        else:
            res.append(Prompt(analyser.command.formatter.param(unit), False))
    for opt in filter(
        lambda x: x.name not in (argv.special if len(analyser.command.options) > 3 else argv.completion_names),
        analyser.command.options,
    ):
        if opt.requires and all(opt.requires[0] not in i for i in got):
            res.append(Prompt(opt.requires[0]))
        elif opt.dest not in got:
            res.extend([Prompt(al) for al in opt.aliases] if isinstance(opt, Option) else [Prompt(opt.name)])
    return res


def prompt(analyser: Analyser, argv: Argv, trigger: str | None = None):
    """获取补全列表"""
    _trigger = trigger or argv.context
    got = [*analyser.options_result.keys(), *analyser.subcommands_result.keys(), *analyser.sentences]
    if isinstance(_trigger, Arg):
        return _prompt_unit(analyser, argv, _trigger)
    elif isinstance(_trigger, Subcommand):
        return [Prompt(i) for i in analyser.get_sub_analyser(_trigger).compile_params]
    elif isinstance(_trigger, str):
        res = list(filter(lambda x: _trigger in x, analyser.compile_params))
        if not res:
            return []
        out = [i for i in res if i not in got]
        return [Prompt(i, True, _trigger) for i in (out or res)]
    releases = argv.release(recover=True)
    target = str(releases[-1]) or str(releases[-2])
    if _res := list(filter(lambda x: target in x and target != x, analyser.compile_params)):
        out = [i for i in _res if i not in got]
        return [Prompt(i, True, target) for i in (out or _res)]
    return _prompt_sentence(analyser) if analyser.sentences else _prompt_none(analyser, argv, got)


def handle_completion(analyser: Analyser, argv: Argv, trigger: str | None = None):
    """处理补全选项触发"""
    if res := prompt(analyser, argv, trigger):
        if comp_ctx.get(None):
            raise PauseTriggered(res, trigger)
        output_manager.send(
            analyser.command.name,
            lambda: f"{lang.require('completion', 'node')}\n* " + "\n* ".join([i.text for i in res]),
        )
    return analyser.export(argv, True, SpecialOptionTriggered("completion"))  # type: ignore
