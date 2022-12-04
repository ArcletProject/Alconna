from typing import TYPE_CHECKING, Optional, Any, Callable, overload

from .components.action import ArgAction
from .components.behavior import ArpamarBehavior
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


@overload
def set_default(
    *,
    value: Any,
    arg: Optional[str] = None,
    option: Optional[str] = None,
    subcommand: Optional[str] = None,
) -> ArpamarBehavior:
    ...


@overload
def set_default(
    *,
    factory: Callable[..., Any],
    arg: Optional[str] = None,
    option: Optional[str] = None,
    subcommand: Optional[str] = None,
) -> ArpamarBehavior:
    ...


def set_default(
    *,
    value: Any = MISSING,
    factory: Callable[..., Any] = MISSING,
    arg: Optional[str] = None,
    option: Optional[str] = None,
    subcommand: Optional[str] = None,
) -> ArpamarBehavior:
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

    class _SetDefault(ArpamarBehavior):

        def __init__(self, default, default_factory):
            self._default = default
            self._default_factory = default_factory

        @property
        def default(self):
            return self._default if self._default is not MISSING else self._default_factory()

        def operate(self, interface: "Arparma"):
            if not option and not subcommand:
                raise BehaveCancelled
            if arg:
                interface.update("other_args", {arg: self.default})
            if option and subcommand is None and not interface.query(f"options.{option}"):
                interface.update(
                    f"options.{option}",
                    {"value": None, "args": {arg: self.default}} if arg else {"value": self.default, "args": {}}
                )
            if subcommand and option is None and not interface.query(f"subcommands.{subcommand}"):
                interface.update(
                    f"subcommands.{subcommand}",
                    {"value": None, "args": {arg: self.default}, "options": {}}
                    if arg else {"value": self.default, "args": {}, "options": {}}
                )
            if option and subcommand and not interface.query(f"{subcommand}.options.{option}"):
                interface.update(
                    f"{subcommand}.options.{option}",
                    {"value": None, "args": {arg: self.default}} if arg else {"value": self.default, "args": {}}
                )

    return _SetDefault(value, factory)
