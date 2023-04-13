from __future__ import annotations
from typing import Final, final
from pathlib import Path
import json


@final
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

    def __getattr__(self, item: str):
        class _getter:
            def __init__(self, prefix: str):
                self.prefix = prefix

        def __getattr__(_self, _item):
            key = f"{_self.prefix}.{_item}"
            if not self.__config.get(key):
                raise AttributeError(self.__config["lang.name_error"].format(target=key))
            return self.__config[key]

        return type(f"{item}_getter", (_getter,), {"__getattr__": __getattr__})(item)


lang: _LangConfig = _LangConfig()
load_lang_file = lang.reload

__all__ = ["lang", "load_lang_file"]
