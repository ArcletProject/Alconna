from dataclasses import dataclass
_repr_ = lambda self: " ".join(f"{k}={getattr(self, k, ...)!r}" for k in self.__slots__)

@dataclass(eq=True)
class Sentence:
    __slots__ = ("name", "separators")
    __repr__ = _repr_
    def __init__(self, name, separators=None):
        self.name = name
        self.separators = separators or (" ",)


@dataclass(eq=True)
class OptionResult:
    __slots__ = ("value", "args")
    __repr__ = _repr_
    def __init__(self, value=Ellipsis, args=None):
        self.value = value
        self.args = args or {}


@dataclass(eq=True)
class SubcommandResult:
    __slots__ = ("value", "args", "options")
    __repr__ = _repr_
    def __init__(self, value=Ellipsis, args=None, options=None):
        self.value = value
        self.args = args or {}
        self.options = options or {}


@dataclass(eq=True)
class HeadResult:
    __slots__ = ("origin", "result", "matched", "groups")
    __repr__ = _repr_
    def __init__(self, origin=None, result=None, matched=False, groups=None):
        self.origin = origin
        self.result = result
        self.matched = matched
        self.groups = groups or {}
