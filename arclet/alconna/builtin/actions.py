"""Alconna ArgAction相关"""
import inspect
from datetime import datetime
from typing import Callable, Any, Optional, TYPE_CHECKING, Union, Coroutine, Dict
from arclet.alconna.base import ArgAction
from arclet.alconna.util import Singleton
from arclet.alconna.arpamar import ArpamarBehavior
from arclet.alconna.exceptions import CancelBehave, OutBoundsBehavior


class _StoreValue(ArgAction):
    """针对特定值的类"""

    def __init__(self, value: Any):
        super().__init__(lambda: value)

    def handle(self, option_dict, varargs, kwargs, is_raise_exception):
        return self.action()


def store_value(value: Any):
    """存储一个值"""
    return _StoreValue(value)


class HelpActionManager(metaclass=Singleton):
    """帮助信息"""
    cache: Dict[str, Callable] = {}
    helpers: Dict[str, ArgAction] = {}
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
            HelpActionManager.helpers[command].awaitable = inspect.iscoroutinefunction(action)


def help_send(command: str, help_string_call: Callable[[], str]):
    """发送帮助信息"""

    class _HELP(ArgAction):
        def __init__(self):
            super().__init__(HelpActionManager.send_action)

        def handle(self, option_dict, varargs, kwargs, is_raise_exception):
            action = require_help_send_action(command=command)
            if action:
                return action(help_string_call())

        async def handle_async(self, option_dict, varargs, kwargs, is_raise_exception):
            action = require_help_send_action(command=command)
            if action:
                return await action(help_string_call())

    HelpActionManager.helpers.setdefault(command, _HELP())
    if command in HelpActionManager.cache:
        HelpActionManager.helpers[command].action = HelpActionManager.cache[command]
        HelpActionManager.helpers[command].awaitable = inspect.iscoroutinefunction(HelpActionManager.cache[command])
        del HelpActionManager.cache[command]
    return HelpActionManager.helpers[command]


if TYPE_CHECKING:
    from arclet.alconna import alconna_version
    from arclet.alconna.arpamar import ArpamarBehaviorInterface


    def version(value: Optional[tuple]):
        """返回一个以元组形式存储的版本信息"""
        if value:
            return _StoreValue(value)
        return _StoreValue(alconna_version)


def set_default(value: Any, option: Optional[str] = None, subcommand: Optional[str] = None):
    """
    设置一个选项的默认值, 在无该选项时会被设置

    当option与subcommand同时传入时, 则会被设置为该subcommand内option的默认值
    """

    class _SET_DEFAULT(ArpamarBehavior):
        def operate(self, interface: "ArpamarBehaviorInterface"):
            if not option and not subcommand:
                raise CancelBehave
            if option and subcommand is None:
                options: dict = interface.require(f"options")
                options.setdefault(option, value)
            if subcommand and option is None:
                subcommands: dict = interface.require("subcommands")
                subcommands.setdefault(subcommand, value)
            if option and subcommand:
                sub_options: dict = interface.require(f"subcommands.{subcommand}")
                sub_options.setdefault(option, value)

    return _SET_DEFAULT()


def exclusion(target_path: str, other_path: str):
    """
    当设置的两个路径同时存在时, 抛出异常
    """

    class _EXCLUSION(ArpamarBehavior):
        def operate(self, interface: "ArpamarBehaviorInterface"):
            if interface.require(target_path) and interface.require(other_path):
                raise OutBoundsBehavior("两个路径不能同时存在")

    return _EXCLUSION()


def cool_down(seconds: float):
    """
    当设置的时间间隔内被调用时, 抛出异常
    """

    class _COOL_DOWN(ArpamarBehavior):
        def __init__(self):
            self.last_time = datetime.now()

        def operate(self, interface: "ArpamarBehaviorInterface"):
            current_time = datetime.now()
            if (current_time - self.last_time).total_seconds() < seconds:
                interface.change_const("matched", False)
                interface.change_const("error_info", OutBoundsBehavior("操作过于频繁"))
            else:
                self.last_time = current_time

    return _COOL_DOWN()
