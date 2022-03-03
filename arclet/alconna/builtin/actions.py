"""Alconna ArgAction相关"""
import inspect
from typing import Callable, Any, Optional, TYPE_CHECKING, Union, Coroutine, List
from ..base import ArgAction


class _StoreValue(ArgAction):
    """针对特定值的类"""

    def __init__(self, value: Any):
        super().__init__(lambda: value)

    def handle(self, option_dict, is_raise_exception):
        return self.action()


def store_bool(value: bool):
    """存储一个布尔值"""
    return _StoreValue(value)


def store_const(value: int):
    """存储一个整数"""
    return _StoreValue(value)


helpers: List[ArgAction] = []
help_send_action: Callable[[str], Union[Any, Coroutine]] = lambda x: print(x)


def change_help_send_action(action: Callable[[str], Any]):
    """修改help_send_action"""
    global help_send_action
    help_send_action = action
    for helper in helpers:
        helper.awaitable = inspect.iscoroutinefunction(action)


def help_send(help_string_call: Callable[[], str]):
    """发送帮助信息"""

    def get_help():
        return help_send_action

    class _HELP(ArgAction):
        def __init__(self):
            super().__init__(help_send_action)

        def handle(self, option_dict, is_raise_exception):
            return get_help()(help_string_call())

        async def handle_async(self, option_dict, is_raise_exception):
            return await get_help()(help_string_call())

    helpers.append(_HELP())
    return helpers[-1]


if TYPE_CHECKING:
    from .. import alconna_version


    def version(value: Optional[tuple]):
        """返回一个以元组形式存储的版本信息"""
        if value:
            return _StoreValue(value)
        return _StoreValue(alconna_version)
