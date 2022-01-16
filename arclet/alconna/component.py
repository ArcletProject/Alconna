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
        alias = f"{self.alias}, " if self.alias != self.name else ""
        setattr(
            self, "help_doc",
            f"# {help_string}\n  {alias}{self.name}{self.separator}{self.args.params(self.separator)}\n")
        return self


class Subcommand(TemplateCommand):
    """子命令, 次于主命令, 可解析 SubOption"""
    options: List[Option]
    sub_params: Dict[str, Union[Args, Option]]

    def __init__(self, name: str, *option: Option, args: Optional[Args] = None,
                 actions: Optional[Callable] = None, **kwargs):
        super().__init__(name, args, actions, **kwargs)
        self.options = list(option)
        self.sub_params = {"sub_args": self.args}

    def help(self, help_string: str):
        """预处理 help 文档"""
        option_string = "".join(list(map(lambda x: getattr(x, "help_doc", ""), self.options)))
        option_help = "## 该子命令内可用的选项有:\n " if option_string else ""
        setattr(self, "help_doc", f"# {help_string}\n"
                                  f"  {self.name}{self.separator}{self.args.params(self.separator)}\n"
                                  f"{option_help}{option_string}")
        return self


class Arpamar:
    """
    亚帕玛尔(Arpamar), Alconna的珍藏宝书

    Example:
        1.`Arpamar.main_args`: 当 Alconna 写入了 main_argument 时,该参数返回对应的解析出来的值

        2.`Arpamar.header`: 当 Alconna 的 command 内写有正则表达式时,该参数返回对应的匹配值

        3.`Arpamar.has`: 判断 Arpamar 内是否有对应的属性

        4.`Arpamar.get`: 返回 Arpamar 中指定的属性

        5.`Arpamar.matched`: 返回命令是否匹配成功

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
    def all_matched_args(self):
        """返回 Alconna 中所有 Args 解析到的值"""
        return {**self._main_args, **self._other_args}

    @property
    def option_args(self):
        """返回 Alconna 中所有 Option 里的 Args 解析到的值"""
        return self._other_args

    def encapsulate_result(self, hdr: Optional[str], margs: Dict[str, Any], opts: Dict[str, Any]) -> None:
        """处理 Arpamar 中的数据"""
        self._header = hdr
        self._main_args = margs['data']
        for k, v in opts.items():
            self._options.setdefault(k, v)
            if isinstance(v, dict):
                for kk, vv in v.items():
                    if not isinstance(vv, dict):
                        self._other_args[kk] = vv
                    else:
                        self._other_args.update(vv)

    def get(self, name: Union[str, Type[NonTextElement]]) -> Union[Dict, str, NonTextElement]:
        """根据选项或者子命令的名字返回对应的数据"""
        if isinstance(name, str):
            if name in self._options:
                return self._options[name]
            if name in self._other_args:
                return self._other_args[name]
        for _, v in self.all_matched_args:
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
