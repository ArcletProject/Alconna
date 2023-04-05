from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar
from typing_extensions import Self

from .args import Arg
from .base import Option, Subcommand
from .config import config
from .exceptions import NullMessage
from .typing import DataCollection
from .util import split, split_once

_cache: dict[type, dict[str, Any]] = {}


@dataclass(repr=True)
class DataCollectionContainer:
    preprocessors: dict[str, Callable[..., Any]] = field(default_factory=dict)
    to_text: Callable[[Any], str | None] = field(default=lambda x: x if isinstance(x, str) else None)
    separators: tuple[str, ...] = field(default=(' ',))  # 分隔符
    filter_out: list[str] = field(default_factory=list)  # 元素黑名单
    default_separate: bool = field(default=True)
    filter_crlf: bool = field(default=True)
    message_cache: bool = field(default=True)
    param_ids: set[str] = field(default_factory=set)

    context: Arg | Subcommand | Option | None = field(init=False)
    current_index: int = field(init=False)  # 当前数据的index
    ndata: int = field(init=False)  # 原始数据的长度
    bak_data: list[str | Any] = field(init=False)
    raw_data: list[str | Any] = field(init=False)
    temporary_data: dict[str, Any] = field(init=False)  # 临时数据
    temp_token: int = field(init=False)  # 临时token

    @classmethod
    def config(
        cls,
        preprocessors: dict[str, Callable[..., Any]] | None = None,
        to_text: Callable[[Any], str | None] = None,
        filter_out: list[str] | None = None
    ):
        _cache.setdefault(cls, {}).update(locals())

    def __post_init__(self):
        self.reset()
        if __cache := _cache.get(self.__class__, {}):
            self.preprocessors.update(__cache["preprocessors"] or {})
            self.filter_out.extend(__cache["filter_out"] or [])
            self.to_text = __cache["to_text"] or self.to_text

    def reset(self):
        self.current_index, self.ndata, self.temp_token = 0, 0, 0
        self.temporary_data = {}
        self.raw_data, self.bak_data = [], []
        self.context = None

    @staticmethod
    def generate_token(data: list[Any | list[str]]) -> int:
        return hash(str(data))

    @property
    def origin(self) -> DataCollection:
        return self.temporary_data.get("origin", "None")

    @property
    def done(self) -> bool:
        return self.current_index == self.ndata

    def build(self, data: DataCollection[str | Any]) -> Self:
        """命令分析功能, 传入字符串或消息链, 应当在失败时返回fail的arpamar"""
        self.reset()
        self.temporary_data["origin"] = data
        if isinstance(data, str):
            data = [data]
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
            raise NullMessage(config.lang.analyser_handle_null_message.format(target=data))
        self.ndata = i
        self.bak_data = raw_data.copy()
        if self.message_cache:
            self.temp_token = self.generate_token(raw_data)
        return self

    def rebuild(self, *data: str | Any) -> Self:
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
            self.temp_token = self.generate_token(self.raw_data)
        return self

    def popitem(self, separate: tuple[str, ...] | None = None, move: bool = True) -> tuple[str | Any, bool]:
        """获取解析需要的下个数据"""
        if 'sep' in self.temporary_data:
            del self.temporary_data['sep']
        if self.current_index == self.ndata:
            return "", True
        separate = separate or self.separators
        _current_data = self.raw_data[self.current_index]
        if isinstance(_current_data, str):
            _text, _rest_text = split_once(_current_data, separate, self.filter_crlf)
            if move:
                if _rest_text:
                    self.temporary_data['sep'] = separate
                    self.raw_data[self.current_index] = _rest_text
                else:
                    self.current_index += 1
            return _text, True
        if move:
            self.current_index += 1
        return _current_data, False

    def pushback(self, data: str | Any, replace: bool = False):
        """把 pop的数据放回 (实际只是‘指针’移动)"""
        if data in ("", None):
            return
        if 'sep' in self.temporary_data:
            _current_data = self.raw_data[self.current_index]
            self.raw_data[self.current_index] = f"{data}{self.temporary_data['sep'][0]}{_current_data}"
            return
        if self.current_index >= 1:
            self.current_index -= 1
        if replace:
            self.raw_data[self.current_index] = data

    def release(self, separate: tuple[str, ...] | None = None, recover: bool = False) -> list[str | Any]:
        _result = []
        data = self.bak_data if recover else self.raw_data[self.current_index:]
        for _data in data:
            if isinstance(_data, str):
                _result.extend(split(_data, separate))
            else:
                _result.append(_data)
        return _result

    def data_set(self):
        return self.raw_data.copy(), self.current_index

    def data_reset(self, data: list[str | Any], index: int):
        self.raw_data = data
        self.current_index = index


TContainer = TypeVar("TContainer", bound=DataCollectionContainer)
