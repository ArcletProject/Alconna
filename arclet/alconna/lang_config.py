import json
from pathlib import Path
from typing import Union, Dict


class _LangConfig:
    __slots__ = "__config"

    def __init__(self):
        default = Path(__file__).parent / 'default.lang'
        self.__config: Dict[str, str] = json.load(default.open('r', encoding='utf-8'))

    def load_file(self, path: Union[str, Path]):
        if isinstance(path, str):
            path = Path(path)
        self.__config.update(json.load(path.open('r', encoding='utf-8')))

    def require_lang(self, name: str) -> str:
        return self.__config.get(name, name)

    def change_lang(self, name: str, lang_content: str):
        if not self.__config.get(name):
            raise ValueError(self.__config['lang.name_error'].format(target=name))
        self.__config[name] = lang_content

    def __getattr__(self, item: str) -> str:
        item = item.replace('_', '.', 1)
        if not self.__config.get(item):
            raise AttributeError(self.__config['lang.name_error'].format(target=item))
        return self.__config[item]


lang_config = _LangConfig()
load_config_file = lang_config.load_file

__all__ = ['lang_config', 'load_config_file']