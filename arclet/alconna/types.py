import inspect
from typing import TypeVar, Union, Type, Dict

AnyIP = r"(\d+)\.(\d+)\.(\d+)\.(\d+)"
AnyDigit = r"(\d+)"
AnyStr = r"(.+)"
AnyUrl = r"(http[s]?://.+)"
Bool = r"(True|False)"

NonTextElement = TypeVar("NonTextElement")
MessageChain = TypeVar("MessageChain")
TArgument = Union[str, Type[NonTextElement]]


class Args:
    argument: Dict[str, TArgument]
    defaults: Dict[str, Union[str, NonTextElement]]

    def __init__(self, **kwargs):
        self.argument = {k: v for k, v in kwargs.items() if k not in ('name', 'type')}
        self.defaults = {}

    def default(self, **kwargs):
        self.defaults = {k: v for k, v in kwargs.items() if k not in ('name', 'type')}
        return self

    def check(self, keyword: str):
        if keyword in self.defaults:
            if self.defaults[keyword] is None:
                return inspect.Signature.empty
            return self.defaults[keyword]

    def params(self, sep: str = " "):
        argument_string = ""
        i = 0
        length = len(self.argument)
        for k, v in self.argument.items():
            arg = f"<{k}"
            if not isinstance(v, str):
                arg += f": Type_{v.__name__}"
            if k in self.defaults:
                default = self.defaults[k]
                if default is None:
                    arg += " default: Empty"
                else:
                    arg += f" default: {default}"
            argument_string += arg + ">"
            i += 1
            if i != length:
                argument_string += sep
        return argument_string

    def __iter__(self):
        for k, v in self.argument.items():
            yield k, v

    def __len__(self):
        return len(self.argument)

    def __repr__(self):
        if not self.argument:
            return "Empty"
        repr_string = "Args({0})"
        repr_args = ", ".join(
            [
                f"{name}: {argtype}" + (f" = {name}" if name in self.defaults else "")
                for name, argtype in self.argument.items()
            ]
        )
        return repr_string.format(repr_args)
