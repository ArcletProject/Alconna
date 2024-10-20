from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, overload

from tarina import Empty

from .arparma import Arparma, ArparmaBehavior
from .config import lang
from .exceptions import BehaveCancelled
from .base import OptionResult, SubcommandResult

__all__ = ["set_default", "conflict"]


@dataclass
class ConflictWith(ArparmaBehavior):
    source: str
    target: str
    source_limiter: Callable[...,  bool] | None = None
    target_limiter: Callable[..., bool] | None = None

    def get_type(self, res):
        if isinstance(res, OptionResult):
            return lang.require("builtin", "conflict.option")
        if isinstance(res, SubcommandResult):
            return lang.require("builtin", "conflict.subcommand")
        return lang.require("builtin", "conflict.arg")

    def operate(self, interface: Arparma):
        if (s_r := interface.query(self.source, Empty)) is not Empty and (t_r := interface.query(self.target, Empty)) is not Empty:
            source_type = self.get_type(s_r)
            target_type = self.get_type(t_r)
            if self.source_limiter and not self.source_limiter(s_r):
                return
            if self.target_limiter and not self.target_limiter(t_r):
                return
            interface.behave_fail(lang.require("builtin", "conflict.msg").format(
                source_type=source_type,
                target_type=target_type,
                source=self.source,
                target=self.target
            ))


def conflict(
    source: str,
    target: str,
    source_limiter: Callable[..., bool] | None = None,
    target_limiter: Callable[..., bool] | None = None,
):
    """
    当 `source` 与 `target` 同时存在时设置解析结果为失败

    Args:
        source (str): 参数路径1
        target (str): 参数路径2
        source_limiter (Callable[..., bool]): 假设 source 存在时限定特定结果以继续的函数
        target_limiter (Callable[..., bool]): 假设 target 存在时限定特定结果以继续的函数
    """

    return ConflictWith(source, target, source_limiter, target_limiter)


class _MISSING_TYPE:
    pass


MISSING = _MISSING_TYPE()


@dataclass(init=True, eq=True, unsafe_hash=True)
class _SetDefault(ArparmaBehavior):
    _default: Any = field(default=MISSING)
    _default_factory: Callable | _MISSING_TYPE = field(default=MISSING)
    path: str | None = field(default=None)

    @property
    def default(self):
        if self._default is not MISSING:
            return self._default
        if callable(self._default_factory):
            return self._default_factory()
        raise BehaveCancelled("cannot specify both value and factory")

    def operate(self, interface: Arparma):
        if not self.path:
            interface.behave_cancel()
        else:
            def_val = self.default
            if not interface.query(self.path):
                self.update(interface, self.path, def_val)


@overload
def set_default(
    *,
    value: Any,
    path: str,
) -> _SetDefault:
    ...


@overload
def set_default(
    *,
    factory: Callable[..., Any],
    path: str,
) -> _SetDefault:
    ...


def set_default(
    *,
    value: Any = MISSING,
    factory: Callable[..., Any] | _MISSING_TYPE = MISSING,
    path: str | None = None,
) -> _SetDefault:
    """
    设置一个选项的默认值, 在无该选项时会被设置

    当 option 与 subcommand 同时传入时, 则会被设置为该 subcommand 内 option 的默认值

    Args:
        value (Any): 默认值
        factory (Callable[..., Any]): 默认值工厂
        path: str: 参数路径
    """
    if value is not MISSING and factory is not MISSING:
        raise ValueError("cannot specify both value and factory")

    return _SetDefault(value, factory, path)
