from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .arparma import Arparma
from .base import Subcommand, SPECIAL_OPTIONS, Option
from .args import Arg
from .i18n import i18n

if TYPE_CHECKING:
    from .core import Alconna


@dataclass(eq=True, frozen=True, unsafe_hash=True)
class Prompt:
    text: str = field(hash=True)
    can_use: bool = field(default=True, hash=False)
    removal_prefix: str | None = field(default=None, hash=False)


@dataclass
class EnterResult:
    result: Arparma | None = None
    exception: type[Exception] | Exception | None = None


def _prompt_none(command: Alconna, args_got: list[str], opts_got: list[tuple[str, ...]]):
    res: list[Prompt] = []
    if unit := next((arg for arg in command.args if arg.name not in args_got), None):
        template = i18n.require("completion.prompt_arg")
        if not (comp := unit.field.get_completion()):
            res.append(Prompt(command.formatter.param(unit), False))
        elif isinstance(comp, str):
            res.append(Prompt(template.format(name=unit.name, prompt=comp), False))
        else:
            res.extend(Prompt(template.format(name=unit.name, prompt=i), False) for i in comp)
    for opt in command.options:
        if isinstance(opt, SPECIAL_OPTIONS):
            continue
        if (command.dest, opt.dest) not in opts_got:
            res.extend([Prompt(al) for al in opt.aliases] if isinstance(opt, Option) else [Prompt(opt.name)])
    return res


def prompt(command: Alconna, buffer: list, args_got: list[str], opts_got: list[tuple[str, ...]], trigger: str | Arg | Subcommand | None = None):
    """获取补全列表"""
    target = str(buffer[-1])
    if isinstance(buffer[-1], str) and buffer[-1] in command.config.builtin_option_name["completion"]:
        target = str(buffer[-2])
    if isinstance(trigger, Arg):
        template = i18n.require("completion.prompt_arg")
        if not (comp := trigger.field.get_completion()):
            return [Prompt(command.formatter.param(trigger), False)]
        if isinstance(comp, str):
            return [Prompt(template.format(name=trigger.name, prompt=comp), False)]
        o = list(filter(lambda x: target in x, comp)) or comp
        return [Prompt(template.format(name=trigger.name, prompt=i), False, target) for i in o]
    elif isinstance(trigger, Subcommand):
        return [Prompt(i, True) for i in trigger._lookup_map if target in i]
    if isinstance(trigger, str):
        target = trigger
    if _res := [x for x in command._lookup_map if target in x]:
        out = [i for i in _res if (command.dest, i) not in opts_got]
        return [Prompt(i, True, target) for i in (out or _res)]
    return _prompt_none(command, args_got, opts_got)
