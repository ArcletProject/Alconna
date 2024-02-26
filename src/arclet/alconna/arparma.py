from __future__ import annotations

import inspect
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Callable, ClassVar, Generic, TypeVar, cast, overload
from typing_extensions import Self

from tarina import Empty, generic_isinstance, lang, safe_eval

from .exceptions import BehaveCancelled, OutBoundsBehave
from .model import HeadResult, OptionResult, SubcommandResult
from .typing import TDC

T = TypeVar("T")
T1 = TypeVar("T1")
D = TypeVar("D")


def _handle_opt(_pf: str, _parts: list[str], _opts: dict[str, OptionResult]):
    """处理 `options.xxx.yyy.zzz` 形式的参数"""
    if _pf == "options":
        _pf = _parts.pop(0)
    if not _parts:  # options.foo or foo
        return _opts, _pf
    elif not (__src := _opts.get(_pf)):  # options.foo.bar or foo.bar
        return _opts, _pf
    if (_end := _parts.pop(0)) == "value":
        return __src, _end
    if _end == "args":
        return (__src.args, _parts.pop(0)) if _parts else (__src, _end)
    return __src.args, _end


def _handle_sub(_pf: str, _parts: list[str], _subs: dict[str, SubcommandResult]):
    """处理 `subcommands.xxx.yyy.zzz` 形式的参数"""
    if _pf == "subcommands":
        _pf = _parts.pop(0)
    if not _parts:
        return _subs, _pf
    elif not (__src := _subs.get(_pf)):
        return _subs, _pf
    if (_end := _parts.pop(0)) == "value":
        return __src, _end
    if _end == "args":
        return (__src.args, _parts.pop(0)) if _parts else (__src, _end)
    if _end == "options" and (_end in __src.options or not _parts):
        raise RuntimeError(lang.require("arparma", "ambiguous_name").format(target=f"{_pf}.{_end}"))
    if _end == "options" or _end in __src.options:
        return _handle_opt(_end, _parts, __src.options)
    if _end == "subcommands" and (_end in __src.subcommands or not _parts):
        raise RuntimeError(lang.require("arparma", "ambiguous_name").format(target=f"{_pf}.{_end}"))
    if _end == "subcommands" or _end in __src.subcommands:
        return _handle_sub(_end, _parts, __src.subcommands)
    return __src.args, _end


class _Query(Generic[T]):
    source: Arparma

    def __get__(self, instance: Arparma, owner: type) -> _Query[T]:
        self.source = instance
        return self

    def __set_name__(self, owner, name):
        self.name = name

    def __getitem__(self, item: type[T1]) -> _Query[T1]:
        return cast("_Query[T1]", self)

    @overload
    def __call__(self, path: str) -> T | None:
        ...

    @overload
    def __call__(self, path: str, default: D) -> T | D:
        ...

    def __call__(self, path: str, default: D | None = None) -> T | D | None:
        """查询 `Arparma` 中的数据

        Args:
            path (str): 要查询的路径
            default (T | None, optional): 如果查询失败, 则返回该值
        """
        source, endpoint = self.source.__require__(path.split("."))
        if source is None:
            return default
        if isinstance(source, dict):
            return source.get(endpoint, default) if endpoint else MappingProxyType(source)  # type: ignore
        return getattr(source, endpoint, default) if endpoint else source  # type: ignore


class Arparma(Generic[TDC]):
    """承载解析结果与操作数据的接口类

    Attributes:
        origin (TDC): 原始数据
        matched (bool): 是否匹配
        header_match (HeadResult): 命令头匹配结果
        error_info (type[BaseException] | BaseException | str): 错误信息
        error_data (list[str | Any]): 错误数据
        main_args (dict[str, Any]): 主参数匹配结果
        other_args (dict[str, Any]): 其他参数匹配结果
        options (dict[str, OptionResult]): 选项匹配结果
        subcommands (dict[str, SubcommandResult]): 子命令匹配结果
    """

    header_match: HeadResult
    options: dict[str, OptionResult]
    subcommands: dict[str, SubcommandResult]

    def __init__(
        self,
        source: str,
        origin: TDC,
        matched: bool = False,
        header_match: HeadResult | None = None,
        error_info: type[Exception] | Exception | None = None,
        error_data: list[str | Any] | None = None,
        main_args: dict[str, Any] | None = None,
        options: dict[str, OptionResult] | None = None,
        subcommands: dict[str, SubcommandResult] | None = None,
        ctx: dict[str, Any] | None = None,
    ):
        """初始化 `Arparma`
        Args:
            source (str): 命令源
            origin (TDC): 原始数据
            matched (bool, optional): 是否匹配
            header_match (HeadResult | None, optional): 命令头匹配结果
            error_info (type[Exception] | Exception | None, optional): 错误信息
            error_data (list[str | Any] | None, optional): 错误数据
            main_args (dict[str, Any] | None, optional): 主参数匹配结果
            options (dict[str, OptionResult] | None, optional): 选项匹配结果
            subcommands (dict[str, SubcommandResult] | None, optional): 子命令匹配结果
            ctx (dict[str, Any] | None, optional): 上下文
        """
        self.source = source
        self.origin = origin
        self.matched = matched
        self.header_match = header_match or HeadResult()
        self.error_info = error_info
        self.error_data = error_data or []
        self.main_args = main_args or {}
        self.other_args = {}
        self.options = options or {}
        self.subcommands = subcommands or {}
        self.context = ctx or {}

    _additional: ClassVar[dict[str, Callable[[], Any]]] = {}
    query = _Query[Any]()

    def _clr(self):
        self.context.clear()
        self.error_data.clear()
        self.main_args.clear()
        self.other_args.clear()
        self.options.clear()
        self.subcommands.clear()
        ks = list(self.__dict__.keys())
        for k in ks:
            delattr(self, k)

    @property
    def header(self) -> dict[str, Any]:
        """返回可能解析到的命令头中的组信息"""
        return self.header_match.groups

    @property
    def head_matched(self):
        """返回命令头是否匹配"""
        return self.header_match.matched

    @property
    def header_result(self):
        """返回命令头匹配结果"""
        return self.header_match.result

    @property
    def non_component(self) -> bool:
        """返回是否没有解析到任何组件"""
        return not self.subcommands and not self.options

    @property
    def components(self) -> dict[str, OptionResult | SubcommandResult]:
        """返回解析到的组件"""
        return {**self.options, **self.subcommands}

    @property
    def all_matched_args(self) -> dict[str, Any]:
        """返回 Alconna 中所有 Args 解析到的值"""
        return {**self.main_args, **self.other_args}

    @property
    def token(self) -> int:
        """返回命令的 Token"""
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

    def unpack(self) -> None:
        """处理 `Arparma` 中的数据"""
        self._unpack_opts(self.options)
        self._unpack_subs(self.subcommands)

    @staticmethod
    def behave_cancel():
        """取消行为器的后续操作"""
        raise BehaveCancelled

    @staticmethod
    def behave_fail():
        """取消行为器的后续操作并抛出 `OutBoundsBehave`"""
        raise OutBoundsBehave

    def execute(self, behaviors: list[ArparmaBehavior] | None = None) -> Self:
        """执行行为器

        Args:
            behaviors (list[ArparmaBehavior] | None, optional): 要执行的行为器列表
        Returns:
            Self: 返回自身
        """
        if not behaviors:
            return self
        for b in behaviors:
            b.before_operate(self)
        for b in behaviors:
            try:
                b.operate(self)
            except BehaveCancelled:
                continue
            except OutBoundsBehave as e:
                return self.fail(e)
        return self

    def call(self, target: Callable[..., T]) -> T:
        """依据 `Arparma` 中的数据调用函数

        Args:
            target (Callable[..., T]): 要调用的函数
        Returns:
            T: 函数返回值
        Raises:
            RuntimeError: 如果 Arparma 未匹配, 则抛出 RuntimeError
        """
        if not self.matched:
            raise RuntimeError("No matched")
        pos_args = []
        kw_args = {}
        data = {
            **{k: v() for k, v in self._additional.items()},
            **self.all_matched_args,
            "context": self.context,
            "all_args": self.all_matched_args,
            "options": self.options,
            "subcommands": self.subcommands,
        }

        sig = inspect.signature(target)
        for p in sig.parameters.values():
            if p.name not in data:
                continue
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
                pos_args.append(data[p.name])
            elif p.kind == p.VAR_POSITIONAL:
                pos_args.extend(data[p.name])
            elif p.kind == p.VAR_KEYWORD:
                kw_args = {**kw_args, **data[p.name]}
            else:
                kw_args[p.name] = data[p.name]
        bind = sig.bind(*pos_args, **kw_args)
        bind.apply_defaults()
        try:
            return target(*bind.args, **bind.kwargs)
        finally:
            data.clear()

    def fail(self, exc: type[Exception] | Exception) -> Self:
        """生成一个失败的 `Arparma`"""
        return Arparma(self.source, self.origin, False, self.header_match, error_info=exc)  # type: ignore

    def __require__(self, parts: list[str]) -> tuple[dict[str, Any] | OptionResult | SubcommandResult | None, str]:
        """如果能够返回, 除开基本信息, 一定返回该path所在的dict"""
        if len(parts) == 1:
            part = parts[0]
            if part in {"options", "subcommands", "main_args", "other_args", "context"}:
                return getattr(self, part, {}), ""
            for src in (self.main_args, self.other_args, self.options, self.subcommands, self.context):
                if part in src:
                    return src, part
            return (self.all_matched_args, "") if part == "args" else (None, part)
        prefix = parts.pop(0)  # parts[0]
        if prefix in {"options", "subcommands"} and prefix in self.components:
            raise RuntimeError(lang.require("arparma", "ambiguous_name").format(target=prefix))
        if prefix == "options" or prefix in self.options:
            return _handle_opt(prefix, parts, self.options)
        if prefix == "subcommands" or prefix in self.subcommands:
            return _handle_sub(prefix, parts, self.subcommands)
        prefix = prefix.replace("$main", "main_args").replace("$other", "other_args")
        if prefix in {"main_args", "other_args"}:
            return getattr(self, prefix, {}), parts.pop(0)
        path = ".".join([prefix] + parts)
        if path in self.context:
            return self.context, path
        try:
            return safe_eval(path, self.context), ""  # type: ignore
        except Exception:
            return None, prefix

    def query_with(self, arg_type: type[T], *args):
        return self.query[arg_type](*args)

    def find(self, path: str) -> bool:
        """查询路径是否存在

        Args:
            path (str): 要查询的路径

        Returns:
            bool: 是否存在
        """
        return self.query(path, Empty) != Empty

    exist = find

    @classmethod
    def addition(cls, **supplier: Callable[[], Any]):
        cls._additional.update(supplier)

    @overload
    def __getitem__(self, item: str) -> Any:
        ...

    @overload
    def __getitem__(self, item: type[T]) -> T | None:
        ...

    @overload
    def __getitem__(self, item: tuple[type[T], int]) -> T | None:
        ...

    def __getitem__(self, item: str | type[T] | tuple[type[T], int]) -> T | Any | None:
        """查询 `Arparma` 中的数据

        Args:
            item (str | type[T]): 要查询的路径或类型
        """

        if isinstance(item, str):
            return self.query(item)
        if isinstance(item, tuple):
            return [i for i in self.all_matched_args.values() if generic_isinstance(i, item[0])][item[1]]
        return next(i for i in self.all_matched_args.values() if generic_isinstance(i, item))

    def __getattr__(self, item: str):
        return self.all_matched_args.get(item, self.query(item.replace("_", ".")))

    def __repr__(self):
        if not self.matched:
            attrs = ((s, getattr(self, s, None)) for s in ("matched", "header_match", "error_data", "error_info"))
            return ", ".join([f"{a}={v}" for a, v in attrs])
        else:
            attrs = {
                "matched": self.matched,
                "header_match": self.header_match,
                "options": self.options,
                "subcommands": self.subcommands,
                "main_args": self.main_args,
                "other_args": self.other_args,
            }
            return ", ".join([f"{a}={v}" for a, v in attrs.items() if v])


@dataclass(init=True, unsafe_hash=True, repr=True)
class ArparmaBehavior(metaclass=ABCMeta):
    """解析结果行为器的基类, 对应一个对解析结果的操作行为

    Attributes:
        requires (list[ArparmaBehavior]): 该行为器所依赖的行为器
    """

    record: dict[int, dict[str, tuple[Any, Any]]] = field(default_factory=dict, init=False, repr=False, hash=False)
    requires: list[ArparmaBehavior] = field(init=False, hash=False, repr=False)

    def before_operate(self, interface: Arparma):
        """在操作前调用, 用于准备数据"""
        if not self.record:
            return
        if not (_record := self.record.get(interface.token)):
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
        """对解析结果进行操作"""
        ...

    def update(self, interface: Arparma, path: str, value: Any):
        """更新解析结果

        Args:
            interface (Arparma): Arparma 实例
            path (str): 要更新的路径
            value (Any): 要更新的值
        """

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
    for b in getattr(behavior, "requires", []):
        res.extend(requirement_handler(b))
    res.append(behavior)
    return res
