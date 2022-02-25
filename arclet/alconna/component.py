"""Alconna 的组件相关"""

from typing import Union, Dict, List, Any, Optional, Callable, Type
from .types import NonTextElement
from .base import TemplateCommand, Args


class Option(TemplateCommand):
    """命令选项, 可以使用别名"""
    alias: str

    def __init__(self, name: str, args: Optional[Args] = None, alias: Optional[str] = None,
                 actions: Optional[Callable] = None, **kwargs):
        if "|" in name:
            name, alias = name.replace(' ', '').split('|')
        super().__init__(name, args, actions, **kwargs)
        self.alias = alias or name

    def help(self, help_string: str):
        """预处理 help 文档"""
        self.help_text = help_string
        alias = f"{self.alias}, " if self.alias != self.name else ""
        setattr(
            self, "help_doc",
            f"# {help_string}\n  {alias}{self.name}{self.separator}{self.args.params(self.separator)}\n")
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {**super().to_dict(), "alias": self.alias}

    def __getstate__(self):
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Option":
        name = data['name']
        alias = data['alias']
        args = Args.from_dict(data['args'])
        opt = cls(name, args, alias=alias).separate(data['separator']).help(data['help_text'])
        return opt

    def __setstate__(self, state):
        self.__init__(
            state['name'], Args.from_dict(state['args']), state['alias']
        ).separate(state['separator']).help(state['help_text'])


class Subcommand(TemplateCommand):
    """子命令, 次于主命令, 可解析 SubOption"""
    options: List[Option]
    sub_params: Dict[str, Union[Args, Option]]
    sub_part_len: range

    def __init__(self, name: str, *option: Option, args: Optional[Args] = None,
                 actions: Optional[Callable] = None, **kwargs):
        super().__init__(name, args, actions, **kwargs)
        self.options = list(option)
        self.sub_params = {}
        self.sub_part_len = range(self.nargs)

    def help(self, help_string: str):
        """预处理 help 文档"""
        self.help_text = help_string
        option_string = " ".join(list(map(lambda x: getattr(x, "help_doc", ""), self.options)))
        option_help = "## 该子命令内可用的选项有:\n " if option_string else ""
        setattr(self, "help_doc", f"# {help_string}\n"
                                  f"  {self.name}{self.separator}{self.args.params(self.separator)}\n"
                                  f"{option_help}{option_string}")
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {**super().to_dict(), "options": [option.to_dict() for option in self.options]}

    def __getstate__(self):
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subcommand":
        name = data['name']
        options = [Option.from_dict(option) for option in data['options']]
        args = Args.from_dict(data['args'])
        sub = cls(name, *options, args=args).separate(data['separator']).help(data['help_text'])
        return sub

    def __setstate__(self, state):
        self.__init__(
            state['name'],
            *[Option.from_dict(option) for option in state['options']],
            args=Args.from_dict(state['args'])
        ).separate(state['separator']).help(state['help_text'])


class Arpamar:
    """
    亚帕玛尔(Arpamar), Alconna的珍藏宝书

    Example:

    1. `Arpamar.main_args`: 当 Alconna 写入了 main_argument 时,该参数返回对应的解析出来的值

        2. `Arpamar.header`: 当 Alconna 的 command 内写有正则表达式时,该参数返回对应的匹配值

        3. `Arpamar.has`: 判断 Arpamar 内是否有对应的属性

        4. `Arpamar.get`: 返回 Arpamar 中指定的属性

        5. `Arpamar.matched`: 返回命令是否匹配成功

    """

    def __init__(self):
        self.matched: bool = False
        self.head_matched: bool = False
        self.error_data: List[Union[str, NonTextElement]] = []

        self._options: Dict[str, Any] = {}
        self._other_args: Dict[str, Any] = {}
        self._header: Optional[str] = None
        self._main_args: Dict[str, Any] = {}

    __slots__ = ("matched", "head_matched", "error_data", "_options", "_other_args", "_header", "_main_args")

    @property
    def main_args(self):
        """返回可能解析到的 main arguments"""
        return self._main_args

    @property
    def header(self):
        """返回可能解析到的命令头中的信息"""
        if self._header:
            return self._header
        return self.head_matched

    @property
    def options(self):
        """返回 Alconna 中所有 Option 里的 Args 解析到的值"""
        return self._options

    @property
    def all_matched_args(self):
        """返回 Alconna 中所有 Args 解析到的值"""
        return {**self._main_args, **self._other_args}

    @property
    def option_args(self):
        """返回 Alconna 中所有 Option 里的 Args 解析到的值"""
        return self._other_args

    def encapsulate_result(self, header: Optional[str], main_args: Dict[str, Any], options: Dict[str, Any]) -> None:
        """处理 Arpamar 中的数据"""
        self._header = header
        self._main_args = main_args
        self._options = options
        for k in options:
            v = options[k]
            if isinstance(v, dict):
                self._other_args = {**self._other_args, **v}
            elif isinstance(v, list):
                _rr = {}
                for i in v:
                    if not isinstance(i, dict):
                        break
                    for kk, vv in i.items():
                        if kk not in _rr:
                            _rr[kk] = [vv]
                        else:
                            _rr[kk].append(vv)

                self._other_args = {**self._other_args, **_rr}

    def get(self, name: Union[str, Type[NonTextElement]]) -> Union[Dict, str, NonTextElement]:
        """根据选项或者子命令的名字返回对应的数据"""
        if isinstance(name, str):
            if name in self._options:
                return self._options[name]
            if name in self._other_args:
                return self._other_args[name]
            if name in self._main_args:
                return self._main_args[name]
        else:
            for _, v in self.all_matched_args.items():
                if isinstance(v, name):
                    return v

    def has(self, name: str) -> bool:
        """判断 Arpamar 是否有对应的选项/子命令的解析结果"""
        return any([name in self._other_args, name in self._options])

    def __getitem__(self, item: Union[str, Type[NonTextElement]]):
        return self.get(item)

    def __getattr__(self, item):
        return self.get(item)

    def __repr__(self):
        attrs = ((s, getattr(self, s)) for s in self.__slots__)
        return " ".join([f"{a}={v}" for a, v in attrs if v is not None])
