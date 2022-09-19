from typing import TYPE_CHECKING, Optional, Any

from .components.action import ArgAction
from .components.behavior import ArpamarBehavior
from .exceptions import BehaveCancelled
from .base import Option
from .args import Args

__all__ = ["HelpOption", "ShortcutOption", "CompletionOption", "set_default", "store_value", "version"]

HelpOption = Option("--help|-h", help_text="显示帮助信息")
ShortcutOption = Option(
    '--shortcut|-sct', Args["delete;O", "delete"]["name", str]["command", str, "_"],
    help_text='设置快捷命令'
)
CompletionOption = Option("--comp|-cp", help_text="补全当前命令")


class _StoreValue(ArgAction):
    """针对特定值的类"""

    def __init__(self, value: Any):
        super().__init__(lambda: value)

    def handle(self, option_dict, varargs=None, kwargs=None, raise_exception=False):
        return self.action()


def store_value(value: Any):
    """存储一个值"""
    return _StoreValue(value)


if TYPE_CHECKING:
    from arclet.alconna import alconna_version
    from arclet.alconna.arpamar import Arpamar


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
        def operate(self, interface: "Arpamar"):
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
