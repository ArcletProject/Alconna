import re
from typing import Union, Type, Optional, Dict, List, Any
from pydantic import BaseModel

from . import split_once
from .exceptions import NullName, InvalidOptionName
from .types import NonTextElement


class Default:
    args: Union[str, Type[NonTextElement]]
    default: Union[str, Type[NonTextElement]]

    def __init__(
            self,
            args: Union[str, Type[NonTextElement]],
            default: Optional[Union[str, NonTextElement]] = None
    ):
        self.args = args
        self.default = default


Argument_T = Union[str, Type[NonTextElement], Default]


class CommandInterface(BaseModel):
    name: str
    separator: str = " "

    def separate(self, sep: str):
        self.separator = sep
        return self

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"


class OptionInterface(CommandInterface):
    type: str
    args: Dict[str, Argument_T]


class Option(OptionInterface):
    type: str = "OPT"

    def __init__(self, name: str, **kwargs):
        if name == "":
            raise NullName
        if re.match(r"^[`~?/.,<>;\':\"|!@#$%^&*()_+=\[\]}{]+.*$", name):
            raise InvalidOptionName
        super().__init__(
            name=name,
            args={k: v for k, v in kwargs.items() if k not in ('name', 'type')}
        )


class Subcommand(OptionInterface):
    type: str = "SBC"
    Options: List[Option]

    def __init__(self, name: str, *options: Option, **kwargs):
        if name == "":
            raise NullName
        if re.match(r"^[`~?/.,<>;\':\"|!@#$%^&*()_+=\[\]}{]+.*$", name):
            raise InvalidOptionName
        super().__init__(
            name=name,
            Options=list(options),
            args={k: v for k, v in kwargs.items() if k not in ('name', 'type')}
        )


class Arpamar(BaseModel):
    """
    亚帕玛尔(Arpamar), Alconna的珍藏宝书

    Example:
        1.`Arpamar.main_argument`: 当 Alconna 写入了 main_argument 时,该参数返回对应的解析出来的值

        2.`Arpamar.header`: 当 Alconna 的 command 内写有正则表达式时,该参数返回对应的匹配值

        3.`Arpamar.has`: 判断 Arpamar 内是否有对应的属性

        4.`Arpamar.get`: 返回 Arpamar 中指定的属性

        5.`Arpamar.matched`: 返回命令是否匹配成功

    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_index: int = 0  # 记录解析时当前字符串的index
        self.is_str: bool = False  # 是否解析的是string
        self.results: Dict[str, Any] = {'options': {}}
        self.elements: Dict[int, NonTextElement] = {}
        self.raw_texts: List[List[Union[int, str]]] = []
        self.need_marg: bool = False
        self.matched: bool = False
        self.head_matched: bool = False
        self._args: Dict[str, Any] = {}

    @property
    def main_argument(self):
        if 'main_argument' in self.results and self.need_marg:
            return self.results['main_argument']

    @property
    def header(self):
        if self.results['header']:
            return self.results['header']
        else:
            return self.head_matched

    @property
    def option_args(self):
        return self._args

    def encapsulate_result(self) -> None:
        for k, v in self.results['options'].items():
            self.__setattr__(k, v)
            if isinstance(v, dict):
                for kk, vv in v.items():
                    if not isinstance(vv, dict):
                        self._args[kk] = vv
                    else:
                        self._args.update(vv)

    def get(self, name: str) -> dict:
        return self.__getattribute__(name)

    def has(self, name: str) -> bool:
        return name in self.__dict__

    def split_by(self, separate: str):
        _text: str = ""  # 重置
        _rest_text: str = ""

        if self.raw_texts[self.current_index][0]:  # 如果命令头匹配后还有字符串没匹配到
            _text, _rest_text = split_once(self.raw_texts[self.current_index][0], separate)

        elif not self.is_str and len(self.raw_texts) > 1:  # 如果命令头匹配后字符串为空则有两种可能，这里选择不止一段字符串
            self.current_index += 1
            _text, _rest_text = split_once(self.raw_texts[self.current_index][0], separate)

        return _text, _rest_text

    class Config:
        extra = 'allow'


Options_T = List[OptionInterface]
