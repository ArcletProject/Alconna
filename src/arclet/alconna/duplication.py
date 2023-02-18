from __future__ import annotations

from typing import cast
from inspect import isclass

from .arparma import Arparma
from .stub import BaseStub, ArgsStub, SubcommandStub, OptionStub



class Duplication:
    """用以更方便的检查、调用解析结果的类。"""
    header: dict[str, str]

    def __init__(self, target: Arparma):
        from .base import Subcommand, Option
        self.header = target.header.copy()
        for key, value in self.__annotations__.items():
            if isclass(value) and issubclass(value, BaseStub):
                if value == ArgsStub:
                    setattr(self, key, ArgsStub(target.source.args).set_result(target.main_args))
                elif value == SubcommandStub:
                    for subcommand in filter(lambda x: isinstance(x, Subcommand), target.source.options):
                        if subcommand.dest == key and key in target.subcommands:
                            setattr(self, key, SubcommandStub(subcommand).set_result(target.subcommands[key]))
                elif value == OptionStub:
                    for option in filter(lambda x: isinstance(x, Option), target.source.options):
                        if option.dest == key and key in target.options:
                            setattr(self, key, OptionStub(option).set_result(target.options[key]))
            elif key != 'header' and key in target.all_matched_args:
                setattr(self, key, target.all_matched_args[key])

    def __repr__(self):
        return f'{self.__class__.__name__}({self.__annotations__})'

    def option(self, name: str) -> OptionStub | None:
        return cast(OptionStub, getattr(self, name, None))

    def subcommand(self, name: str) -> SubcommandStub | None:
        return cast(SubcommandStub, getattr(self, name, None))


def generate_duplication(arp: Arparma) -> Duplication:
    """依据给定的命令生成一个解析结果的检查类。"""
    from .base import Subcommand, Option
    options = filter(lambda x: isinstance(x, Option), arp.source.options)
    subcommands = filter(lambda x: isinstance(x, Subcommand), arp.source.options)
    return cast(Duplication, type(
        f"{arp.source.name.strip('/.-:')}Interface",
        (Duplication,), {
            "__annotations__": {
                "args": ArgsStub,
                **{opt.dest: OptionStub for opt in options},
                **{sub.dest: SubcommandStub for sub in subcommands},
            }
        }
    )(arp))
