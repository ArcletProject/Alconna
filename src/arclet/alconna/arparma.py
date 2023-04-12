from __future__ import annotations

from abc import ABCMeta, abstractmethod
from contextlib import suppress
from dataclasses import dataclass, field
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Callable, Generic, Mapping, TypeVar, overload
from tarina import get_signature, generic_isinstance, Empty

from typing_extensions import Self

from .config import config
from .exceptions import BehaveCancelled, OutBoundsBehave
from .model import HeadResult, OptionResult, SubcommandResult
from .typing import TDataCollection

T = TypeVar('T')
D = TypeVar('D')


def _handle_opt(_pf: str, _parts: list[str], _opts: dict[str, OptionResult]):
    if _pf == "options":
        _pf = _parts.pop(0)
    if not _parts:  # options.foo or foo
        return _opts, _pf
    elif not (__src := _opts.get(_pf)):  # options.foo.bar or foo.bar
        return _opts, _pf
    if (_end := _parts.pop(0)) == "value":
        return __src, _end
    if _end == 'args':
        return (__src.args, _parts.pop(0)) if _parts else (__src, _end)
    return __src.args, _end


def _handle_sub(_pf: str, _parts: list[str], _subs: dict[str, SubcommandResult]):
    if _pf == "subcommands":
        _pf = _parts.pop(0)
    if not _parts:
        return _subs, _pf
    elif not (__src := _subs.get(_pf)):
        return _subs, _pf
    if (_end := _parts.pop(0)) == "value":
        return __src, _end
    if _end == 'args':
        return (__src.args, _parts.pop(0)) if _parts else (__src, _end)
    if _end == "options" and (_end in __src.options or not _parts):
        raise RuntimeError(config.lang.arpamar_ambiguous_name.format(target=f"{_pf}.{_end}"))
    if _end == "options" or _end in __src.options:
        return _handle_opt(_end, _parts, __src.options)
    if _end == "subcommands" and (_end in __src.subcommands or not _parts):
        raise RuntimeError(config.lang.arpamar_ambiguous_name.format(target=f"{_pf}.{_end}"))
    if _end == "subcommands" or _end in __src.subcommands:
        return _handle_sub(_end, _parts, __src.subcommands)
    return __src.args, _end


class Arparma(Generic[TDataCollection]):
    """承载解析结果与操作数据的接口类"""
    header_match: HeadResult
    options: dict[str, OptionResult]
    subcommands: dict[str, SubcommandResult]

    def __init__(
        self,
        source: str,
        origin: TDataCollection,
        matched: bool = False,
        header_match: HeadResult | None = None,
        error_info: type[BaseException] | BaseException | str = '',
        error_data: list[str | Any] | None = None,
        main_args: dict[str, Any] | None = None,
        options: dict[str, OptionResult] | None = None,
        subcommands: dict[str, SubcommandResult] | None = None,
    ):
        self._source = source
        self.origin = origin
        self.matched = matched
        self.header_match = header_match or HeadResult()
        self.error_info = error_info
        self.error_data = error_data or []
        self.main_args = main_args or {}
        self.other_args = {}
        self.options = options or {}
        self.subcommands = subcommands or {}

    def _clr(self):
        ks = list(self.__dict__.keys())
        for k in ks:
            delattr(self, k)

    @property
    def source(self):
        from .manager import command_manager
        return command_manager.get_command(self._source)

    @property
    def header(self) -> dict[str, Any]:
        """返回可能解析到的命令头中的信息"""
        return self.header_match.groups

    @property
    def head_matched(self):
        return self.header_match.matched

    @property
    def header_result(self):
        return self.header_match.result

    @property
    def non_component(self) -> bool:
        return not self.subcommands and not self.options

    @property
    def components(self) -> dict[str, OptionResult | SubcommandResult]:
        return {**self.options, **self.subcommands}

    @property
    def all_matched_args(self) -> dict[str, Any]:
        """返回 Alconna 中所有 Args 解析到的值"""
        return {**self.main_args, **self.other_args}

    @property
    def token(self) -> int:
        from .manager import command_manager
        return command_manager.get_token(self)

    def _unpack_opts(self, _data):
        for _v in _data.values():
            self.other_args = {**self.other_args, **_v.args}

    def _unpack_subs(self, _data):
        for _v in _data.values():
            self.other_args = {**self.other_args, **_v.args}
            if _v.options:
                self._unpack_opts(_v.options)
            if _v.subcommands:
                self._unpack_subs(_v.subcommands)

    def unpack(
        self,
    ) -> None:
        """处理 Arparma 中的数据"""
        self._unpack_opts(self.options)
        self._unpack_subs(self.subcommands)

    @staticmethod
    def behave_cancel():
        raise BehaveCancelled

    @staticmethod
    def behave_fail():
        raise OutBoundsBehave

    def execute(self, behaviors: list[ArparmaBehavior] | None = None) -> Self:
        if behaviors := (self.source.behaviors[1:] + (behaviors or [])):
            exc_behaviors = []
            for behavior in behaviors:
                exc_behaviors.extend(requirement_handler(behavior))
            for b in exc_behaviors:
                b.before_operate(self)
            for b in exc_behaviors:
                try:
                    b.operate(self)
                except BehaveCancelled:
                    continue
                except OutBoundsBehave as e:
                    return self.fail(e)
        return self

    def call(self, target: Callable[..., T], **additional):
        if self.matched:
            names = tuple(p.name for p in get_signature(target))
            return target(**{k: v for k, v in {**self.all_matched_args, **additional}.items() if k in names})
        raise RuntimeError

    def fail(self, exc: type[BaseException] | BaseException | str):
        return Arparma(self._source, self.origin, False, self.header_match, error_info=exc)

    def __require__(self, parts: list[str]) -> tuple[dict[str, Any] | OptionResult | SubcommandResult | None, str]:
        """如果能够返回, 除开基本信息, 一定返回该path所在的dict"""
        if len(parts) == 1:
            part = parts[0]
            for src in (self.main_args, self.other_args, self.options, self.subcommands):
                if part in src:
                    return src, part
            if part in {"options", "subcommands", "main_args", "other_args"}:
                return getattr(self, part, {}), ''
            return (self.all_matched_args, '') if part == "args" else (None, part)
        prefix = parts.pop(0)  # parts[0]
        if prefix in {"options", "subcommands"} and prefix in self.components:
            raise RuntimeError(config.lang.arpamar_ambiguous_name.format(target=prefix))
        if prefix == "options" or prefix in self.options:
            return _handle_opt(prefix, parts, self.options)
        if prefix == "subcommands" or prefix in self.subcommands:
            return _handle_sub(prefix, parts, self.subcommands)
        prefix = prefix.replace("$main", "main_args").replace("$other", "other_args")
        if prefix in {"main_args", "other_args"}:
            return getattr(self, prefix, {}), parts.pop(0)
        return None, prefix

    @overload
    def query(self, path: str) -> Mapping[str, Any] | Any | None: ...
    @overload
    def query(self, path: str, default: T) -> T | Mapping[str, Any] | Any: ...
    def query(self, path: str, default: T | None = None) -> Any | Mapping[str, Any] | T | None:
        """根据path查询值"""
        source, endpoint = self.__require__(path.split('.'))
        if source is None:
            return default
        if isinstance(source, (OptionResult, SubcommandResult)):
            return getattr(source, endpoint, default) if endpoint else source
        return source.get(endpoint, default) if endpoint else MappingProxyType(source)

    @overload
    def query_with(self, arg_type: type[T], path: str | None = None) -> T | None: ...
    @overload
    def query_with(self, arg_type: type[T], *, default: D) -> T | D: ...
    @overload
    def query_with(self, arg_type: type[T], path: str, default: D) -> T | D: ...
    def query_with(self, arg_type: type[T], path: str | None = None, default: D | None = None) -> T | D | None:
        """根据类型查询参数"""
        if path:
            return res if generic_isinstance(res := self.query(path, Empty), arg_type) else default
        with suppress(IndexError):
            return [v for v in self.all_matched_args.values() if generic_isinstance(v, arg_type)][0]
        return default

    def find(self, path: str) -> bool:
        """查询路径是否存在"""
        return self.query(path, Empty) != Empty

    @overload
    def __getitem__(self, item: type[T]) -> T | None: ...
    @overload
    def __getitem__(self, item: str) -> Any:  ...
    def __getitem__(self, item: str | type[T]) -> T | Any | None:
        if isinstance(item, str):
            return self.query(item)
        if data := self.query_with(item):
            return data

    def __getattr__(self, item: str):
        return self.all_matched_args.get(item, self.query(item.replace('_', '.')))

    def __repr__(self):
        if self.error_info:
            attrs = ((s, getattr(self, s, None)) for s in ("matched", "header_match", "error_data", "error_info"))
            return ", ".join([f"{a}={v}" for a, v in attrs if v is not None])
        else:
            attrs = [(s, getattr(self, s, None)) for s in ("matched", "header_match", "options", "subcommands")]
            margs = {k: v for k, v in self.main_args.items() if k not in ('$varargs', '$kwargs', '$kwonly')}
            attrs.append(("main_args", margs))
            other_args = {k: v for k, v in self.other_args.items() if k not in ('$varargs', '$kwargs', '$kwonly')}
            attrs.append(("other_args", other_args))
            return ", ".join([f"{a}={v}" for a, v in attrs if v])


@dataclass(init=True, unsafe_hash=True, repr=True)
class ArparmaBehavior(metaclass=ABCMeta):
    """
    解析结果行为器的基类, 对应一个对解析结果的操作行为
    """
    record: dict[int, dict[str, tuple[Any, Any]]] = field(default_factory=dict, init=False, repr=False, hash=False)
    requires: list[ArparmaBehavior] = field(init=False, hash=False, repr=False)

    def before_operate(self, interface: Arparma):
        if not self.record:
            return
        if not (_record := self.record.get(interface.token, None)):
            return
        for path, (past, current) in _record.items():
            source, end = interface.__require__(path.split("."))
            if source is None:
                continue
            if isinstance(source, dict):
                if past != Empty:
                    source[end] = past
                elif source.get(end, Empty) != current:
                    source.pop(end)
            elif past != Empty:
                setattr(source, end, past)
            elif getattr(source, end, Empty) != current:
                delattr(source, end)
        _record.clear()

    @abstractmethod
    def operate(self, interface: Arparma):
        ...

    def update(self, interface: Arparma, path: str, value: Any):
        def _update(tkn, src, pth, ep, val):
            _record = self.record.setdefault(tkn, {})
            if isinstance(src, dict):
                _record[pth] = (src.get(ep, Empty), val)
                src[ep] = val
            else:
                _record[pth] = (getattr(src, ep, Empty), val)
                setattr(src, ep, val)

        source, end = interface.__require__(path.split("."))
        if source is None:
            return
        if end:
            _update(interface.token, source, path, end, value)
        elif isinstance(value, dict):
            for k, v in value.items():
                _update(interface.token, source, f"{path}.{k}", k, v)


@lru_cache(4096)
def requirement_handler(behavior: ArparmaBehavior) -> list[ArparmaBehavior]:
    res = []
    for b in getattr(behavior, 'requires', []):
        res.extend(requirement_handler(b))
    res.append(behavior)
    return res
