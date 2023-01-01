from __future__ import annotations

from typing import TYPE_CHECKING 
from nepattern import Empty
from ..components.output import output_manager
from ..base import Subcommand, Option
from ..args import Arg, Args
from ..config import config
from ..exceptions import ParamsUnmatched
from .parts import analyse_args

if TYPE_CHECKING:
    from .analyser import Analyser


def handle_help(analyser: Analyser):
    _help_param = [str(i) for i in analyser.release(recover=True, move_head=True) if i not in analyser.special]
    output_manager.send(
        analyser.alconna.name,
        lambda: analyser.alconna.formatter_type(analyser.alconna).format_node(_help_param),
        analyser.raise_exception
    )
    return analyser.export(fail=True)


def handle_shortcut(analyser: Analyser):
    analyser.popitem()
    opt_v = analyse_args(analyser, Args["delete;?", "delete"]["name", str]["command", str, "_"], 3)
    try:
        msg = analyser.alconna.shortcut(
            opt_v["name"],
            None if opt_v["command"] == "_" else analyser.converter(opt_v["command"]),
            bool(opt_v.get("delete"))
        )
        output_manager.send(analyser.alconna.name, lambda: msg, analyser.raise_exception)
    except Exception as e:
        output_manager.send(analyser.alconna.name, lambda: str(e), analyser.raise_exception)
    return analyser.export(fail=True)


def _handle_unit(analyser: Analyser, trigger: Arg):
    if gen := trigger.field.completion:
        comp = gen()
        if isinstance(comp, str):
            return output_manager.send(analyser.alconna.name, lambda: comp, analyser.raise_exception)
        target = analyser.release(recover=True)[-2]
        o = "\n- ".join(list(filter(lambda x: target in x, comp)) or comp)
        return output_manager.send(
            analyser.alconna.name, lambda: f"{config.lang.common_completion_arg}\n- {o}", analyser.raise_exception
        )
    default = trigger.field.default_gen
    o = f"{trigger.value}{'' if default is None else f' default:({None if default is Empty else default})'}"
    return output_manager.send(
        analyser.alconna.name, lambda: f"{config.lang.common_completion_arg}\n{o}", analyser.raise_exception
    )


def _handle_sentence(analyser: Analyser):
    res: list[str] = []
    s_len = len(stc := analyser.sentences)
    for opt in filter(
        lambda x: len(x.requires) >= s_len and x.requires[s_len - 1] == stc[-1],
        analyser.alconna.options,
    ):
        if len(opt.requires) > s_len:
            res.append(opt.requires[s_len])
        else:
            res.extend(opt.aliases if isinstance(opt, Option) else [opt.name])
    return res


def _handle_none(analyser: Analyser, got: list[str]):
    res: list[str] = []
    if not analyser.main_args and analyser.self_args.argument:
        unit = analyser.self_args.argument[0]
        if gen := unit.field.completion:
            res.append(comp if isinstance(comp := gen(), str) else "\n- ".join(comp))
        else:
            default = unit.field.default_gen
            res.append(
                f"{unit.value}{'' if default is None else f' ({None if default is Empty else default})'}"
            )
    for opt in filter(
        lambda x: x.name not in analyser.alconna.namespace_config.builtin_option_name['completion'],
        analyser.alconna.options,
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
            analyser.alconna.name,
            lambda: f"{config.lang.common_completion_node}\n- " + "\n- ".join(trigger.sub_params),
            analyser.raise_exception
        )
    elif isinstance(trigger, str):
        res = list(filter(lambda x: trigger in x, analyser.command_params))
        if not res:
            return analyser.export(
                fail=True,
                exception=ParamsUnmatched(config.lang.analyser_param_unmatched.format(target=trigger)),
            )
        out = [i for i in res if i not in (*analyser.options.keys(), *analyser.subcommands.keys(), *analyser.sentences)]
        output_manager.send(
            analyser.alconna.name,
            lambda: f"{config.lang.common_completion_node}\n- " + "\n- ".join(out or res),
            analyser.raise_exception
        )
    else:
        got = [*analyser.options.keys(), *analyser.subcommands.keys(), *analyser.sentences]
        target = analyser.release(recover=True)[-1]
        if _res := list(filter(lambda x: target in x and target != x, analyser.command_params)):
            out = [i for i in _res if i not in got]
            output_manager.send(
                analyser.alconna.name,
                lambda: f"{config.lang.common_completion_node}\n- " + "\n- ".join(out or _res),
                analyser.raise_exception
            )
        else:
            res = _handle_sentence(analyser) if analyser.sentences else _handle_none(analyser, got)
            output_manager.send(
                analyser.alconna.name,
                lambda: f"{config.lang.common_completion_node}\n- " + "\n- ".join(set(res)),
                analyser.raise_exception
            )
    return analyser.export(fail=True, exception='NoneType: None\n')  # type: ignore
