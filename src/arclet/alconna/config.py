from __future__ import annotations

from dataclasses import dataclass, field
from typing import ContextManager, TypedDict, Callable, Any, TYPE_CHECKING
from tarina import lang
from pathlib import Path

from .typing import TPrefixes, DataCollection

if TYPE_CHECKING:
    from .formatter import TextFormatter


class OptionNames(TypedDict):
    help: set[str]
    shortcut: set[str]
    completion: set[str]


@dataclass(init=True, repr=True)
class Namespace:
    name: str
    prefixes: TPrefixes = field(default_factory=list)
    separators: tuple[str, ...] = field(default_factory=lambda: (" ",))
    formatter_type: type[TextFormatter] | None = field(default=None)  # type: ignore
    fuzzy_match: bool = field(default=False)
    raise_exception: bool = field(default=False)
    enable_message_cache: bool = field(default=True)
    builtin_option_name: OptionNames = field(
        default_factory=lambda: {
            "help": {"--help", "-h"},
            "shortcut": {"--shortcut", "-sct"},
            "completion": {"--comp", "-cp", "?", "？"},
        }
    )
    to_text: Callable[[Any], str | None] = field(default=lambda x: x if isinstance(x, str) else None)
    converter: Callable[[Any], DataCollection[Any]] | None = field(default=lambda x: x)

    def __eq__(self, other):
        return isinstance(other, Namespace) and other.name == self.name

    def __hash__(self):
        return hash(self.name)

    @property
    def headers(self):
        return self.prefixes

    @headers.setter
    def headers(self, value):
        self.prefixes = value


class namespace(ContextManager[Namespace]):
    """
    新建一个命名空间配置并暂时作为默认命名空间

    with namespace("xxx") as np:
        np.headers = [aaa]
        alc = Alconna(...)
        alc.headers == [aaa]
    """

    def __init__(self, name: Namespace | str):
        self.np = Namespace(name) if isinstance(name, str) else name
        self.name = self.np.name if isinstance(name, Namespace) else name
        self.old = config.default_namespace
        config.default_namespace = self.np

    def __enter__(self) -> Namespace:
        return self.np

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type or exc_val or exc_tb:
            return False
        config.default_namespace = self.old
        config.namespaces[self.name] = self.np
        del self.old
        del self.np


class _AlconnaConfig:
    command_max_count: int = 200
    message_max_cache: int = 100
    fuzzy_threshold: float = 0.6
    _default_namespace = "Alconna"
    namespaces: dict[str, Namespace] = {_default_namespace: Namespace(_default_namespace)}

    @property
    def default_namespace(self):
        return self.namespaces[self._default_namespace]

    @default_namespace.setter
    def default_namespace(self, np: str | Namespace):
        if isinstance(np, str):
            if np not in self.namespaces:
                old = self.namespaces.pop(self._default_namespace, Namespace(np))
                old.name = np
                self.namespaces[np] = old
            self._default_namespace = np
        else:
            self._default_namespace = np.name
            self.namespaces[np.name] = np


config = _AlconnaConfig()
lang.load(Path(__file__).parent / "i18n")

__all__ = ["config", "Namespace", "namespace", "lang"]
