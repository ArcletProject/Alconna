from __future__ import annotations

from inspect import isclass
from typing import cast

from tarina import Empty

from arclet.alconna.arparma import Arparma
from arclet.alconna.core import Alconna
from arclet.alconna.base import Option, Subcommand

from .stub import ArgsStub, BaseStub, OptionStub, SubcommandStub


class Duplication:
    """`副本`, 用以更方便的检查、调用解析结果的类。"""

    header: dict[str, str]

    def __init__(self, target: Arparma):
        source = target.source
        self.header = target.header.copy()
        for key, value in self.__annotations__.items():
            if isclass(value) and issubclass(value, BaseStub):
                if value is ArgsStub:
                    setattr(self, key, ArgsStub(source.args).set_result(target.main_args))
                elif value is SubcommandStub:
                    for subcommand in source.options:
                        if isinstance(subcommand, Subcommand) and subcommand.dest == key:
                            setattr(self, key, SubcommandStub(subcommand).set_result(target.subcommands.get(key, None)))
                elif value is OptionStub:
                    for option in source.options:
                        if isinstance(option, Option) and option.dest == key:
                            setattr(self, key, OptionStub(option).set_result(target.options.get(key, None)))
            elif key != "header":
                setattr(self, key, target.all_matched_args.get(key, Empty))

    def __repr__(self):
        return f"{self.__class__.__name__}({self.__annotations__})"

    def option(self, name: str) -> OptionStub | None:
        """获取指定名称的选项存根。"""
        return cast(OptionStub, getattr(self, name, None))

    def subcommand(self, name: str) -> SubcommandStub | None:
        """获取指定名称的子命令存根。"""
        return cast(SubcommandStub, getattr(self, name, None))


def generate_duplication(alc: Alconna) -> type[Duplication]:
    """依据给定的命令生成一个解析结果的检查类。"""

    options = filter(lambda x: isinstance(x, Option), alc.options)
    subcommands = filter(lambda x: isinstance(x, Subcommand), alc.options)
    return cast(
        "type[Duplication]",
        type(
            f"{alc.name.strip('/.-:')}Interface",
            (Duplication,),
            {
                "__annotations__": {
                    "args": ArgsStub,
                    **{opt.dest: OptionStub for opt in options},
                    **{sub.dest: SubcommandStub for sub in subcommands},
                }
            },
        ),
    )
