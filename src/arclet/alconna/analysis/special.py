from typing import TYPE_CHECKING, Union, List
from nepattern import Empty
from ..components.output import output_manager
from ..base import Subcommand, Option
from ..args import ArgUnit
from ..builtin import ShortcutOption
from ..config import config
from ..exceptions import ParamsUnmatched
from .parts import analyse_option

if TYPE_CHECKING:
    from .analyser import Analyser


def handle_help(analyser: "Analyser"):
    analyser.current_index, analyser.content_index = analyser.head_pos
    _help_param = [str(i) for i in analyser.release() if i not in {"-h", "--help"}]

    def _get_help():
        formatter = analyser.alconna.formatter_type(analyser.alconna)
        return formatter.format_node(_help_param)

    output_manager.get(analyser.alconna.name, _get_help).handle(
        raise_exception=analyser.raise_exception
    )
    return analyser.export(fail=True)


def handle_shortcut(analyser: "Analyser"):
    opt_v = analyse_option(analyser, ShortcutOption)[1]["args"]
    try:
        msg = analyser.alconna.shortcut(
            opt_v["name"],
            None if opt_v["command"] == "_" else analyser.converter(opt_v["command"]),
            bool(opt_v.get("delete"))
        )
        output_manager.get(analyser.alconna.name, lambda: msg).handle(
            raise_exception=analyser.raise_exception
        )
    except Exception as e:
        output_manager.get(analyser.alconna.name, lambda: str(e)).handle(
            raise_exception=analyser.raise_exception
        )
    return analyser.export(fail=True)


def _handle_unit(analyser: "Analyser", trigger: ArgUnit):
    if gen := trigger["field"].completion:
        comp = gen()
        if isinstance(comp, str):
            return output_manager.get(analyser.alconna.name, lambda: gen()).handle(
                raise_exception=analyser.raise_exception
            )
        target = analyser.release(recover=True)[-2]
        o = "\n- ".join(list(filter(lambda x: target in x, comp)) or comp)
        return output_manager.get(
            analyser.alconna.name, lambda: f"{config.lang.common_completion_arg}\n- {o}"
        ).handle(raise_exception=analyser.raise_exception)
    default = trigger["field"].default_gen
    o = f"{trigger['value']}{'' if default is None else f' default:({None if default is Empty else default})'}"
    return output_manager.get(
        analyser.alconna.name, lambda: f"{config.lang.common_completion_arg}\n{o}"
    ).handle(raise_exception=analyser.raise_exception)


def _handle_sentence(analyser: "Analyser"):
    res: List[str] = []
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


def _handle_none(analyser: "Analyser", got: List[str]):
    res: List[str] = []
    if not analyser.main_args and analyser.self_args.argument:
        unit = list(analyser.self_args.argument.values())[0]
        if gen := unit["field"].completion:
            res.append(comp if isinstance(comp := gen(), str) else "\n- ".join(comp))
        else:
            default = unit["field"].default_gen
            res.append(
                f"{unit['value']}{'' if default is None else f' ({None if default is Empty else default})'}"
            )
    for opt in filter(
        lambda x: x.name not in ("--shortcut", "--comp"),
        analyser.alconna.options,
    ):
        if opt.requires and all(opt.requires[0] not in i for i in got):
            res.append(opt.requires[0])
        elif opt.dest not in got:
            res.extend(opt.aliases if isinstance(opt, Option) else [opt.name])
    return res


def handle_completion(
    analyser: "Analyser", trigger: Union[None, ArgUnit, Subcommand, str] = None
):
    if isinstance(trigger, dict):
        _handle_unit(analyser, trigger)
    elif isinstance(trigger, Subcommand):
        output_manager.get(
            analyser.alconna.name,
            lambda: f"{config.lang.common_completion_node}\n- "
            + "\n- ".join(trigger.sub_params),
        ).handle(raise_exception=analyser.raise_exception)
    elif isinstance(trigger, str):
        res = list(filter(lambda x: trigger in x, analyser.command_params))
        if not res:
            return analyser.export(
                fail=True,
                exception=ParamsUnmatched(
                    config.lang.analyser_param_unmatched.format(target=trigger)
                ),
            )
        out = [i for i in res if i not in (*analyser.options.keys(), *analyser.subcommands.keys(), *analyser.sentences)]
        output_manager.get(
            analyser.alconna.name,
            lambda: f"{config.lang.common_completion_node}\n- "
            + "\n- ".join(out or res),
        ).handle(raise_exception=analyser.raise_exception)
    else:
        got = [*analyser.options.keys(), *analyser.subcommands.keys(), *analyser.sentences]
        target = analyser.release(recover=True)[-2]
        if _res := list(filter(lambda x: target in x and target != x, analyser.command_params)):
            out = [i for i in _res if i not in got]
            output_manager.get(
                analyser.alconna.name,
                lambda: f"{config.lang.common_completion_node}\n- " + "\n- ".join(out or _res),
            ).handle(raise_exception=analyser.raise_exception)
        else:
            res = (
                _handle_sentence(analyser)
                if analyser.sentences
                else _handle_none(analyser, got)
            )
            output_manager.get(
                analyser.alconna.name,
                lambda: f"{config.lang.common_completion_node}\n- " + "\n- ".join(set(res)),
            ).handle(raise_exception=analyser.raise_exception)
    return analyser.export(fail=True, exception='NoneType: None\n')  # type: ignore
