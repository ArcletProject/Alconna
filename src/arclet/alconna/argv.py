from __future__ import annotations

from dataclasses import dataclass, field, InitVar
from typing import Any, Callable, Generic
from typing_extensions import Self
from tarina import split, split_once, lang

from .args import Arg
from .config import Namespace, config
from .base import Option, Subcommand
from .exceptions import NullMessage
from .typing import TDC

_cache: dict[type, dict[str, Any]] = {}


@dataclass(repr=True)
class Argv(Generic[TDC]):
    namespace: InitVar[Namespace] = field(default=config.default_namespace)
    fuzzy_match: bool = field(default=False)
    preprocessors: dict[str, Callable[..., Any]] = field(default_factory=dict)
    to_text: Callable[[Any], str | None] = field(default=lambda x: x if isinstance(x, str) else None)
    separators: tuple[str, ...] = field(default=(' ',))  # 分隔符
    filter_out: list[str] = field(default_factory=list)  # 元素黑名单
    checker: Callable[[Any], bool] | None = field(default=None)
    converter: Callable[[str | list], TDC] = field(default=lambda x: x)
    filter_crlf: bool = field(default=True)
    message_cache: bool = field(default=True)
    param_ids: set[str] = field(default_factory=set)

    context: Arg | Subcommand | Option | None = field(init=False)
    current_index: int = field(init=False)  # 当前数据的index
    ndata: int = field(init=False)  # 原始数据的长度
    bak_data: list[str | Any] = field(init=False)
    raw_data: list[str | Any] = field(init=False)
    token: int = field(init=False)  # 临时token
    origin: TDC = field(init=False)
    _sep: tuple[str, ...] | None = field(init=False)

    @classmethod
    def config(
        cls,
        preprocessors: dict[str, Callable[..., Any]] | None = None,
        to_text: Callable[[Any], str | None] | None = None,
        filter_out: list[str] | None = None,
        checker: Callable[[Any], bool] | None = None,
        converter: Callable[[str | list], TDC] | None = None
    ):
        _cache.setdefault(cls, {}).update(locals())

    def __post_init__(self, namespace: Namespace):
        self.reset()
        self.special: dict[str, str] = {}
        self.special.update(
            [(i, "help") for i in namespace.builtin_option_name['help']] +
            [(i, "completion") for i in namespace.builtin_option_name['completion']] +
            [(i, "shortcut") for i in namespace.builtin_option_name['shortcut']]
        )
        self.completion_names = namespace.builtin_option_name['completion']
        if __cache := _cache.get(self.__class__, {}):
            self.preprocessors.update(__cache["preprocessors"] or {})
            self.filter_out.extend(__cache["filter_out"] or [])
            self.to_text = __cache["to_text"] or self.to_text
            self.checker = __cache["checker"] or self.checker
            self.converter = __cache["converter"] or self.converter

    def reset(self):
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
        return hash(repr(data))

    @property
    def done(self) -> bool:
        return self.current_index == self.ndata

    def build(self, data: TDC) -> Self:
        """命令分析功能, 传入字符串或消息链"""
        self.reset()
        if self.checker and not self.checker(data):
            raise TypeError(data)
        self.origin = data
        if data.__class__ is str:
            data = [data]  # type: ignore
        i, raw_data = 0, self.raw_data
        for unit in data:
            if (uname := unit.__class__.__name__) in self.filter_out:
                continue
            if (proc := self.preprocessors.get(uname)) and (res := proc(unit)):
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

    def addon(self, *data: str | Any) -> Self:
        self.raw_data = self.bak_data.copy()
        for i, d in enumerate(data):
            if not d:
                continue
            if isinstance(d, str) and i > 0 and isinstance(self.raw_data[-1], str):
                self.raw_data[-1] += f"{self.separators[0]}{d}"
            else:
                self.raw_data.append(d)
                self.ndata += 1
        self.current_index = 0
        self.bak_data = self.raw_data.copy()
        if self.message_cache:
            self.token = self.generate_token(self.raw_data)
        return self

    def next(self, separate: tuple[str, ...] | None = None, move: bool = True) -> tuple[str | Any, bool]:
        """获取解析需要的下个数据"""
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
        """把 pop的数据放回 (实际只是‘指针’移动)"""
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

    def release(self, separate: tuple[str, ...] | None = None, recover: bool = False) -> list[str | Any]:
        _result = []
        data = self.bak_data if recover else self.raw_data[self.current_index:]
        for _data in data:
            if _data.__class__ is str:
                _result.extend(split(_data, separate or (' ',)))
            else:
                _result.append(_data)
        return _result

    def data_set(self):
        return self.raw_data.copy(), self.current_index

    def data_reset(self, data: list[str | Any], index: int):
        self.raw_data = data
        self.current_index = index
