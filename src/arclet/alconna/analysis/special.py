from typing import TYPE_CHECKING, Union
from nepattern import Empty
from ..components.output import output_manager
from ..base import ShortcutOption, Subcommand, Option
from ..args import ArgUnit
from ..config import config
from ..exceptions import ParamsUnmatched
from .parts import analyse_option

if TYPE_CHECKING:
    from .analyser import Analyser


def handle_help(analyser: 'Analyser'):
    analyser.current_index, analyser.content_index = analyser.head_pos
    _help_param = [str(i) for i in analyser.release() if i not in {"-h", "--help"}]

    def _get_help():
        formatter = analyser.alconna.formatter_type(analyser.alconna)
        return formatter.format_node(_help_param)

    output_manager.get(analyser.alconna.name, _get_help).handle(raise_exception=analyser.raise_exception)
    return analyser.export(fail=True)


def handle_shortcut(analyser: 'Analyser'):
    opt_v = analyse_option(analyser, ShortcutOption)[1]['args']
    try:
        msg = analyser.alconna.shortcut(
            opt_v['name'], None if opt_v['command'] == "_" else analyser.converter(opt_v['command']),
            bool(opt_v.get('delete')), opt_v['expiration']
        )
        output_manager.get(analyser.alconna.name, lambda: msg).handle(raise_exception=analyser.raise_exception)
    except Exception as e:
        output_manager.get(analyser.alconna.name, lambda: str(e)).handle(raise_exception=analyser.raise_exception)
    return analyser.export(fail=True)


def handle_completion(
        analyser: 'Analyser',
        trigger: Union[None, ArgUnit, Subcommand, str] = None
):
    r_e = analyser.raise_exception
    if isinstance(trigger, dict):
        trigger: ArgUnit
        if gen := trigger['field'].completion:
            output_manager.get(analyser.alconna.name, lambda: gen()).handle(raise_exception=r_e)
        else:
            default = trigger['field'].default_gen
            o = f"{trigger['value']}{'' if default is None else f' default:({None if default is Empty else default})'}"
            output_manager.get(analyser.alconna.name, lambda: f'next arg:\n{o}').handle(raise_exception=r_e)
    elif isinstance(trigger, Subcommand):
        output_manager.get(
            analyser.alconna.name, lambda: 'next input maybe:\n- ' + '\n- '.join(trigger.sub_params)
        ).handle(raise_exception=r_e)
    elif isinstance(trigger, str):
        res = list(filter(lambda x: x.startswith(trigger), analyser.command_params))
        if not res:
            return analyser.export(
                fail=True, exception=ParamsUnmatched(config.lang.analyser_param_unmatched.format(target=trigger))
            )
        output_manager.get(analyser.alconna.name, lambda: 'next input maybe:\n- ' + '\n- '.join(res)).handle(
            raise_exception=r_e
        )
    else:
        res = []
        if analyser.sentences:
            s_len = len(stc := analyser.sentences)
            for opt in filter(
                lambda x: len(x.requires) >= s_len and x.requires[s_len - 1] == stc[-1], analyser.alconna.options
            ):
                res.extend(
                    [opt.requires[s_len]] if len(opt.requires) > s_len else
                    (opt.aliases if isinstance(opt, Option) else [opt.name])
                )
        else:
            for opt in filter(lambda x: x.name not in ("--shortcut", "--comp"), analyser.alconna.options):
                res.extend(
                    [opt.requires[0]] if opt.requires else
                    (opt.aliases if isinstance(opt, Option) else [opt.name])
                )
        output_manager.get(analyser.alconna.name, lambda: 'next input maybe:\n- ' + '\n- '.join(set(res))).handle(
            raise_exception=r_e
        )
    return analyser.export(fail=True)
