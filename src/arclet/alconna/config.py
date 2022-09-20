import asyncio
import json
from pathlib import Path
from contextlib import contextmanager
from typing import Union, Dict, Final, Optional, Set, List, Tuple, ContextManager
from dataclasses import dataclass, field


@dataclass
class Namespace:
    name: str
    headers: Union[List[Union[str, object]], List[Tuple[object, str]]] = field(default_factory=list)
    separators: Set[str] = field(default_factory=lambda: set(" "))
    fuzzy_match: bool = field(default=False)
    raise_exception: bool = field(default=False)
    enable_message_cache: bool = field(default=True)

    def __eq__(self, other):
        return isinstance(other, Namespace) and other.name == self.name

    def __hash__(self):
        return hash(self.name)


class _LangConfig:
    path: Final[Path] = Path(__file__).parent / "default.lang"
    __slots__ = "__config", "__file"

    def __init__(self):
        self.__file = json.load(self.path.open("r", encoding="utf-8"))
        self.__config: Dict[str, str] = self.__file[self.__file["$default"]]

    @property
    def types(self):
        return [key for key in self.__file if key != "$default"]

    def change_type(self, name: str):
        if name != "$default" and name in self.__file:
            self.__config = self.__file[name]
            self.__file["$default"] = name
            json.dump(
                self.__file,
                self.path.open("w", encoding="utf-8"),
                ensure_ascii=False,
                indent=2,
            )
            return
        raise ValueError(self.__config["lang.type_error"].format(target=name))

    def reload(self, path: Union[str, Path], lang_type: Optional[str] = None):
        if isinstance(path, str):
            path = Path(path)
        content = json.load(path.open("r", encoding="utf-8"))
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
    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    command_max_count: int = 200
    message_max_cache: int = 100
    fuzzy_threshold: float = 0.6
    _default_namespace = "Alconna"
    namespaces: Dict[str, Namespace] = {_default_namespace: Namespace(_default_namespace)}

    @property
    def default_namespace(self):
        return self.namespaces[self._default_namespace]

    @default_namespace.setter
    def default_namespace(self, np: Union[str, Namespace]):
        if isinstance(np, str):
            if np not in self.namespaces:
                old = self.namespaces.pop(self._default_namespace)
                assert old
                old.name = np
                self.namespaces[np] = old
            self._default_namespace = np
        else:
            self._default_namespace = np.name
            self.namespaces[np.name] = np

    @classmethod
    def set_loop(cls, loop: asyncio.AbstractEventLoop) -> None:
        """设置事件循环"""
        cls.loop = loop


@contextmanager
def namespace(name: Union[Namespace, str]) -> ContextManager[Namespace]:
    """
    新建一个命名空间配置并暂时作为默认命名空间

    Example:
        with namespace("xxx") as np:
            np.headers = [aaa]
            alc = Alconna(...)
            alc.headers == [aaa]
    """
    np = Namespace(name) if isinstance(name, str) else name
    name = np.name if isinstance(name, Namespace) else name
    old = config.default_namespace
    config.default_namespace = np
    yield np
    config.default_namespace = old
    config.namespaces[name] = np


config = _AlconnaConfig()
load_lang_file = config.lang.reload

__all__ = ["config", "load_lang_file", "Namespace", "namespace"]
