from __future__ import annotations

from dataclasses import InitVar, dataclass, field
from typing import Any, Callable, ClassVar, Generic, Iterable
from typing_extensions import Self

from tarina import lang, split, split_once

from ..args import Arg
from ..base import Option, Subcommand
from ..config import Namespace, config
from ..exceptions import NullMessage
from ..typing import TDC


@dataclass(repr=True)
class Argv(Generic[TDC]):
    """命令行参数"""
    namespace: InitVar[Namespace] = field(default=config.default_namespace)
    fuzzy_match: bool = field(default=False)
    """当前命令是否模糊匹配"""
    preprocessors: dict[type, Callable[..., Any]] = field(default_factory=dict)
    """命令元素的预处理器"""
    to_text: Callable[[Any], str | None] = field(default=lambda x: x if isinstance(x, str) else None)
    """将命令元素转换为文本, 或者返回None以跳过该元素"""
    separators: tuple[str, ...] = field(default=(' ',))
    """命令分隔符"""
    filter_out: list[type] = field(default_factory=list)
    """需要过滤掉的命令元素"""
    checker: Callable[[Any], bool] | None = field(default=None)
    """检查传入命令"""
    converter: Callable[[str | list], TDC] = field(default=lambda x: x)
    """将字符串或列表转为目标命令类型"""
    filter_crlf: bool = field(default=True)
    """是否过滤掉换行符"""
    message_cache: bool = field(default=True)
    """是否缓存消息"""
    param_ids: set[str] = field(default_factory=set)
    """节点名集合"""

    context: Arg | Subcommand | Option | None = field(init=False)
    """当前节点"""
    current_index: int = field(init=False)
    """当前数据的索引"""
    ndata: int = field(init=False)
    """原始数据的长度"""
    bak_data: list[str | Any] = field(init=False)
    """备份的原始数据"""
    raw_data: list[str | Any] = field(init=False)
    """原始数据"""
    token: int = field(init=False)
    """命令的token"""
    origin: TDC = field(init=False)
    """原始命令"""
    _sep: tuple[str, ...] | None = field(init=False)

    _cache: ClassVar[dict[type, dict[str, Any]]] = {}

    def __post_init__(self, namespace: Namespace):
        self.reset()
        self.special: dict[str, str] = {}
        self.special.update(
            [(i, "help") for i in namespace.builtin_option_name['help']] +
            [(i, "completion") for i in namespace.builtin_option_name['completion']] +
            [(i, "shortcut") for i in namespace.builtin_option_name['shortcut']]
        )
        self.completion_names = namespace.builtin_option_name['completion']
        if __cache := self.__class__._cache.get(self.__class__, {}):
            self.preprocessors.update(__cache.get("preprocessors") or {})
            self.filter_out.extend(__cache.get("filter_out") or [])
            self.to_text = __cache.get("to_text") or self.to_text
            self.checker = __cache.get("checker") or self.checker
            self.converter = __cache.get("converter") or self.converter

    def reset(self):
        """重置命令行参数"""
        self.current_index = 0
        self.ndata = 0
        self.bak_data = []
        self.raw_data = []
        self.token = 0
        self.origin = "None"
        self._sep = None
        self.context = None

    @staticmethod
    def generate_token(data: list) -> int:
        """命令的`token`的生成函数"""
        return hash(repr(data))

    @property
    def done(self) -> bool:
        """命令是否解析完毕"""
        return self.current_index == self.ndata

    def build(self, data: TDC) -> Self:
        """命令分析功能, 传入字符串或消息链

        Args:
            data (TDC): 命令

        Returns:
            Self: 自身
        """
        self.reset()
        if self.checker and not self.checker(data):
            if not self.converter:
                raise TypeError(data)
            try:
                data = self.converter(data)
            except Exception as e:
                raise TypeError(data) from e
        self.origin = data
        if data.__class__ is str:
            data = [data]  # type: ignore
        i = 0
        raw_data = self.raw_data
        for unit in data:
            if (utype := unit.__class__) in self.filter_out:
                continue
            if (proc := self.preprocessors.get(utype)) and (res := proc(unit)):
                unit = res
            if (text := self.to_text(unit)) is None:
                raw_data.append(unit)
            elif not (res := text.strip()):
                continue
            else:
                raw_data.append(res)
            i += 1
        if i < 1:
            raise NullMessage(lang.require("argv", "null_message").format(target=data))
        self.ndata = i
        self.bak_data = raw_data.copy()
        if self.message_cache:
            self.token = self.generate_token(raw_data)
        return self

    def addon(self, data: Iterable[str | Any]) -> Self:
        """添加命令元素

        Args:
            data (Iterable[str | Any]): 命令元素

        Returns:
            Self: 自身
        """
        for i, d in enumerate(data):
            if not d:
                continue
            if res := self.to_text(d):
                d = res
            if isinstance(d, str) and i > 0 and isinstance(self.raw_data[-1], str):
                self.raw_data[-1] += f"{self.separators[0]}{d}"
            else:
                self.raw_data.append(d)
                self.ndata += 1
        self.bak_data = self.raw_data.copy()
        if self.message_cache:
            self.token = self.generate_token(self.raw_data)
        return self

    def next(self, separate: tuple[str, ...] | None = None, move: bool = True) -> tuple[str | Any, bool]:
        """获取解析需要的下个数据

        Args:
            separate (tuple[str, ...] | None, optional): 分隔符.
            move (bool, optional): 是否移动指针.

        Returns:
            tuple[str | Any, bool]: 下个数据, 是否是字符串.
        """
        if self._sep:
            self._sep = None
        if self.current_index == self.ndata:
            return "", True
        separate = separate or self.separators
        _current_data = self.raw_data[self.current_index]
        if _current_data.__class__ is str:
            _text, _rest_text = split_once(_current_data, separate, self.filter_crlf)  # type: ignore
            if move:
                if _rest_text:
                    self._sep = separate
                    self.raw_data[self.current_index] = _rest_text
                else:
                    self.current_index += 1
            return _text, True
        if move:
            self.current_index += 1
        return _current_data, False

    def rollback(self, data: str | Any, replace: bool = False):
        """把获取的数据放回 (实际只是`指针`移动)

        Args:
            data (str | Any): 数据.
            replace (bool, optional): 是否替换.
        """
        if data == "" or data is None:
            return
        if self._sep:
            _current_data = self.raw_data[self.current_index]
            self.raw_data[self.current_index] = f"{data}{self._sep[0]}{_current_data}"
            return
        if self.current_index >= 1:
            self.current_index -= 1
        if replace:
            self.raw_data[self.current_index] = data

    def free(self, separate: tuple[str, ...] | None = None):
        """将当前位置的数据释放"""
        separate = separate or self.separators
        if self.current_index == self.ndata:
            return
        _current_data = self.raw_data[self.current_index]
        if _current_data.__class__ is str:
            _text, _rest_text = split_once(_current_data, separate, self.filter_crlf)
            if _rest_text:
                self.bak_data.insert(self.current_index + 1, _rest_text)
                self.raw_data.insert(self.current_index + 1, _rest_text)
                self.ndata += 1
            self.bak_data[self.current_index] = self.bak_data[self.current_index][:-len(_current_data)]
            self.raw_data[self.current_index] = ""
        else:
            self.bak_data.pop(self.current_index)
            self.raw_data.pop(self.current_index)

    def release(self, separate: tuple[str, ...] | None = None, recover: bool = False) -> list[str | Any]:
        """获取剩余的数据

        Args:
            separate (tuple[str, ...] | None, optional): 分隔符.
            recover (bool, optional): 是否从头开始获取.

        Returns:
            list[str | Any]: 剩余的数据.
        """
        _result = []
        data = self.bak_data if recover else self.raw_data[self.current_index:]
        for _data in data:
            if _data.__class__ is str:
                _result.extend(split(_data, separate or (' ',), self.filter_crlf))
            else:
                _result.append(_data)
        return _result

    def data_set(self):
        return self.raw_data.copy(), self.current_index

    def data_reset(self, data: list[str | Any], index: int):
        self.raw_data = data
        self.current_index = index
