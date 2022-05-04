import json
from pathlib import Path
from typing import Union, Dict, Final, Optional


class _LangConfig:
    path: Final[Path] = Path(__file__).parent / 'default.lang'
    __slots__ = "__config", '__file'

    def __init__(self):
        self.__file = json.load(self.path.open('r', encoding='utf-8'))
        self.__config: Dict[str, str] = self.__file[self.__file['default']]

    @property
    def types(self):
        return [key for key in self.__file if key != 'default']

    def change_type(self, name: str):
        if name != 'default' and name in self.__file:
            self.__config = self.__file[name]
            self.__file['default'] = name
            json.dump(self.__file, self.path.open('w', encoding='utf-8'), ensure_ascii=False, indent=2)
            return
        raise ValueError(self.__config['lang.type_error'].format(target=name))

    def reload(self, path: Union[str, Path], lang_type: Optional[str] = None):
        if isinstance(path, str):
            path = Path(path)
        content = json.load(path.open('r', encoding='utf-8'))
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
            raise ValueError(self.__config['lang.name_error'].format(target=name))
        self.__config[name] = lang_content

    def __getattr__(self, item: str) -> str:
        item = item.replace('_', '.', 1)
        if not self.__config.get(item):
            raise AttributeError(self.__config['lang.name_error'].format(target=item))
        return self.__config[item]


lang_config = _LangConfig()
load_lang_file = lang_config.reload

__all__ = ['lang_config', 'load_lang_file']
