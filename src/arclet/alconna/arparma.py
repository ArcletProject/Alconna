from __future__ import annotations

from warnings import warn
import inspect
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Callable, ClassVar, Generic, TypeVar, cast, overload, Literal
from typing_extensions import Self

from tarina import Empty, generic_isinstance, safe_eval

from .exceptions import BehaveCancelled, OutBoundsBehave
from .base import HeadResult, OptionResult, SubcommandResult
from .utils import TDC
from .args import ArgsMeta, ArgsBase

T = TypeVar("T")
T1 = TypeVar("T1")
D = TypeVar("D")


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
    def __call__(self, path: str, *, force_return: Literal[True]) -> T:
        ...

    @overload
    def __call__(self, path: str, default: D) -> T | D:
        ...

    def __call__(self, path: str, default: D | None = None, *, force_return: bool = False) -> T | D | None:
        """查询 `Arparma` 中的数据

        Args:
            path (str): 要查询的路径
            default (T | None, optional): 如果查询失败, 则返回该值
            force_return (bool, optional): 是否强制返回值, 默认为 False; 如果为 True, 则查询失败时抛出异常
        """
        source, endpoint = self.source.__require__(path.split("."))
        if source is None:
            if force_return:
                raise KeyError(path)
            return default
        if isinstance(source, dict):
            if endpoint:
                if endpoint in source:
                    return source[endpoint]
                if force_return:
                    raise KeyError(path)
                return default
            return MappingProxyType(source)  # type: ignore
        if isinstance(endpoint, str) and endpoint:
            try:
                return getattr(source, endpoint)
            except AttributeError:
                if force_return:
                    raise
                return default
        return source  # type: ignore


class Arparma(Generic[TDC]):
    """承载解析结果与操作数据的接口类

    Attributes:
        origin (TDC): 原始数据
        matched (bool): 是否匹配
        header_match (HeadResult): 命令头匹配结果
        error_info (type[BaseException] | BaseException | str): 错误信息
        error_data (list[str | Any]): 错误数据
        value_result (dict[tuple[str, ...], Any]): 值匹配结果
        args_result (dict[tuple[str, ...], dict[str, Any]]): 参数匹配结果
        context (dict[str, Any]): 上下文
        output (str | None): 输出信息
    """

    header_match: HeadResult
    output: str | None

    def __init__(
        self,
        _id: int,
        origin: TDC,
        matched: bool = False,
        header_match: HeadResult | None = None,
        error_info: type[Exception] | Exception | None = None,
        error_data: list[str | Any] | None = None,
        value_result: dict[tuple[str, ...], Any] | None = None,
        args_result: dict[tuple[str, ...], dict[str, Any]] | None = None,
        ctx: dict[str, Any] | None = None,
    ):
        """初始化 `Arparma`
        Args:
            _id (int): 命令源
            origin (TDC): 原始数据
            matched (bool, optional): 是否匹配
            header_match (HeadResult | None, optional): 命令头匹配结果
            error_info (type[Exception] | Exception | None, optional): 错误信息
            error_data (list[str | Any] | None, optional): 错误数据
            value_result (dict[tuple[str, ...], Any] | None, optional): 值匹配结果
            args_result (dict[tuple[str, ...], dict[str, Any]] | None, optional): 参数匹配结果
            ctx (dict[str, Any] | None, optional): 上下文
        """
        self._id = _id
        self.origin = origin
        self.matched = matched
        self.header_match = header_match or HeadResult()
        self.error_info = error_info
        self.error_data = error_data or []
        self.value_result = value_result or {}
        self.args_result = args_result or {}
        self.context = ctx or {}
        self.output = None
        self.buffer = []

    _additional: ClassVar[dict[str, Callable[[], Any]]] = {}
    query = _Query[Any]()

    def _clr(self):
        self.context.clear()
        self.error_data.clear()
        self.value_result.clear()
        self.args_result.clear()
        ks = list(self.__dict__.keys())
        for k in ks:
            delattr(self, k)

    @property
    def head_matched(self):
        """返回命令头是否匹配"""
        return self.header_match.matched

    @property
    def non_component(self) -> bool:
        """返回是否没有解析到任何组件"""
        return not self.value_result

    @property
    def main_args(self) -> dict[str, Any]:
        """返回 Alconna 中主要 Args 解析到的值"""
        return self.args_result.get((), {})

    @property
    def other_args(self) -> dict[str, Any]:
        """返回 Alconna 中其他 Args 解析到的值"""
        return {k: v for path, args in self.args_result.items() for k, v in args.items() if path}

    @property
    def all_matched_args(self) -> dict[str, Any]:
        """返回 Alconna 中所有 Args 解析到的值"""
        return {k: v for args in self.args_result.values() for k, v in args.items()}

    @property
    def token(self) -> int:
        """返回命令的 Token"""
        from .manager import command_manager

        return command_manager.get_token(self)

    @property
    def source(self):
        from .manager import command_manager

        return command_manager._resolve(self._id)

    @property
    def options(self):
        result = {}
        for path, v in self.value_result.items():
            if path == ():
                continue
            prefixes, key = path[:-1], path[-1]
            if not prefixes:
                if key in result:
                    result[key].value = v
                else:
                    result[key] = SubcommandResult(v)
            else:
                sub = result.setdefault(prefixes[0], SubcommandResult())
                for part in prefixes[1:]:
                    sub = sub.subcommands.setdefault(part, SubcommandResult())
                sub.subcommands[key] = SubcommandResult(v)
        for path, v in self.args_result.items():
            if path == ():
                continue
            prefixes, key = path[:-1], path[-1]
            if not prefixes:
                if key in result:
                    result[key].args = v
                else:
                    result[key] = SubcommandResult(..., v)
            else:
                sub = result.setdefault(prefixes[0], SubcommandResult())
                for part in prefixes[1:]:
                    sub = sub.subcommands.setdefault(part, SubcommandResult())
                if key in sub.subcommands:
                    sub.subcommands[key].args = v
                else:
                    sub.subcommands[key] = SubcommandResult(..., v)
        return result

    @staticmethod
    def behave_cancel(*msg: str):
        """取消行为器的后续操作"""
        raise BehaveCancelled(*msg)

    @staticmethod
    def behave_fail(*msg: str):
        """取消行为器的后续操作并抛出 `OutBoundsBehave`"""
        raise OutBoundsBehave(*msg)

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
            "args": self.main_args,
            "all_args": self.all_matched_args,
            "options": self.options,
        }

        sig = inspect.signature(target)
        for p in sig.parameters.values():
            if p.name not in data:
                continue
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
                if p.name == "args" and isinstance(p.annotation, ArgsMeta) and issubclass(p.annotation, ArgsBase):
                    pos_args.append(p.annotation.load(data[p.name]))
                else:
                    pos_args.append(data[p.name])
            elif p.kind == p.VAR_POSITIONAL:
                pos_args.extend(data[p.name])
            elif p.kind == p.VAR_KEYWORD:
                kw_args = {**kw_args, **data[p.name]}
            else:
                if p.name == "args" and isinstance(p.annotation, ArgsMeta) and issubclass(p.annotation, ArgsBase):
                    kw_args[p.name] = p.annotation.load(data[p.name])
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
        return Arparma(self._id, self.origin, False, self.header_match, error_info=exc)  # type: ignore

    def __require__(self, parts: list[str]) -> tuple[Any, tuple[str, ...] | str | None]:
        """如果能够返回, 除开基本信息, 一定返回该path所在的dict"""
        bak = parts.copy()
        if len(bak) > 1:
            if parts[0] == "*":
                for _path in self.value_result:
                    if parts[1] in _path:
                        parts = list(_path)
                        break
            if parts[-1] == "value":
                parts.pop()
                if tuple(parts) in self.value_result:
                    return self.value_result, tuple(parts)
            elif parts[-1] == "args":
                parts.pop()
                if tuple(parts) in self.args_result:
                    return self.args_result, tuple(parts)
            if tuple(parts) in self.value_result:
                return OptionResult(self.value_result[tuple(parts)], self.args_result.get(tuple(parts), {})), None
                # return self.value_result, tuple(parts)
            may_arg = parts.pop()
            if tuple(parts) in self.args_result:
                return self.args_result[tuple(parts)], may_arg
        else:
            part = bak[0]
            if part in {"main_args", "other_args", "context"}:
                return getattr(self, part, {}), ""
            for src in (self.main_args, self.other_args, self.context):
                if part in src:
                    return src, part
            if (part,) in self.value_result:
                return OptionResult(self.value_result[(part,)], self.args_result.get((part,), {})), None
            if part == "args":
                return self.all_matched_args, ""
        path = ".".join(bak)
        if path in self.context:
            return self.context, path
        try:
            return safe_eval(path, self.context), ""  # type: ignore
        except Exception:
            return None, path

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
        warn(
            f"`Arparma.{item}` is deprecated, use `Arparma.query({item!r})` or `Arparma[{item!r}]` instead",
            category=DeprecationWarning,
            stacklevel=2
        )
        return self.all_matched_args.get(item, self.query(item.replace("_", ".")))

    def __repr__(self):
        if not self.matched:
            attrs = ((s, getattr(self, s, None)) for s in ("matched", "header_match", "error_data", "error_info"))
            return ", ".join([f"{a}={v}" for a, v in attrs])
        else:
            attrs = {
                "matched": self.matched,
                "header_match": self.header_match,
                "value_result": dict(sorted(self.value_result.items(), key=lambda x: x[0])),
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

    requires: list[ArparmaBehavior] = field(init=False, hash=False, repr=False)

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

        def _update(tkn, src, ep, val):
            if isinstance(src, dict):
                src[ep] = val
            else:
                setattr(src, ep, val)

        parts = path.split(".")
        source, end = interface.__require__(parts)
        if source is None:
            return
        if end:
            _update(interface.token, source, end, value)
        elif isinstance(value, dict):
            for k, v in value.items():
                _update(interface.token, source, (*parts, k), v)


@lru_cache(4096)
def requirement_handler(behavior: ArparmaBehavior) -> list[ArparmaBehavior]:
    res = []
    for b in getattr(behavior, "requires", []):
        res.extend(requirement_handler(b))
    res.append(behavior)
    return res
