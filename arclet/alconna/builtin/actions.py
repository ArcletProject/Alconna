"""Alconna ArgAction相关"""
import inspect
from typing import Callable, Any, Optional, TYPE_CHECKING, Union, Coroutine, Dict
from arclet.alconna.base import ArgAction
from arclet.alconna.util import Singleton


class _StoreValue(ArgAction):
    """针对特定值的类"""

    def __init__(self, value: Any):
        super().__init__(lambda: value)

    def handle(self, option_dict, varargs, kwargs, is_raise_exception):
        return self.action()


def store_bool(value: bool):
    """存储一个布尔值"""
    return _StoreValue(value)


def store_const(value: int):
    """存储一个整数"""
    return _StoreValue(value)


class HelpDispatch(metaclass=Singleton):
    """帮助信息"""
    helpers: Dict[str, ArgAction] = {}
    help_send_action: Callable[[str], Union[Any, Coroutine]] = lambda x: print(x)


def require_help_send_action(action: Optional[Callable[[str], Any]] = None, command: Optional[str] = None):
    """修改help_send_action"""
    if action is None:
        if command is None:
            return HelpDispatch.help_send_action
        return HelpDispatch.helpers[command].action
    if command is None:
        HelpDispatch.help_send_action = action
        for helper in HelpDispatch.helpers.values():
            helper.awaitable = inspect.iscoroutinefunction(action)
    else:
        HelpDispatch.helpers[command].action = action
        HelpDispatch.helpers[command].awaitable = inspect.iscoroutinefunction(action)


def help_send(command: str, help_string_call: Callable[[], str]):
    """发送帮助信息"""

    class _HELP(ArgAction):
        def __init__(self):
            super().__init__(HelpDispatch.help_send_action)

        def handle(self, option_dict, varargs, kwargs, is_raise_exception):
            action = require_help_send_action(command=command)
            if action:
                return action(help_string_call())

        async def handle_async(self, option_dict, varargs, kwargs, is_raise_exception):
            action = require_help_send_action(command=command)
            if action:
                return await action(help_string_call())

    HelpDispatch.helpers[command] = _HELP()
    return HelpDispatch.helpers[command]


if TYPE_CHECKING:
    from .. import alconna_version


    def version(value: Optional[tuple]):
        """返回一个以元组形式存储的版本信息"""
        if value:
            return _StoreValue(value)
        return _StoreValue(alconna_version)
