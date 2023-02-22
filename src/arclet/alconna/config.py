from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import ContextManager, Final, TypedDict
from .typing import THeader


class OptionNames(TypedDict):
    help: set[str]
    shortcut: set[str]
    completion: set[str]


@dataclass(init=True, repr=True)
class Namespace:
    name: str
    headers: THeader = field(default_factory=list)
    separators: tuple[str, ...] = field(default_factory=lambda: (" ",))
    formatter_type: type["TextFormatter"] | None = field(default=None)  # type: ignore
    fuzzy_match: bool = field(default=False)
    raise_exception: bool = field(default=False)
    enable_message_cache: bool = field(default=True)
    builtin_option_name: OptionNames = field(
        default_factory=lambda: {
            "help": {"--help", "-h"},
            "shortcut": {"--shortcut", "-sct"},
            "completion": {"--comp", "-cp"},
        }
    )

    def __eq__(self, other):
        return isinstance(other, Namespace) and other.name == self.name

    def __hash__(self):
        return hash(self.name)


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


class _LangConfig:
    path: Final[Path] = Path(__file__).parent / "default.lang"
    __slots__ = "__config", "__file"

    def __init__(self):
        with self.path.open("r", encoding="utf-8") as f:
            self.__file = json.load(f)
        self.__config: dict[str, str] = self.__file[self.__file["$default"]]

    @property
    def types(self):
        return [key for key in self.__file if key != "$default"]

    def change_type(self, name: str):
        if name != "$default" and name in self.__file:
            self.__config = self.__file[name]
            self.__file["$default"] = name
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(
                    self.__file, f, ensure_ascii=False, indent=2
                )
            return
        raise ValueError(self.__config["lang.type_error"].format(target=name))

    def reload(self, path: str | Path, lang_type: str | None = None):
        if isinstance(path, str):
            path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            content = json.load(f)
        if not lang_type:
            self.__config.update(content)
        elif lang_type in self.__file:
            self.__file[lang_type].update(content)
            self.__config = self.__file[lang_type]
        else:
            self.__file[lang_type] = content
            self.__config = self.__file[lang_type]

    def require(self, name: str) -> str:
        return self.__config.get(name, name)

    def set(self, name: str, lang_content: str):
        if not self.__config.get(name):
            raise ValueError(self.__config["lang.name_error"].format(target=name))
        self.__config[name] = lang_content

    def __getattr__(self, item: str) -> str:
        item = item.replace("_", ".", 1)
        if not self.__config.get(item):
            raise AttributeError(self.__config["lang.name_error"].format(target=item))
        return self.__config[item]


class _AlconnaConfig:
    lang: _LangConfig = _LangConfig()
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
load_lang_file = config.lang.reload

__all__ = ["config", "load_lang_file", "Namespace", "namespace"]
