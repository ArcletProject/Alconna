from ..components.output import output_send
from ..base import ShortcutOption
from .parts import analyse_option
from .analyser import Analyser


def handle_help(analyser: Analyser):
    _help_param = analyser.recover_raw_data()
    _help_param[0] = _help_param[0].replace("--help", "", 1).replace("-h", "", 1).lstrip()

    def _get_help():
        formatter = analyser.alconna.formatter_type(analyser.alconna)
        return formatter.format_node(_help_param)

    output_send(analyser.alconna.name, _get_help).handle({}, is_raise_exception=analyser.is_raise_exception)
    return analyser.export(fail=True)


def handle_shortcut(analyser: Analyser):
    def _shortcut(sct: str, command: str, expiration: int, delete: bool):
        return analyser.alconna.shortcut(
            sct, None if command == "_" else analyser.converter(command), delete, expiration
        )

    _, opt_v = analyse_option(analyser, ShortcutOption)
    try:
        msg = _shortcut(
            opt_v['args']['name'], opt_v['args']['command'],
            opt_v['args']['expiration'], True if opt_v['args'].get('delete') else False
        )
        output_send(analyser.alconna.name, lambda: msg).handle({}, is_raise_exception=analyser.is_raise_exception)
    except Exception as e:
        output_send(analyser.alconna.name, lambda: str(e)).handle({}, is_raise_exception=analyser.is_raise_exception)
    return analyser.export(fail=True)
