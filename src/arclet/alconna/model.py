from dataclasses import dataclass

_repr_ = lambda self: "(" + " ".join([f"{k}={getattr(self, k, ...)!r}" for k in self.__slots__]) + ")"


@dataclass(init=False, eq=True)
class Sentence:
    __slots__ = ("name",)
    __str__ = lambda self: self.name  # type: ignore
    __repr__ = lambda self: self.name  # type: ignore

    def __init__(self, name):
        self.name = name


@dataclass(init=False, eq=True)
class OptionResult:
    __slots__ = ("value", "args")
    __repr__ = _repr_

    def __init__(self, value=Ellipsis, args=None):
        self.value = value
        self.args = args or {}


@dataclass(init=False, eq=True)
class SubcommandResult:
    __slots__ = ("value", "args", "options", "subcommands")
    __repr__ = _repr_

    def __init__(self, value=Ellipsis, args=None, options=None, subcommands=None):
        self.value = value
        self.args = args or {}
        self.options = options or {}
        self.subcommands = subcommands or {}


@dataclass(init=False, eq=True)
class HeadResult:
    __slots__ = ("origin", "result", "matched", "groups")
    __repr__ = _repr_

    def __init__(self, origin=None, result=None, matched=False, groups=None, fixes=None):
        self.origin = origin
        self.result = result
        self.matched = matched
        self.groups = groups or {}
        if fixes:
            self.groups.update({k: v.validate(self.groups[k])._value for k, v in fixes.items() if k in self.groups})  # noqa
