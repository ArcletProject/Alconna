from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from .analyser import TAnalyser, SubAnalyser
from ..typing import TDataCollection
from ..base import Option, Subcommand
from ..model import Sentence
from ..config import Namespace

if TYPE_CHECKING:
    from ..arparma import Arparma
    from ..core import Alconna


def _compile_opts(option: Option, data: dict[str, Sentence | list[Option] | SubAnalyser]):
    for alias in option.aliases:
        if (li := data.get(alias)) and isinstance(li, list):
            li.append(option)  # type: ignore
            li.sort(key=lambda x: x.priority, reverse=True)
        else:
            data[alias] = [option]



def default_params_parser(analyser: SubAnalyser, _config: Namespace):
    require_len = 0
    for opts in analyser.command.options:
        if isinstance(opts, Option):
            _compile_opts(opts, analyser.compile_params)  # type: ignore
            analyser.container.param_ids.update(opts.aliases)
        elif isinstance(opts, Subcommand):
            sub = SubAnalyser(opts, analyser.container, _config, analyser.fuzzy_match)
            analyser.compile_params[opts.name] = sub
            analyser.container.param_ids.add(opts.name)
            default_params_parser(sub, _config)
        if not set(analyser.container.separators).issuperset(opts.separators):
            analyser.container.default_separate &= False
        if opts.requires:
            analyser.container.param_ids.update(opts.requires)
            require_len = max(len(opts.requires), require_len)
            for k in opts.requires:
                analyser.compile_params.setdefault(k, Sentence(name=k))
    analyser.part_len = range(
        len(analyser.command.options) + analyser.need_main_args + require_len
    )


def compile(alconna: Alconna[TAnalyser], params_parser: Callable[[TAnalyser, Namespace], None] = default_params_parser) -> TAnalyser:
    _analyser = alconna.analyser_type(alconna)
    params_parser(_analyser, alconna.namespace_config)
    return _analyser


def analyse(alconna: Alconna, command: TDataCollection) -> Arparma[TDataCollection]:
    return compile(alconna).process(command).analyse().execute()
