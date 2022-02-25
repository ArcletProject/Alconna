"""Alconna ArgAction相关"""

from typing import Callable, Any, Optional, TYPE_CHECKING, Iterable


class ArgAction:
    """
    负责封装action的类

    Attributes:
        action: 实际的function
    """
    action: Callable[..., Iterable]

    def __init__(self, action: Callable = None):
        """
        ArgAction的构造函数

        Args:
            action: (...) -> Iterable
        """
        self.action = action

    def __call__(self, option_dict, exception_in_time):
        try:
            additional_values = self.action(*option_dict.values())
            if additional_values is None:
                additional_values = list(option_dict.values())
            elif not isinstance(additional_values, Iterable):
                additional_values = [additional_values]
            for i, k in enumerate(option_dict.keys()):
                option_dict[k] = additional_values[i]
        except Exception as e:
            if exception_in_time:
                raise e
        return option_dict


class _StoreValue(ArgAction):
    """针对特定值的类"""

    def __init__(self, value: Any):
        super().__init__(lambda: value)

    def __call__(self, option_dict, exception_in_time):
        return self.action()


def store_bool(value: bool):
    """存储一个布尔值"""
    return _StoreValue(value)


def store_const(value: int):
    """存储一个整数"""
    return _StoreValue(value)


help_send_action: Callable[[str], Any] = lambda x: print(x)


def change_help_send_action(action: Callable[[str], Any]):
    """修改help_send_action"""
    global help_send_action
    help_send_action = action


def help_send(help_string_call: Callable[[], str]):
    """发送帮助信息"""

    class _HELP(ArgAction):
        def __init__(self):
            super().__init__(lambda x: x)

        def __call__(self, option_dict, exception_in_time):
            return help_send_action(help_string_call())

    return _HELP()


if TYPE_CHECKING:
    from . import alconna_version


    def version(value: Optional[tuple]):
        """返回一个以元组形式存储的版本信息"""
        if value:
            return _StoreValue(value)
        return _StoreValue(alconna_version)
