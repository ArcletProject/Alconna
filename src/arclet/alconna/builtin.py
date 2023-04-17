from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, overload

from .action import ArgAction
from .arparma import Arparma, ArparmaBehavior
from .exceptions import BehaveCancelled
from .model import OptionResult, SubcommandResult

__all__ = ["set_default", "store_value", "store_true", "store_false"]


class _MISSING_TYPE: pass
MISSING = _MISSING_TYPE()


class _StoreValue(ArgAction):
    def __init__(self, value: Any):
        super().__init__(lambda: value)


def store_value(value: Any):
    """存储一个值"""
    return _StoreValue(value)


store_true = store_value(True)
store_false = store_value(False)


@dataclass(init=True, eq=True, unsafe_hash=True)
class _SetDefault(ArparmaBehavior):
    _default: Any = field(default=MISSING)
    _default_factory: Callable | _MISSING_TYPE = field(default=MISSING)
    arg: str | None = field(default=None)
    option: str | None = field(default=None)
    subcommand: str | None = field(default=None)

    @property
    def default(self):
        if self._default is not MISSING:
            return self._default
        if callable(self._default_factory):
            return self._default_factory()
        raise BehaveCancelled('cannot specify both value and factory')

    def operate(self, interface: Arparma):
        if not self.option and not self.subcommand:
            raise BehaveCancelled
        if self.arg and self.arg not in interface.other_args:
            self.update(interface, f"other_args.{self.arg}", self.default)
        if self.option and self.subcommand is None:
            if not interface.query(f"options.{self.option}"):
                self.update(
                    interface, f"options.{self.option}",
                    OptionResult(None, {self.arg: self.default}) if self.arg else OptionResult(self.default)
                )
            elif self.arg and not interface.query(f"options.{self.option}.{self.arg}"):
                self.update(interface, f"options.{self.option}.{self.arg}", self.default)
        if self.subcommand and self.option is None:
            if not interface.query(f"subcommands.{self.subcommand}"):
                self.update(
                    interface, f"subcommands.{self.subcommand}",
                    SubcommandResult(None, {self.arg: self.default}) if self.arg else SubcommandResult(self.default)
                )
            elif self.arg and not interface.query(f"subcommands.{self.subcommand}.{self.arg}"):
                self.update(interface, f"subcommands.{self.subcommand}.{self.arg}", self.default)
        if self.option and self.subcommand:
            if not interface.query(f"subcommands.{self.subcommand}.options.{self.option}"):
                self.update(
                    interface, f"subcommands.{self.subcommand}.options.{self.option}",
                    OptionResult(None, {self.arg: self.default}) if self.arg else OptionResult(self.default)
                )
            elif self.arg and not interface.query(f"subcommands.{self.subcommand}.options.{self.option}.{self.arg}"):
                self.update(interface, f"subcommands.{self.subcommand}.options.{self.option}.{self.arg}", self.default)


@overload
def set_default(
    *, value: Any, arg: str | None = None, option: str | None = None, subcommand: str | None = None,
) -> _SetDefault:
    ...


@overload
def set_default(
    *, factory: Callable[..., Any], arg: str | None = None, option: str | None = None, subcommand: str | None = None,
) -> _SetDefault:
    ...


def set_default(
    *,
    value: Any = MISSING,
    factory: Callable[..., Any] = MISSING,
    arg: str | None = None, option: str | None = None, subcommand: str | None = None,
) -> _SetDefault:
    """
    设置一个选项的默认值, 在无该选项时会被设置

    当option与subcommand同时传入时, 则会被设置为该subcommand内option的默认值

    Args:
        value: 默认值
        factory: 默认值生成函数
        arg: 参数名称
        option: 选项名
        subcommand: 子命令名
    """
    if value is not MISSING and factory is not MISSING:
        raise ValueError('cannot specify both value and factory')

    return _SetDefault(value, factory, arg, option, subcommand)
