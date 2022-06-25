from ..components.output import output_manager
from ..base import ShortcutOption
from .parts import analyse_option
from .analyser import Analyser


def handle_help(analyser: Analyser):
    analyser.current_index, analyser.content_index = analyser.head_pos
    _help_param = [str(i) for i in analyser.release() if i not in {"-h", "--help"}]

    def _get_help():
        formatter = analyser.alconna.formatter_type(analyser.alconna)
        return formatter.format_node(_help_param)

    output_manager.get(analyser.alconna.name, _get_help).handle(is_raise_exception=analyser.is_raise_exception)
    return analyser.export(fail=True)


def handle_shortcut(analyser: Analyser):
    opt_v = analyse_option(analyser, ShortcutOption)[1]['args']
    try:
        msg = analyser.alconna.shortcut(
            opt_v['name'], None if opt_v['command'] == "_" else analyser.converter(opt_v['command']),
            bool(opt_v.get('delete')), opt_v['expiration']
        )
        output_manager.get(analyser.alconna.name, lambda: msg).handle(is_raise_exception=analyser.is_raise_exception)
    except Exception as e:
        output_manager.get(analyser.alconna.name, lambda: str(e)).handle(is_raise_exception=analyser.is_raise_exception)
    return analyser.export(fail=True)
