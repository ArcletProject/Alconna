from typing import TYPE_CHECKING, Optional, Any, Callable, overload, Union

from .components.action import ArgAction
from .components.behavior import ArparmaBehavior
from .exceptions import BehaveCancelled

__all__ = ["set_default", "store_value", "version", "store_true", "store_false"]


class _MISSING_TYPE:
    pass


MISSING = _MISSING_TYPE()


class _StoreValue(ArgAction):
    """针对特定值的类"""

    def __init__(self, value: Any):
        super().__init__(lambda: value)

    def handle(self, option_dict, varargs=None, kwargs=None, raise_exception=False):
        return self.action()


def store_value(value: Any):
    """存储一个值"""
    return _StoreValue(value)


store_true = store_value(True)
store_false = store_value(False)


if TYPE_CHECKING:
    from arclet.alconna import alconna_version
    from arclet.alconna.arparma import Arparma


    def version(value: Optional[tuple]):
        """返回一个以元组形式存储的版本信息"""
        return _StoreValue(value) if value else _StoreValue(alconna_version)


class _SetDefault(ArparmaBehavior):

    def __init__(
        self,
        default: Any = MISSING,
        default_factory: Union[Callable, _MISSING_TYPE] = MISSING,
        arg: Optional[str] = None,
        option: Optional[str] = None,
        subcommand: Optional[str] = None
    ):
        self._default = default
        self._default_factory = default_factory
        self.arg = arg
        self.opt = option
        self.sub = subcommand

    @property
    def default(self):
        return self._default if self._default is not MISSING else self._default_factory()

    def operate(self, interface: "Arparma"):
        if not self.opt and not self.sub:
            raise BehaveCancelled
        if self.arg:
            interface.update("other_args", {self.arg: self.default})
        if self.opt and self.sub is None and not interface.query(f"options.{self.opt}"):
            interface.update(
                f"options.{self.opt}",
                {"value": None, "args": {self.arg: self.default}} if self.arg else {"value": self.default, "args": {}}
            )
        if self.sub and self.opt is None and not interface.query(f"subcommands.{self.sub}"):
            interface.update(
                f"subcommands.{self.sub}",
                {"value": None, "args": {self.arg: self.default}, "options": {}}
                if self.arg else {"value": self.default, "args": {}, "options": {}}
            )
        if self.opt and self.sub and not interface.query(f"{self.sub}.options.{self.opt}"):
            interface.update(
                f"{self.sub}.options.{self.opt}",
                {"value": None, "args": {self.arg: self.default}} if self.arg else {"value": self.default, "args": {}}
            )


@overload
def set_default(
    *,
    value: Any,
    arg: Optional[str] = None,
    option: Optional[str] = None,
    subcommand: Optional[str] = None,
) -> _SetDefault:
    ...


@overload
def set_default(
    *,
    factory: Callable[..., Any],
    arg: Optional[str] = None,
    option: Optional[str] = None,
    subcommand: Optional[str] = None,
) -> _SetDefault:
    ...


def set_default(
    *,
    value: Any = MISSING,
    factory: Callable[..., Any] = MISSING,
    arg: Optional[str] = None,
    option: Optional[str] = None,
    subcommand: Optional[str] = None,
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
