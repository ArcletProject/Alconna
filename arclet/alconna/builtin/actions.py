"""Alconna ArgAction相关"""
import inspect
from datetime import datetime
from typing import Callable, Any, Optional, TYPE_CHECKING, Union, Coroutine, Dict
from arclet.alconna.base import ArgAction
from arclet.alconna.util import Singleton
from arclet.alconna.arpamar.behavior import ArpamarBehavior
from arclet.alconna.exceptions import BehaveCancelled, OutBoundsBehavior


class _StoreValue(ArgAction):
    """针对特定值的类"""

    def __init__(self, value: Any):
        super().__init__(lambda: value)

    def handle(self, option_dict, varargs, kwargs, is_raise_exception):  # noqa
        return self.action()


def store_value(value: Any):
    """存储一个值"""
    return _StoreValue(value)


class HelpAction(ArgAction):
    help_string_call: Callable

    def __init__(self, help_call, command=None):
        super().__init__(HelpActionManager.send_action)
        self.help_string_call = help_call
        self.command = command

    def handle(self, option_dict, varargs, kwargs, is_raise_exception):  # noqa
        action = require_help_send_action(command=self.command)
        if action:
            help_string = self.help_string_call()
            return super().handle({"help": help_string}, varargs, kwargs, is_raise_exception)
        return option_dict


class HelpActionManager(metaclass=Singleton):
    """帮助信息"""
    cache: Dict[str, Callable] = {}
    helpers: Dict[str, HelpAction] = {}
    send_action: Callable[[str], Union[Any, Coroutine]] = lambda x: print(x)


def require_help_send_action(action: Optional[Callable[[str], Any]] = None, command: Optional[str] = None):
    """修改help_send_action"""
    if action is None:
        if command is None:
            return HelpActionManager.send_action
        return HelpActionManager.helpers[command].action
    if command is None:
        HelpActionManager.send_action = action
        for helper in HelpActionManager.helpers.values():
            helper.awaitable = inspect.iscoroutinefunction(action)
    else:
        if not HelpActionManager.helpers.get(command):
            HelpActionManager.cache[command] = action
        else:
            HelpActionManager.helpers[command].action = action


def help_send(command: str, help_string_call: Callable[[], str]):
    """帮助信息的发送 action"""
    if command not in HelpActionManager.helpers:
        HelpActionManager.helpers[command] = HelpAction(help_string_call, command)
    else:
        HelpActionManager.helpers[command].help_string_call = help_string_call

    if command in HelpActionManager.cache:
        HelpActionManager.helpers[command].action = HelpActionManager.cache[command]
        del HelpActionManager.cache[command]
    return HelpActionManager.helpers[command]


if TYPE_CHECKING:
    from arclet.alconna import alconna_version
    from arclet.alconna.arpamar.behavior import ArpamarBehaviorInterface


    def version(value: Optional[tuple]):
        """返回一个以元组形式存储的版本信息"""
        if value:
            return _StoreValue(value)
        return _StoreValue(alconna_version)


def set_default(value: Any, option: Optional[str] = None, subcommand: Optional[str] = None):
    """
    设置一个选项的默认值, 在无该选项时会被设置

    当option与subcommand同时传入时, 则会被设置为该subcommand内option的默认值

    Args:
        value: 默认值
        option: 选项名
        subcommand: 子命令名
    """

    class _SetDefault(ArpamarBehavior):
        def operate(self, interface: "ArpamarBehaviorInterface"):
            if not option and not subcommand:
                raise BehaveCancelled
            if option and subcommand is None:
                options = interface.require(f"options")  # type: Dict[str, Any]
                options.setdefault(option, value)  # type: ignore
            if subcommand and option is None:
                subcommands = interface.require("subcommands")  # type: Dict[str, Any]
                subcommands.setdefault(subcommand, value)  # type: ignore
            if option and subcommand:
                sub_options = interface.require(f"subcommands.{subcommand}")  # type: Dict[str, Any]
                sub_options.setdefault(option, value)  # type: ignore

    return _SetDefault()


def exclusion(target_path: str, other_path: str):
    """
    当设置的两个路径同时存在时, 抛出异常

    Args:
        target_path: 目标路径
        other_path: 其他路径
    """

    class _EXCLUSION(ArpamarBehavior):
        def operate(self, interface: "ArpamarBehaviorInterface"):
            if interface.require(target_path) and interface.require(other_path):
                raise OutBoundsBehavior("两个路径不能同时存在")

    return _EXCLUSION()


def cool_down(seconds: float):
    """
    当设置的时间间隔内被调用时, 抛出异常

    Args:
        seconds: 时间间隔
    """

    class _CoolDown(ArpamarBehavior):
        def __init__(self):
            self.last_time = datetime.now()

        def operate(self, interface: "ArpamarBehaviorInterface"):
            current_time = datetime.now()
            if (current_time - self.last_time).total_seconds() < seconds:
                interface.change_const("matched", False)
                interface.change_const("error_info", OutBoundsBehavior("操作过于频繁"))
            else:
                self.last_time = current_time

    return _CoolDown()
