"""Alconna ArgAction相关"""
import inspect
from datetime import datetime
from typing import Callable, Any, Optional, TYPE_CHECKING, Union, Coroutine, Dict
from arclet.alconna.base import ArgAction
from arclet.alconna.util import Singleton
from arclet.alconna.arpamar.behavior import ArpamarBehavior
from arclet.alconna.exceptions import BehaveCancelled, OutBoundsBehavior
from arclet.alconna.lang_config import lang_config


class _StoreValue(ArgAction):
    """针对特定值的类"""

    def __init__(self, value: Any):
        super().__init__(lambda: value)

    def handle(self, option_dict, varargs=None, kwargs=None, is_raise_exception=False):
        return self.action()


def store_value(value: Any):
    """存储一个值"""
    return _StoreValue(value)


class HelpActionManager(metaclass=Singleton):
    """帮助信息"""
    cache: Dict[str, Callable]
    helpers: Dict[str, "HelpAction"]
    send_action: Callable[[str], Union[Any, Coroutine]]

    def __init__(self):
        self.cache = {}
        self.helpers = {}
        self.send_action = lambda x: print(x)

    def require_send_action(
            self,
            action: Optional[Callable[[str], Any]] = None,
            command: Optional[str] = None
    ):
        """修改help_send_action"""
        if action is None:
            if command is None:
                return self.send_action
            return self.helpers[command].action
        if command is None:
            self.send_action = action
            for helper in self.helpers.values():
                helper.awaitable = inspect.iscoroutinefunction(action)
        else:
            if not self.helpers.get(command):
                self.cache[command] = action
            else:
                self.helpers[command].action = action


help_manager = HelpActionManager()


class HelpAction(ArgAction):
    help_string_call: Callable[[], str]

    def __init__(self, help_call, command=None):
        super().__init__(help_manager.send_action)
        self.help_string_call = help_call
        self.command = command

    def handle(self, option_dict, varargs=None, kwargs=None, is_raise_exception=False):
        action = help_manager.require_send_action(command=self.command)
        if action:
            return super().handle({"help": self.help_string_call()}, varargs, kwargs, is_raise_exception)
        return option_dict


def help_send(command: str, help_string_call: Callable[[], str]):
    """帮助信息的发送 action"""
    if command not in help_manager.helpers:
        help_manager.helpers[command] = HelpAction(help_string_call, command)
    else:
        help_manager.helpers[command].help_string_call = help_string_call

    if command in help_manager.cache:
        help_manager.helpers[command].action = help_manager.cache[command]
        del help_manager.cache[command]
    return help_manager.helpers[command]


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
                raise OutBoundsBehavior(
                    lang_config.behavior_exclude_matched.format(target=target_path, other=other_path)
                )

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
                interface.change_const("error_info", OutBoundsBehavior(lang_config.behavior_cooldown_matched))
            else:
                self.last_time = current_time

    return _CoolDown()
