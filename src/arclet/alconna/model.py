class Sentence:
    __slots__ = ("name", "separators")

    def __init__(self, name, separators=None):
        self.name = name
        self.separators = separators or (" ",)


class OptionResult:
    __slots__ = ("value", "args")

    def __init__(self, value=Ellipsis, args=None):
        self.value = value
        self.args = args or {}


class SubcommandResult:
    __slots__ = ("value", "args", "options")

    def __init__(self, value=Ellipsis, args=None, options=None):
        self.value = value
        self.args = args or {}
        self.options = options or {}


class HeadResult:
    __slots__ = ("origin", "result", "matched", "groups")

    def __init__(self, origin=None, result=None, matched=False, groups=None):
        self.origin = origin
        self.result = result
        self.matched = matched
        self.groups = groups or {}
