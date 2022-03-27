from typing import TYPE_CHECKING, cast, Optional
from inspect import isclass

from .stub import BaseStub, ArgsStub, SubcommandStub, OptionStub, Subcommand, Option

if TYPE_CHECKING:
    from ..main import Alconna
    from . import Arpamar


class AlconnaDuplication:
    __target: 'Arpamar'

    @property
    def origin(self) -> "Arpamar":
        return self.__target

    @property
    def header(self):
        return self.__target.header

    def set_target(self, target: 'Arpamar'):
        self.__target = target
        if self.__stubs__.get("main_args"):
            getattr(self, self.__stubs__["main_args"]).set_result(target.main_args)  # type: ignore
        for key in self.__stubs__["options"]:
            if key in target.options:
                getattr(self, key).set_result(target.options[key])
        for key in self.__stubs__["subcommands"]:
            if key in target.options:
                getattr(self, key).set_result(target.subcommands[key])
        return self

    def __init__(self, alconna: 'Alconna'):
        self.__stubs__ = {"options": [], "subcommands": []}
        for key, value in self.__annotations__.items():
            if isclass(value) and issubclass(value, BaseStub):
                if value == ArgsStub:
                    setattr(self, key, ArgsStub(alconna.args))
                    self.__stubs__["main_args"] = key  # type: ignore
                elif value == SubcommandStub:
                    for subcommand in filter(lambda x: isinstance(x, Subcommand), alconna.options):
                        if subcommand.name.lstrip('-') == key:
                            setattr(self, key, SubcommandStub(subcommand))  # type: ignore
                            self.__stubs__["subcommands"].append(key)
                elif value == OptionStub:
                    for option in filter(lambda x: isinstance(x, Option), alconna.options):
                        if option.name.lstrip('-') == key:
                            setattr(self, key, OptionStub(option))  # type: ignore
                            self.__stubs__["options"].append(key)
                else:
                    raise TypeError(f'{value} is not a valid stub')

    def __repr__(self):
        return f'<{self.__class__.__name__} with {self.__stubs__}>'

    def option(self, name: str) -> Optional[OptionStub]:
        return cast(OptionStub, getattr(self, name, None))

    def subcommand(self, name: str) -> Optional[SubcommandStub]:
        return cast(SubcommandStub, getattr(self, name, None))


def generate_duplication(command: "Alconna") -> AlconnaDuplication:
    options = filter(lambda x: isinstance(x, Option), command.options)
    subcommands = filter(lambda x: isinstance(x, Subcommand), command.options)
    return cast(AlconnaDuplication, type(
        command.name.replace("ALCONNA::", "") + 'Interface',
        (AlconnaDuplication,),
        {
            "__annotations__": {
                **{"args": ArgsStub},
                **{opt.name.lstrip('-'): OptionStub for opt in options if opt.name.lstrip('-') != "help"},
                **{sub.name.lstrip('-'): SubcommandStub for sub in subcommands},
            }
        }
    )(command))
