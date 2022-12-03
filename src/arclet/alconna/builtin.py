from typing import TYPE_CHECKING, Optional, Any

from .components.action import ArgAction
from .components.behavior import ArpamarBehavior
from .exceptions import BehaveCancelled

__all__ = ["set_default", "store_value", "version", "store_true", "store_false"]


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


def set_default(
        value: Any,
        arg: Optional[str] = None,
        option: Optional[str] = None,
        subcommand: Optional[str] = None,
):
    """
    设置一个选项的默认值, 在无该选项时会被设置

    当option与subcommand同时传入时, 则会被设置为该subcommand内option的默认值

    Args:
        value: 默认值
        arg: 参数名称
        option: 选项名
        subcommand: 子命令名
    """

    class _SetDefault(ArpamarBehavior):
        def operate(self, interface: "Arparma"):
            if not option and not subcommand:
                raise BehaveCancelled
            if arg:
                interface.update("other_args", {arg: value})
            if option and subcommand is None and not interface.query(f"options.{option}"):
                interface.update(
                    f"options.{option}",
                    {"value": None, "args": {arg: value}} if arg else {"value": value, "args": {}}
                )
            if subcommand and option is None and not interface.query(f"subcommands.{subcommand}"):
                interface.update(
                    f"subcommands.{subcommand}",
                    {"value": None, "args": {arg: value}, "options": {}}
                    if arg else {"value": value, "args": {}, "options": {}}
                )
            if option and subcommand and not interface.query(f"{subcommand}.options.{option}"):
                interface.update(
                    f"{subcommand}.options.{option}",
                    {"value": None, "args": {arg: value}} if arg else {"value": value, "args": {}}
                )

    return _SetDefault()
